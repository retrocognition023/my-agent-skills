"""
Windows 环境作业小工具（本次 PyCharm/Python 环境整改专用）

用法：
    python win_env_tools.py procs [关键字...]     # 列出含关键字的进程（含完整路径）
    python win_env_tools.py recycle <路径> [...]  # 将路径移入回收站（绝不永久删除）

设计说明：
- procs 走 Win32 CreateToolhelp32Snapshot，不依赖 tasklist / wmic（本机沙箱下这两个无输出）。
- recycle 走 Shell SHFileOperationW + FOF_ALLOWUNDO，等价于资源管理器里「删除到回收站」，
  可在回收站中还原；这是本项目「删除一律走回收站，不用 rm -rf」硬约束的实现方式。
"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

# ---------------------------------------------------------------- 进程枚举

TH32CS_SNAPPROCESS = 0x00000002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MAX_PATH = 260


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * MAX_PATH),
    ]


def _process_image_path(pid: int) -> str:
    """取进程可执行文件完整路径；权限不足时返回空串。"""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        k32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
        return ""
    finally:
        k32.CloseHandle(h)


def list_processes(keywords: list[str]) -> int:
    """打印名字或路径命中任一关键字的进程。返回命中数量。"""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]

    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == wintypes.HANDLE(-1).value:
        print("CreateToolhelp32Snapshot 失败:", ctypes.get_last_error())
        return -1

    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    hits = 0
    try:
        ok = k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            name = entry.szExeFile
            path = ""
            low = name.lower()
            if any(k.lower() in low for k in keywords):
                path = _process_image_path(entry.th32ProcessID)
                hits += 1
            elif keywords == []:
                path = _process_image_path(entry.th32ProcessID)
            if any(k.lower() in (name + " " + path).lower() for k in keywords):
                print(f"{entry.th32ProcessID:>8}  {name:<28} {path}")
            ok = k32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snap)
    return hits


# ---------------------------------------------------------------- 回收站删除

FO_DELETE = 0x0003
FOF_SILENT = 0x0004
FOF_NOCONFIRMATION = 0x0010
FOF_ALLOWUNDO = 0x0040
FOF_NOERRORUI = 0x0400


class SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", ctypes.c_uint16),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


def recycle(paths: list[str]) -> int:
    """
    将给定路径（文件或目录，可多个）移入回收站。

    Args:
        paths: 绝对路径列表。

    Returns:
        进程退出码，0 表示成功。

    Raises:
        ValueError: 路径不存在或不是绝对路径。
    """
    normalized: list[str] = []
    for p in paths:
        ap = os.path.abspath(p)
        if not os.path.exists(ap):
            raise ValueError(f"路径不存在: {ap}")
        normalized.append(ap)

    # SHFileOperation 要求多字符串以「双 NULL」结尾
    from_str = "\0".join(normalized) + "\0\0"

    op = SHFILEOPSTRUCTW()
    op.hwnd = None
    op.wFunc = FO_DELETE
    op.pFrom = from_str
    op.pTo = None
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI

    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.SHFileOperationW.argtypes = [ctypes.POINTER(SHFILEOPSTRUCTW)]
    shell32.SHFileOperationW.restype = ctypes.c_int
    rc = shell32.SHFileOperationW(ctypes.byref(op))
    if op.fAnyOperationsAborted:
        print("警告：操作被中止（可能有文件被占用）")
    return rc


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "procs":
        kws = argv[2:] or ["pycharm", "java", "python"]
        n = list_processes(kws)
        print(f"--- 命中 {n} 个进程 ---")
        return 0
    if cmd == "recycle":
        if len(argv) < 3:
            print("用法: recycle <路径> [路径...]")
            return 2
        rc = recycle(argv[2:])
        print(f"SHFileOperationW 返回码: {rc}（0 = 成功，已入回收站）")
        for p in argv[2:]:
            print(f"  仍存在: {os.path.exists(os.path.abspath(p))}  {p}")
        return 0
    print("未知子命令:", cmd)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
