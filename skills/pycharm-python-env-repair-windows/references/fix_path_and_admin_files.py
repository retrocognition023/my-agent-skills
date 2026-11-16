"""
修正 PATH 与残留环境变量，并生成两个需要管理员权限的提权清理文件。

背景（实测）：
  HKCU 环境变量 `PyCharm`                    = D:\\Pycharm\\PyCharm 2026.2.2\\bin   -> 有效（安装器托管）
  HKCU 环境变量 `PyCharm Community Edition`  = D:\\PyCharm Community Edition 2024.2.3\\bin;  -> 失效残留
  用户 PATH 同时含 `%PyCharm Community Edition%`、`%PyCharm%` 与后加的字面路径（三者冗余）

本脚本：
  1) 备份当前 PATH 与环境变量
  2) 删除失效的 PATH 条目 `%PyCharm Community Edition%` 与失效变量
  3) 删除后加的字面重复条目，保留 `%PyCharm%`（安装器托管，升级自动跟随）
  4) 广播环境变更并验证
  5) 生成提权清理文件（注册表删除 .reg + 防火墙删除 .cmd）
"""

from __future__ import annotations

import ctypes
import os
import sys
import winreg

B = chr(92)
BIN = "D:" + B + "Pycharm" + B + "PyCharm 2026.2.2" + B + "bin"
VAR_NEW = "PyCharm"
VAR_OLD = "PyCharm Community Edition"
ENTRY_OLD = "%" + VAR_OLD + "%"
ENTRY_NEW = "%" + VAR_NEW + "%"
TOOLS = os.path.dirname(os.path.abspath(__file__))
DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
AIDIR = os.path.join(DESKTOP, "PyCharm残留清理-需管理员权限")
REG_TARGET = "HKEY_LOCAL_MACHINE" + B + "Software" + B + "Classes" + B + "PyCharmCE2024.2"
FW_RULE = "PyCharm Community Edition 2024.2.3"


def broadcast() -> None:
    res = ctypes.c_ulong()
    ctypes.windll.user32.SendMessageTimeoutW(
        0xFFFF, 0x001A, 0, ctypes.c_wchar_p("Environment"), 0x0002, 3000, ctypes.byref(res))


def backup() -> str:
    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment")
    val, typ = winreg.QueryValueEx(k, "Path")
    winreg.CloseKey(k)
    p = os.path.join(TOOLS, "_path_backup_before_final.txt")
    with open(p, "w", encoding="utf-8") as f:
        f.write(f"TYPE={typ}\n{val}\n")
    return p


def clean_path_and_vars() -> list[str]:
    msgs = []
    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                       winreg.KEY_READ | winreg.KEY_WRITE)
    old, typ = winreg.QueryValueEx(k, "Path")
    entries = [e for e in old.split(";") if e.strip()]

    removed = []
    keep = []
    for e in entries:
        s = e.strip()
        if s.lower() == ENTRY_OLD.lower():
            removed.append(s)
        elif s.rstrip(B).lower() == BIN.lower():
            removed.append(s)          # 我先前加的字面重复项
        else:
            keep.append(s)
    if removed:
        winreg.SetValueEx(k, "Path", 0,
                          typ if typ in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) else winreg.REG_EXPAND_SZ,
                          ";".join(keep))
        msgs.append(f"PATH 移除 {len(removed)} 项: {removed}")
    else:
        msgs.append("PATH 无需变更")

    # 删除失效变量
    try:
        winreg.DeleteValue(k, VAR_OLD)
        msgs.append(f"已删除失效环境变量 {VAR_OLD!r}")
    except FileNotFoundError:
        msgs.append(f"环境变量 {VAR_OLD!r} 不存在")
    winreg.CloseKey(k)
    return msgs


def verify() -> None:
    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment")
    val, _ = winreg.QueryValueEx(k, "Path")
    print("  用户 PATH 现状:")
    for e in val.split(";"):
        if e.strip():
            print("    ", e)
    print()
    for name in (VAR_NEW, VAR_OLD):
        try:
            v, _ = winreg.QueryValueEx(k, name)
            print(f"  变量 {name!r:32} = {v}   路径存在: {os.path.isdir(os.path.expandvars(v.rstrip(';')))}")
        except FileNotFoundError:
            print(f"  变量 {name!r:32} = (已删除)")
    winreg.CloseKey(k)
    print()
    print("  PyCharm 启动器:")
    for f in ("pycharm64.exe", "pycharm.bat", "pycharm.exe"):
        p = os.path.join(BIN, f)
        print(f"    {f:16} 存在: {os.path.exists(p)}")


def make_admin_files() -> list[str]:
    os.makedirs(AIDIR, exist_ok=True)
    made = []

    # 1) 注册表删除用的 .reg（双击即可，Windows 会自动请求管理员）
    reg_path = os.path.join(AIDIR, "1-删除注册表残留（双击运行）.reg")
    content = "Windows Registry Editor Version 5.00\r\n\r\n[-" + REG_TARGET + "]\r\n"
    with open(reg_path, "wb") as f:
        f.write(b"\xff\xfe" + content.encode("utf-16-le"))
    made.append(reg_path)

    # 2) 防火墙规则删除用的 .cmd（右键以管理员身份运行）
    cmd_path = os.path.join(AIDIR, "2-删除防火墙残留（右键以管理员身份运行）.cmd")
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        "rem ===========================================================",
        "rem  删除旧版 PyCharm 残留的 Windows 防火墙放行规则",
        "rem  请右键本文件 -> 以管理员身份运行",
        "rem  备份见 D:\\env-backup-20260917\\firewall-backup\\",
        "rem ===========================================================",
        "net session >nul 2>&1",
        "if %errorlevel% neq 0 (",
        "  echo [错误] 未获得管理员权限。请右键选择「以管理员身份运行」。",
        "  pause",
        "  exit /b 1",
        ")",
        "echo 正在删除旧规则: " + FW_RULE,
        'netsh advfirewall firewall delete rule name="' + FW_RULE + '"',
        "echo.",
        "echo 结果核对（应只剩 PyCharm 2026.2.2 相关规则）:",
        'netsh advfirewall firewall show rule name=all | findstr /I "pycharm"',
        "echo.",
        "pause",
    ]
    with open(cmd_path, "wb") as f:
        f.write(("\r\n".join(lines) + "\r\n").encode("gbk", "replace"))
    made.append(cmd_path)
    return made


if __name__ == "__main__":
    print("=== [1] 备份当前 PATH 与环境变量 ===")
    print("   ", backup())
    print()
    print("=== [2] 清理 PATH 与失效变量 ===")
    for m in clean_path_and_vars():
        print("   ", m)
    broadcast()
    print()
    print("=== [3] 复查 ===")
    verify()
    print()
    print("=== [4] 生成提权清理文件 ===")
    for p in make_admin_files():
        print("   ", p, f"({os.path.getsize(p)} 字节)")
    sys.exit(0)
