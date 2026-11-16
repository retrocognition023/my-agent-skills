"""
授权链路最终验证：
1) 日志中"付费插件/Pro 内容"加载情况（授权生效后才会加载）
2) 内部状态库 app-internal-state.db 中的授权相关记录
3) 配置目录中新增的授权状态键

只读。IDE 正在运行时也能安全读取（SQLite 以只读模式打开；若被锁则复制副本再读）。
"""

from __future__ import annotations

import os
import re
import shutil
import sqlite3
import sys
import tempfile

LOG = r"C://Users//<USER>//AppData//Local//JetBrains//<PRODUCT><VERSION>//log//idea.log"  # 按本机实际路径修改
CFG = r"C://Users//<USER>//AppData//Roaming//JetBrains//<PRODUCT><VERSION>"  # 按本机实际路径修改
DB = os.path.join(CFG, "app-internal-state.db")


def section(t: str) -> None:
    print()
    print("=" * 78)
    print(t)
    print("=" * 78)


def part1() -> None:
    section("[1] 日志：付费插件 / Pro 内容的加载情况")
    if not os.path.exists(LOG):
        print("  日志不存在"); return
    with open(LOG, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    pats = {
        "付费插件加载": r"paid plugin",
        "ultimate": r"ultimate",
        "pycharm.pro 内容": r"pycharm\.pro",
        "licen": r"licen[cs]e",
    }
    for name, pat in pats.items():
        hits = [ln.rstrip() for ln in lines if re.search(pat, ln, re.I)]
        print(f"\n  · {name}: 共 {len(hits)} 条")
        for h in hits[-6:]:
            print("     ", h[:175])


def part2() -> None:
    section("[2] 内部状态库 app-internal-state.db")
    if not os.path.exists(DB):
        print("  不存在"); return
    print(f"  文件大小: {os.path.getsize(DB)} 字节")
    src = DB
    tmp = None
    try:
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
    except Exception:
        try:
            tmp = os.path.join(tempfile.gettempdir(), "_state_copy.db")
            shutil.copy2(DB, tmp)
            con = sqlite3.connect(tmp)
        except Exception as e:
            print("  打开失败:", e); return
    try:
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print(f"  表数量: {len(tables)}")
        for t in tables:
            try:
                cur.execute(f'SELECT COUNT(*) FROM "{t}"')
                n = cur.fetchone()[0]
            except Exception:
                n = "?"
            if re.search(r"licen|state|setting|propert", t, re.I) or n not in (0, "?"):
                print(f"    表 {t}  行数={n}")
        print("\n  检索含 license/trial 字样的键值:")
        shown = 0
        for t in tables:
            try:
                cur.execute(f'SELECT * FROM "{t}" LIMIT 400')
                cols = [d[0] for d in cur.description]
                for row in cur.fetchall():
                    s = " | ".join(f"{c}={v}" for c, v in zip(cols, row) if v is not None)
                    if re.search(r"licen|trial|edu|subscription|pro", s, re.I):
                        print(f"    [{t}] {s[:230]}")
                        shown += 1
                        if shown > 25:
                            return
            except Exception:
                continue
        if shown == 0:
            print("    (未检索到相关记录)")
    finally:
        con.close()
        if tmp and os.path.exists(tmp):
            os.remove(tmp)


def part3() -> None:
    section("[3] 配置中与授权/试用相关的状态键（激活后新增）")
    for rel in ("options/other.xml", "options/trace_license_storage.xml",
                "splash-subscription-mode.txt", "disabled_plugins.txt"):
        p = os.path.join(CFG, *rel.split("/"))
        if not os.path.exists(p):
            print(f"  {rel}: (不存在)"); continue
        import datetime
        mt = datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M:%S")
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        print(f"\n  --- {rel}  (修改于 {mt}) ---")
        if rel.endswith(".xml"):
            hits = [ln.strip() for ln in text.splitlines()
                    if re.search(r"licen|trial|pro\.|subscription|evaluat", ln, re.I)]
            print("\n".join("    " + h[:170] for h in hits[:20]) if hits else "    (无相关键)")
        else:
            print("    ", (text.strip()[:200] or "(空)"))

    # 是否存在其它许可证落盘文件
    print("\n  --- 配置目录下所有 *.key 文件 ---")
    for dp, _dn, fn in os.walk(CFG):
        for f in fn:
            if f.lower().endswith((".key", ".key.old")):
                p = os.path.join(dp, f)
                print(f"    {os.path.relpath(p, CFG)}  {os.path.getsize(p)} 字节")


if __name__ == "__main__":
    part1(); part2(); part3()
    print()
    print("完成。")
    sys.exit(0)