"""
核查 JetBrains IDE 的授权状态：解码许可证文件、读取授权存储与相关配置。

只读操作，不修改任何内容。用于回答"教育包授权是否真的生效、Pro 功能是否解锁"。

用法:
    python audit_license.py <产品配置目录，如 %APPDATA%\\JetBrains\\PyCharm2026.2>
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys

INTERESTING_FIELDS = (
    "licenseeName",
    "licenseeEmail",
    "licenseId",
    "licenseRestriction",
    "licenseName",
    "productCode",
    "productName",
    "expirationDate",
    "expiryDate",
    "subscription",
    "isEvaluation",
    "isTrial",
    "fallbackDate",
    "autoProlongated",
    "licenseeType",
    "allProductCode",
    "metadata",
)


def try_b64_json(text: str) -> dict | None:
    """在文本里找出 base64 块并尝试解成 JSON。"""
    cleaned = re.sub(r"[\s\-]+", "", text)
    for pad in range(4):
        try:
            raw = base64.b64decode(cleaned + "=" * pad, validate=False)
        except Exception:
            continue
        i = raw.find(b"{")
        j = raw.rfind(b"}")
        if i >= 0 and j > i:
            try:
                return json.loads(raw[i:j + 1].decode("utf-8", "replace"))
            except Exception:
                continue
    return None


def summarise(obj: dict) -> None:
    for k in INTERESTING_FIELDS:
        if k in obj:
            v = obj[k]
            if isinstance(v, (dict, list)):
                v = json.dumps(v, ensure_ascii=False)[:200]
            print(f"      {k:22} = {v}")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cfg = argv[1]

    print("=" * 78)
    print("[A] 许可证文件 pycharm.key")
    print("=" * 78)
    key = os.path.join(cfg, "pycharm.key")
    if not os.path.exists(key):
        print("  未找到 pycharm.key（说明没有以'许可证文件'形式存储授权）")
    else:
        size = os.path.getsize(key)
        with open(key, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        print(f"  文件大小: {size} 字节")
        obj = try_b64_json(text)
        if obj:
            print("  解码出的许可证字段:")
            summarise(obj)
        else:
            print("  无法解出 JSON，原文前 400 字符:")
            print("   ", text[:400].replace("\n", " "))

    print()
    print("=" * 78)
    print("[B] 授权存储追踪 options/trace_license_storage.xml")
    print("=" * 78)
    p = os.path.join(cfg, "options", "trace_license_storage.xml")
    print("  存在" if os.path.exists(p) else "  不存在", p)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            print(f.read()[:1200])

    print()
    print("=" * 78)
    print("[C] 其他授权相关标记文件")
    print("=" * 78)
    for name in ("splash-subscription-mode.txt", "disabled_plugins.txt", "disabled_update.txt"):
        p = os.path.join(cfg, name)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                content = f.read().strip()
            print(f"  {name}: {content[:300] if content else '(空)'}")
        else:
            print(f"  {name}: (不存在)")

    print()
    print("=" * 78)
    print("[D] options/other.xml 中的授权/试用相关键")
    print("=" * 78)
    p = os.path.join(cfg, "options", "other.xml")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        hits = [ln.strip() for ln in text.splitlines()
                if re.search(r"licen|trial|pro\.|subscription|evaluat|pycharm\.pro", ln, re.I)]
        print("\n".join("  " + h for h in hits[:25]) if hits else "  无相关键")

    print()
    print("=" * 78)
    print("[E] IDE 日志中的授权相关记录")
    print("=" * 78)
    logdir = os.path.join(os.path.dirname(cfg).replace("Roaming", "Local"), "")
    # 兼容：日志在 LOCALAPPDATA\\JetBrains\\<product>\\log
    cand = []
    for base in (os.path.join(os.environ.get("LOCALAPPDATA", ""), "JetBrains"),
                 os.path.join(os.environ.get("APPDATA", ""), "JetBrains")):
        if os.path.isdir(base):
            for d in os.listdir(base):
                lg = os.path.join(base, d, "log", "idea.log")
                if os.path.exists(lg):
                    cand.append(lg)
    prod = os.path.basename(cfg.rstrip("\\/"))
    cand = [c for c in cand if prod in c] or cand
    for lg in cand:
        print(f"  日志: {lg}")
        with open(lg, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        hits = [ln.rstrip() for ln in lines
                if re.search(r"licen[cs]e|Educational|EDU\b|expir|trial|subscription", ln, re.I)]
        for h in hits[-25:]:
            print("   ", h[:230])
        if not hits:
            print("    (无匹配行)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
