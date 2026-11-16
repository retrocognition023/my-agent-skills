"""
回收站核验：给定若干「原始路径前缀」，统计回收站中属于它们的条目数与总体积。

用法:
    python recycle_report.py <盘符> <前缀1> [前缀2 ...]

示例:
    python recycle_report.py D D:/pythonProject/.venv1 D:/pythonProject/.venv

判定依据：回收站 $I 元数据里记录了被删项的原始完整路径与大小。
若某前缀下条目数 > 0，说明该路径的内容已进入回收站（可还原）。
"""

import glob
import os
import struct
import sys


def parse_i(path: str):
    """返回 (原始路径, 字节大小)。目录项大小为 0。"""
    try:
        with open(path, "rb") as f:
            d = f.read()
    except OSError:
        return None
    if len(d) < 32:
        return None
    size = struct.unpack_from("<q", d, 8)[0]
    plen = struct.unpack_from("<I", d, 24)[0]
    if plen <= 0 or plen > 4096:
        return None
    orig = d[28:28 + plen * 2].decode("utf-16-le", "replace").rstrip("\x00")
    return orig, size


def norm(p: str) -> str:
    return p.replace("\\", "/").lstrip("/").lower()


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    drive, prefixes = argv[1], argv[2:]
    root = f"{drive.upper()}:/$Recycle.Bin"
    sid_dirs = [d for d in glob.glob(os.path.join(root, "S-1-5-*")) if os.path.isdir(d)]

    entries = []
    for sd in sid_dirs:
        for p in glob.glob(os.path.join(sd, "$I*")):
            r = parse_i(p)
            if r:
                entries.append(r)

    print(f"盘符 {drive.upper()}: 回收站 $I 条目总数 = {len(entries)}\n")
    total = 0
    for pre in prefixes:
        npre = norm(pre)
        hits = [(o, s) for o, s in entries if norm(o).startswith(npre)]
        size = sum(max(s, 0) for _o, s in hits)
        n_files = sum(1 for _o, s in hits if s > 0)
        total += size
        status = "已进入回收站 ✔" if hits else "未在回收站中找到 ✘"
        print(f"前缀: {pre}")
        print(f"   条目数={len(hits)}  文件数={n_files}  累计体积={size/1024/1024:.2f} MB   {status}")
    print(f"\n合计体积: {total/1024/1024:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
