"""
前置检查：确认能否修改 HKLM（注册表类残留）与防火墙规则，并读取 PATH 现状。

只读为主，仅做一次"临时键创建+删除"来探测 HKLM 写权限（无副作用）。
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import winreg

B = chr(92)


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def probe_hklm_write() -> str:
    """尝试在 HKLM\\Software\\Classes 下创建并立即删除一个临时键。"""
    path = "Software" + B + "Classes" + B + "_wb_write_probe_20260917"
    try:
        k = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, path)
        winreg.CloseKey(k)
        try:
            winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, path)
            return "可写（临时键已创建并删除）"
        except Exception as e:
            return f"可创建但删除失败: {type(e).__name__}"
    except PermissionError:
        return "无权限（PermissionError）"
    except Exception as e:
        return f"{type(e).__name__}: {e}"


def firewall_rules() -> list[str]:
    """列出规则名中含 pycharm 的防火墙规则。"""
    try:
        out = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
            capture_output=True, text=True, encoding="gbk", errors="replace", timeout=120,
        ).stdout
    except Exception as e:
        return [f"<netsh 执行失败: {e}>"]
    lines = out.splitlines()
    names = []
    cur = None
    for ln in lines:
        s = ln.strip()
        if s.startswith("规则名称:") or s.startswith("Rule Name:"):
            cur = s.split(":", 1)[1].strip()
        elif s.startswith("规则名:") and cur is None:
            cur = s.split(":", 1)[1].strip()
        if cur and "pycharm" in cur.lower():
            if cur not in names:
                names.append(cur)
    if not names:
        for ln in lines:
            s = ln.strip()
            if "pycharm" in s.lower():
                names.append(s[:200])
    return names


def path_state() -> None:
    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment")
    val, typ = winreg.QueryValueEx(k, "Path")
    print(f"  用户 PATH 类型: {'REG_EXPAND_SZ' if typ == winreg.REG_EXPAND_SZ else 'REG_SZ'} ({typ})")
    print(f"  条目数: {len(val.split(';'))}")
    hits = [p for p in val.split(";") if "ycharm" in p or "Pycharm" in p]
    print(f"  已含 PyCharm 项: {hits or '(无)'}")
    print(f"  值长度: {len(val)} 字符")
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_path_backup.txt"), "w",
              encoding="utf-8") as f:
        f.write(val)
    print("  已备份当前用户 PATH 到 tools/_path_backup.txt")


if __name__ == "__main__":
    print("=== 权限 ===")
    print("  IsUserAnAdmin():", is_admin())
    print("  HKLM\\Software\\Classes 写权限:", probe_hklm_write())
    print()
    print("=== 目标注册表键现状 ===")
    p = "Software" + B + "Classes" + B + "PyCharmCE2024.2"
    try:
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, p)
        print("  HKLM", p, "-> 存在")
        winreg.CloseKey(k)
    except FileNotFoundError:
        print("  HKLM", p, "-> 不存在（可能已被清理）")
    except Exception as e:
        print("  HKLM", p, "->", type(e).__name__)
    print()
    print("=== 防火墙规则（名称含 pycharm）===")
    rules = firewall_rules()
    for r in rules:
        print("  -", r)
    if not rules:
        print("  (未找到)")
    print()
    print("=== 用户 PATH 现状 ===")
    path_state()
    sys.exit(0)
