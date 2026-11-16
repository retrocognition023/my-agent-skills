"""
防火墙规则核验（改用注册表数据源，避免 netsh 输出编码导致的误判）。

数据源：HKLM\\SYSTEM\\CurrentControlSet\\Services\\SharedAccess\\Parameters\\FirewallPolicy\\FirewallRules
每个值为一条规则，形如：
  v2.10|Action=Allow|Active=TRUE|Dir=In|Protocol=6|Profile=Public|App=<exe路径>|Name=<规则名>|Desc=<描述>|...

做法：枚举全部规则值，解析 Name= 与 App=，筛出含 pycharm 的规则，区分新版/旧版。
另附 netsh 文本对照（自动尝试多种编码，避免乱码误判）。
"""

from __future__ import annotations

import re
import subprocess
import sys
import winreg

B = chr(92)
FW_KEY = ("SYSTEM" + B + "CurrentControlSet" + B + "Services" + B + "SharedAccess"
          + B + "Parameters" + B + "FirewallPolicy" + B + "FirewallRules")


def parse_rule(v: str) -> dict:
    d = {}
    for part in v.split("|"):
        if "=" in part:
            k, _, val = part.partition("=")
            d[k.strip()] = val.strip()
    return d


def from_registry() -> tuple[list[dict], list[dict], int]:
    k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, FW_KEY)
    old, new, total = [], [], 0
    i = 0
    while True:
        try:
            name, v, _t = winreg.EnumValue(k, i)
            i += 1
            total += 1
        except OSError:
            break
        s = str(v)
        if "pycharm" not in (name + s).lower():
            continue
        d = parse_rule(s)
        d["_regname"] = name
        rn = (d.get("Name", "") + " " + name).lower()
        if "community edition 2024.2.3" in rn or "community edition 2024.2.3" in s.lower():
            old.append(d)
        else:
            new.append(d)
    winreg.CloseKey(k)
    return old, new, total


def decode_any(raw: bytes) -> str:
    for enc in ("utf-8", "gbk", "cp936", "utf-16-le"):
        try:
            t = raw.decode(enc)
        except Exception:
            continue
        if "规则名称" in t or "Rule Name" in t:
            return t
    return raw.decode("gbk", "replace")


def netsh_names() -> list[str]:
    r = subprocess.run(["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
                       capture_output=True)
    txt = decode_any(r.stdout or b"")
    names = []
    for m in re.finditer(r"(?:规则名称|Rule Name)\s*:\s*(.+)", txt):
        nm = m.group(1).strip()
        if nm and nm not in names:
            names.append(nm)
    return names


if __name__ == "__main__":
    print("=" * 76)
    print("[注册表数据源] FirewallRules")
    print("=" * 76)
    old, new, total = from_registry()
    print(f"  规则总数: {total}")
    print(f"  含 pycharm 且属于【旧版 2024.2.3】: {len(old)} 条")
    for d in old:
        print(f"     ❌ Name={d.get('Name')}  Protocol={d.get('Protocol')} Dir={d.get('Dir')} App={d.get('App')}")
    print(f"  含 pycharm 且属于【新版 2026.2.2】: {len(new)} 条")
    for d in new:
        print(f"     ✅ Name={d.get('Name')}  Protocol={d.get('Protocol')} Dir={d.get('Dir')} App={d.get('App')}")

    print()
    print("=" * 76)
    print("[netsh 文本对照]")
    print("=" * 76)
    names = netsh_names()
    py = [n for n in names if "pycharm" in n.lower()]
    print(f"  规则总数（netsh）: {len(names)}")
    print(f"  含 pycharm 的规则名: {py if py else '(无)'}")

    print()
    ok = (len(old) == 0 and len([n for n in py if "2024.2.3" in n]) == 0)
    print("=" * 76)
    print("结论：旧版防火墙规则", "已彻底清除 ✅" if ok else "仍有残留 ❌")
    print("=" * 76)
    sys.exit(0 if ok else 1)
