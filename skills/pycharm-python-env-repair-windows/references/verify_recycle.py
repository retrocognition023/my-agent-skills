"""
核对：本次删除的 jupyter-plugin 内容是否 100% 完整进入了回收站。

做法：解析 C 盘回收站的 $I 元数据（每个被删项一份，内含原始完整路径），
      与删除前建立的备份副本（D:\\env-backup-20260917\\plugins\\jupyter-plugin）做集合比对。
      两边集合完全一致 => 没有任何文件被永久删除。

注意：本机 Git Bash 会对 heredoc 中的反斜杠做路径转换，因此这里用脚本文件执行，
      并在比较前统一把反斜杠归一化为正斜杠，避免转义干扰。
"""

import glob
import os
import struct
import sys

SID = "S-1-5-21-3604669885-2686114270-3325209745-1001"
RECYCLE_ROOT = "C:/$Recycle.Bin/" + SID
TARGET_PREFIX = "C:/Users/<USER>/AppData/Roaming/JetBrains/<PRODUCT><VERSION>/plugins/<PLUGIN>"  # 按本机实际路径修改
BACKUP_DIR = "D:/env-backup-20260917/plugins/jupyter-plugin"


def norm(p: str) -> str:
    """统一分隔符并去掉长路径前缀，方便集合比较。"""
    p = p.replace("\\", "/")
    return p.lstrip("/")


def parse_i_original_path(path: str) -> str | None:
    """解析回收站 $I 文件，返回被删项的原始完整路径。"""
    try:
        with open(path, "rb") as f:
            d = f.read()
    except OSError:
        return None
    if len(d) < 32:
        return None
    plen = struct.unpack_from("<I", d, 24)[0]
    if plen <= 0 or plen > 4096:
        return None
    return d[28:28 + plen * 2].decode("utf-16-le", "replace").rstrip("\x00")


def main() -> int:
    bin_paths = []
    for p in glob.glob(os.path.join(RECYCLE_ROOT, "$I*")):
        s = parse_i_original_path(p)
        if s:
            bin_paths.append(s)

    pre = norm(TARGET_PREFIX).lower()
    matched = [x for x in bin_paths if norm(x).lower().startswith(pre)]
    print(f"回收站 $I 条目总数            : {len(bin_paths)}")
    print(f"其中属于 jupyter-plugin 的     : {len(matched)}")

    bin_rel = set()
    for x in matched:
        rel = norm(x)[len(pre):].strip("/")
        if rel:
            bin_rel.add(rel.lower())

    bk_files = set()
    for dp, _dn, fn in os.walk(BACKUP_DIR):
        for f in fn:
            rel = os.path.relpath(os.path.join(dp, f), BACKUP_DIR)
            bk_files.add(norm(rel).lower())

    print(f"回收站中的文件级条目           : {len(bin_rel)}")
    print(f"备份副本中的文件数             : {len(bk_files)}")
    print()

    only_bk = sorted(bk_files - bin_rel)
    only_bin = sorted(bin_rel - bk_files)
    print(f"【备份有 / 回收站无】= {len(only_bk)}  （>0 说明有文件被永久删除，需警惕）")
    for x in only_bk[:20]:
        print("    -", x)
    print(f"【回收站有 / 备份无】= {len(only_bin)}")
    for x in only_bin[:20]:
        print("    +", x)

    ok = (len(only_bk) == 0 and len(bk_files) > 0)
    print()
    print("结论:", "全部内容均已进入回收站，可随时还原 ✔" if ok else "存在差异，需人工复核 ✘")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
