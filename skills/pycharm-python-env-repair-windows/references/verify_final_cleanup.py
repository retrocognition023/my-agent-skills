"""
复核用户手工执行的提权清理结果：
  1) HKLM\\Software\\Classes\\PyCharmCE2024.2 是否已删除
  2) 防火墙规则是否只剩新版 PyCharm 2026.2.2
  3) PATH / 环境变量最终状态
  4) .py 关联是否仍指向有效的新 exe
  5) 桌面提权文件是否可清理

只读。
"""

from __future__ import annotations

import os
import subprocess
import sys
import winreg

B = chr(92)
DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
AIDIR = os.path.join(DESKTOP, "PyCharm残留清理-需管理员权限")
OLD_KEY = "Software" + B + "Classes" + B + "PyCharmCE2024.2"
OLD_RULE = "PyCharm Community Edition 2024.2.3"


def sec(t: str) -> None:
    print()
    print("=" * 76)
    print(t)
    print("=" * 76)


def check_reg_key() -> bool:
    sec("[1] HKLM\\Software\\Classes\\PyCharmCE2024.2（旧文件类注册项）")
    try:
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, OLD_KEY)
        print("  ❌ 仍然存在！")
        for tail in ("", B + "DefaultIcon", B + "shell" + B + "open" + B + "command"):
            try:
                sk = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, OLD_KEY + tail)
                try:
                    v, _ = winreg.QueryValueEx(sk, "")
                except Exception:
                    v = "(空)"
                print("       ", (tail.strip(B) or "默认"), "=", str(v)[:120])
            except Exception:
                pass
        winreg.CloseKey(k)
        return False
    except FileNotFoundError:
        print("  ✅ 已删除，不再存在")
        return True
    except Exception as e:
        print("  读取异常:", type(e).__name__, e)
        return False


def check_firewall() -> bool:
    sec("[2] 防火墙规则（名称含 pycharm）")
    try:
        r = subprocess.run(["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
                           capture_output=True)
        out = (r.stdout or b"").decode("gbk", "replace")
    except Exception as e:
        print("  netsh 执行失败:", e)
        return False

    blocks = []
    cur = []
    for ln in out.splitlines():
        if ("规则名称" in ln or "Rule Name" in ln) and cur:
            blocks.append(cur)
            cur = [ln]
        else:
            if cur:
                cur.append(ln)
    if cur:
        blocks.append(cur)

    old_hits, new_hits = [], []
    for blk in blocks:
        text = "\n".join(blk)
        low = text.lower()
        if "pycharm community edition 2024.2.3" in low:
            old_hits.append(blk)
        elif "pycharm 2026.2.2" in low:
            new_hits.append(blk)

    if old_hits:
        print(f"  ❌ 旧规则仍存在 {len(old_hits)} 条！")
        for blk in old_hits:
            print("     ", [x.strip() for x in blk[:3]])
        return False
    print("  ✅ 旧规则（PyCharm Community Edition 2024.2.3）已全部删除，0 条残留")

    print(f"  ✅ 新版规则保留 {len(new_hits)} 条:")
    for blk in new_hits:
        name = proto = direction = action = None
        for x in blk:
            s = x.strip()
            if s.startswith("规则名称") or s.startswith("Rule Name"):
                name = s.split(":", 1)[-1].strip()
            if "协议" in s and proto is None:
                proto = s.split(":", 1)[-1].strip()
            if "方向" in s and direction is None:
                direction = s.split(":", 1)[-1].strip()
            if "操作" in s and action is None:
                action = s.split(":", 1)[-1].strip()
        print(f"      - 名称={name}  协议={proto}  方向={direction}  操作={action}")
    return True


def check_path() -> None:
    sec("[3] PATH 与环境变量最终状态")
    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment")
    val, typ = winreg.QueryValueEx(k, "Path")
    print(f"  用户 PATH（类型 {typ}，{len(val)} 字符）:")
    for e in val.split(";"):
        if e.strip():
            print("    ", e.strip())
    print()
    for name in ("PyCharm", "PyCharm Community Edition"):
        try:
            v, _ = winreg.QueryValueEx(k, name)
            exists = os.path.isdir(os.path.expandvars(v.rstrip(";")))
            print(f"  变量 {name:28} = {v}   路径存在: {exists}")
        except FileNotFoundError:
            print(f"  变量 {name:28} = (不存在)")
    winreg.CloseKey(k)


def check_assoc() -> None:
    sec("[4] .py 文件关联链路")
    chain = [("Software" + B + "Classes" + B + ".py", None)]
    try:
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, chain[0][0])
        v, _ = winreg.QueryValueEx(k, "")
        print("  .py ->", v)
        prog = str(v)
        for sub in (B + "shell" + B + "open" + B + "command", B + "DefaultIcon"):
            try:
                kk = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                    "Software" + B + "Classes" + B + prog + sub)
                vv, _ = winreg.QueryValueEx(kk, "")
                print(f"    {sub.strip(B):22} = {str(vv)[:120]}")
                for piece in str(vv).split(chr(34)):
                    if piece.lower().endswith(".exe"):
                        print(f"        目标存在: {os.path.exists(piece)}")
            except Exception:
                print(f"    {sub.strip(B):22} = (未设置)")
    except Exception as e:
        print("  读取失败:", type(e).__name__)


def check_aidir() -> None:
    sec("[5] 桌面提权文件（可清理）")
    if os.path.isdir(AIDIR):
        for f in sorted(os.listdir(AIDIR)):
            p = os.path.join(AIDIR, f)
            print(f"  {f}  ({os.path.getsize(p)} 字节)")
        print("\n  这两项任务已完成，该文件夹可以删除（如需我代删请说明）")
    else:
        print("  文件夹已不存在")


if __name__ == "__main__":
    ok_key = check_reg_key()
    ok_fw = check_firewall()
    check_path()
    check_assoc()
    check_aidir()
    print()
    print("=" * 76)
    print(f"复核结论：注册表残留 {'已清除 ✅' if ok_key else '未清除 ❌'} ；"
          f"防火墙残留 {'已清除 ✅' if ok_fw else '未清除 ❌'}")
    print("=" * 76)
    sys.exit(0 if (ok_key and ok_fw) else 1)
