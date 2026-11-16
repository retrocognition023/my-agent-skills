"""
收尾清理：处理因"路径超过 Windows 260 字符上限"而无法进回收站的残留。

策略（全程非破坏性）：
  1. 找出超长路径的文件，用长路径前缀重命名为短名（路径变短后即可正常回收）
  2. 逐个把顶层条目移入回收站
  3. 最后用 os.rmdir 清掉残留的空目录壳（回收站不接纳空目录）

用法:
    python finish_cleanup.py <目标目录1> [目标目录2 ...]
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from win_env_tools import recycle  # noqa: E402

MAXLEN = 250
PREFIX = "\\\\?\\"


def to_long(path: str) -> str:
    """给绝对路径加长路径前缀。"""
    ap = os.path.abspath(path)
    if not ap.startswith(PREFIX):
        ap = PREFIX + ap
    return ap


def shorten_long_paths(root: str) -> int:
    """把 root 下超长路径的文件重命名为短名。返回处理数量。"""
    fixed = 0
    idx = 0
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            full = os.path.join(dp, f)
            if len(os.path.abspath(full)) <= MAXLEN:
                continue
            idx += 1
            newname = f"_sh{idx}.tmp"
            newfull = os.path.join(dp, newname)
            try:
                os.rename(to_long(full), to_long(newfull))
                fixed += 1
            except OSError as e:
                print(f"      重命名失败: {type(e).__name__} {e}")
    return fixed


def remove_empty_dirs(root: str) -> int:
    """自底向上删除空目录。返回删除数量。"""
    removed = 0
    for dp, dn, fn in os.walk(root, topdown=False):
        for d in dn:
            p = os.path.join(dp, d)
            try:
                os.rmdir(to_long(p))
                removed += 1
            except OSError:
                pass
    return removed


def process(target: str) -> None:
    print(f"\n>>> 处理: {target}")
    if not os.path.exists(target):
        print("    已不存在，跳过")
        return

    n = shorten_long_paths(target)
    if n:
        print(f"    已缩短 {n} 个超长路径文件")

    top = sorted(os.listdir(target))
    for name in top:
        p = os.path.join(target, name)
        try:
            rc = recycle([p])
            print(f"    回收 {name:20} -> 返回码 {rc}  仍存在={os.path.exists(p)}")
        except Exception as e:
            print(f"    回收 {name:20} -> 失败 {type(e).__name__}: {e}")

    # 处理仍存在的部分：再缩短一次并回收
    for name in sorted(os.listdir(target)):
        p = os.path.join(target, name)
        if os.path.exists(p) and os.path.isdir(p):
            n2 = shorten_long_paths(p)
            if n2:
                print(f"    二次缩短 {n2} 个超长路径文件于 {name}")
                try:
                    recycle([p])
                    print(f"    二次回收 {name} -> 仍存在={os.path.exists(p)}")
                except Exception as e:
                    print(f"    二次回收 {name} 失败: {e}")

    left = remove_empty_dirs(target)
    print(f"    清理空目录 {left} 个")
    try:
        if not os.listdir(target):
            os.rmdir(to_long(target))
            print("    顶层目录已空，已移除")
    except OSError as e:
        print(f"    顶层目录仍非空或移除失败: {e}")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    for t in argv[1:]:
        process(t)
    print("\n完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
