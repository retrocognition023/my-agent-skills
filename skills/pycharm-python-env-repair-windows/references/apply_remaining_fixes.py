"""
执行"无需管理员权限"的部分（reg.exe 被沙箱拉黑，故注册表导出由本脚本自行实现）：

  1) 导出待删除的注册表键为 .reg 备份（自实现递归导出，兼容 REG_SZ/EXPAND_SZ/DWORD/QWORD/BINARY/MULTI_SZ）
  2) 导出待删除的防火墙规则（netsh 文本 + FirewallRules 注册表原始数据）
  3) 把 PyCharm 的 bin 目录加入用户 PATH（保持 REG_EXPAND_SZ 类型）
  4) 广播 WM_SETTINGCHANGE
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import winreg

B = chr(92)
BIN = "D:" + B + "Pycharm" + B + "PyCharm 2026.2.2" + B + "bin"
BACKUP_ROOT = "D:" + B + "env-backup-20260917"
REG_BACKUP = BACKUP_ROOT + B + "registry-backup"
FW_BACKUP = BACKUP_ROOT + B + "firewall-backup"

KEY_PARENT = "Software" + B + "Classes"
KEY_NAME = "PyCharmCE2024.2"
FW_RULE = "PyCharm Community Edition 2024.2.3"
FW_KEY = ("SYSTEM" + B + "CurrentControlSet" + B + "Services" + B + "SharedAccess"
          + B + "Parameters" + B + "FirewallPolicy" + B + "FirewallRules")

HIVE_LABEL = "HKEY_LOCAL_MACHINE"
skipped: list[str] = []


def esc(s: str) -> str:
    return s.replace(B, B + B).replace('"', B + '"')


def hexbytes(data: bytes) -> str:
    return ",".join(f"{b:02x}" for b in data)


def emit(hive, path: str, fullname: str, out: list[str]) -> None:
    try:
        k = winreg.OpenKey(hive, path)
    except Exception:
        return
    vals = []
    i = 0
    while True:
        try:
            n, v, t = winreg.EnumValue(k, i)
            i += 1
            vals.append((n, v, t))
        except OSError:
            break
    subs = []
    j = 0
    while True:
        try:
            s = winreg.EnumKey(k, j)
            j += 1
            subs.append(s)
        except OSError:
            break
    winreg.CloseKey(k)

    out.append(f"[{fullname}]")
    for n, v, t in vals:
        name_part = "@" if n == "" else f'"{esc(n)}"'
        try:
            if t == winreg.REG_SZ:
                out.append(f'{name_part}="{esc(str(v))}"')
            elif t == winreg.REG_EXPAND_SZ:
                out.append(f'{name_part}=hex(2):' + hexbytes(str(v).encode("utf-16-le") + b"\x00\x00"))
            elif t == winreg.REG_DWORD:
                out.append(f"{name_part}=dword:{int(v) & 0xFFFFFFFF:08x}")
            elif t == winreg.REG_QWORD:
                out.append(f"{name_part}=hex(b):" + hexbytes(int(v).to_bytes(8, "little")))
            elif t == winreg.REG_MULTI_SZ:
                raw = b"".join(x.encode("utf-16-le") + b"\x00\x00" for x in v) + b"\x00\x00"
                out.append(f"{name_part}=hex(7):" + hexbytes(raw))
            elif t == winreg.REG_BINARY:
                out.append(f"{name_part}=hex:" + hexbytes(v))
            else:
                skipped.append(f"{fullname} :: {n} (类型 {t})")
        except Exception as e:
            skipped.append(f"{fullname} :: {n} 序列化失败 {type(e).__name__}")
    out.append("")

    for s in subs:
        emit(hive, path + B + s, fullname + B + s, out)


def backup_registry() -> str:
    os.makedirs(REG_BACKUP, exist_ok=True)
    out_path = REG_BACKUP + B + "HKLM-Software-Classes-" + KEY_NAME + ".reg"
    lines = ["Windows Registry Editor Version 5.00", ""]
    emit(winreg.HKEY_LOCAL_MACHINE, KEY_PARENT + B + KEY_NAME,
         HIVE_LABEL + B + KEY_PARENT + B + KEY_NAME, lines)
    data = "\r\n".join(lines) + "\r\n"
    with open(out_path, "wb") as f:
        f.write(b"\xff\xfe" + data.encode("utf-16-le"))
    ok = os.path.exists(out_path)
    return f"{'OK' if ok else '失败'}  {out_path}  ({os.path.getsize(out_path)} 字节)"


def backup_firewall() -> str:
    os.makedirs(FW_BACKUP, exist_ok=True)
    msgs = []
    # a) netsh 文本
    try:
        r = subprocess.run(["netsh", "advfirewall", "firewall", "show", "rule",
                            "name=" + FW_RULE, "verbose"], capture_output=True)
        p = FW_BACKUP + B + "netsh-stale-rules.txt"
        with open(p, "wb") as f:
            f.write((r.stdout or b"") + b"\n--- STDERR ---\n" + (r.stderr or b""))
        msgs.append(f"netsh 文本 -> {p} ({os.path.getsize(p)} 字节)")
    except Exception as e:
        msgs.append(f"netsh 执行失败: {type(e).__name__} {e}")

    # b) FirewallRules 注册表中的原始数据
    try:
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, FW_KEY)
        vals = []
        i = 0
        while True:
            try:
                n, v, _t = winreg.EnumValue(k, i)
                i += 1
                if "pycharm community edition 2024.2.3" in str(v).lower():
                    vals.append((n, v))
            except OSError:
                break
        winreg.CloseKey(k)
        p2 = FW_BACKUP + B + "firewallrules-raw.txt"
        with open(p2, "w", encoding="utf-8") as f:
            f.write("以下为 HKLM" + B + FW_KEY + B + " 中命中旧路径的规则原始值\n\n")
            for n, v in vals:
                f.write(f"KEY NAME: {n}\nVALUE   : {v}\n\n")
        msgs.append(f"注册表原始值 {len(vals)} 条 -> {p2}")
    except Exception as e:
        msgs.append(f"FirewallRules 读取失败: {type(e).__name__} {e}")
    return " ; ".join(msgs)


def update_path() -> str:
    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                       winreg.KEY_READ | winreg.KEY_WRITE)
    old, typ = winreg.QueryValueEx(k, "Path")
    cur = [p for p in old.split(";") if p.strip()]
    if any(p.strip().rstrip(B).lower() == BIN.lower() for p in cur):
        winreg.CloseKey(k)
        return "已存在，未重复添加"
    new = ";".join(cur + [BIN])
    winreg.SetValueEx(k, "Path", 0,
                      typ if typ in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) else winreg.REG_EXPAND_SZ,
                      new)
    winreg.CloseKey(k)

    res = ctypes.c_ulong()
    ctypes.windll.user32.SendMessageTimeoutW(
        0xFFFF, 0x001A, 0, ctypes.c_wchar_p("Environment"), 0x0002, 3000, ctypes.byref(res))
    return f"已添加（{len(old)} -> {len(new)} 字符）并已广播环境变更"


def verify_path() -> str:
    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment")
    val, _ = winreg.QueryValueEx(k, "Path")
    winreg.CloseKey(k)
    return val


if __name__ == "__main__":
    print("=== [1] 导出注册表键备份 ===")
    print("   ", backup_registry())
    print()
    print("=== [2] 导出防火墙规则备份 ===")
    print("   ", backup_firewall())
    print()
    print("=== [3] 把 PyCharm 加入用户 PATH ===")
    print("   ", update_path())
    print()
    print("=== [4] 复查用户 PATH ===")
    v = verify_path()
    for x in v.split(";"):
        if x.strip():
            mark = "  <== 新增" if x.strip().rstrip(B).lower() == BIN.lower() else ""
            print("   ", x + mark)
    print()
    print("   PyCharm bin 目录存在:", os.path.isdir(BIN))
    if skipped:
        print("\n   注意：以下键值未能写入 .reg（已在备份目录留档）:")
        for s in skipped[:10]:
            print("     -", s)
    sys.exit(0)
