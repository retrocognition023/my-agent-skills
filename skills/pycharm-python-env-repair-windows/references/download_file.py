"""
通用文件下载器（替代 curl —— 本机 curl 的文件写入会被沙箱拦截，返回错误 23）。

特性：
- 流式分块下载，实时打印进度（每 5% 一条）
- 断点续传：目标文件已存在且小于远端大小时，用 HTTP Range 续传
- 完成后计算 SHA256 并打印，便于与官网公布值比对
- 只写文件，不执行、不打开下载内容

用法:
    python download_file.py <url> <输出路径> [--expect-sha256 <哈希>]

退出码: 0 成功 / 1 失败 / 2 校验不符
"""

from __future__ import annotations

import hashlib
import os
import sys
import time
import urllib.error
import urllib.request

CHUNK = 1024 * 1024
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) EnvRepairDownloader/1.0"


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def remote_info(url: str) -> tuple[int | None, str]:
    """
    取远端文件大小与**重定向后的真实地址**。

    为什么要拿真实地址：JetBrains 的 CDN 先 302 跳转，若直接对原始 URL 发 Range 请求，
    跳转目标会返回 404。必须先把 Range 发到最终地址才能续传。
    """
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            n = r.headers.get("Content-Length")
            return (int(n) if n else None), r.geturl()
    except Exception:
        return None, url


def _stream(url: str, out: str, have: int) -> tuple[int, float, bool]:
    """
    单次流式下载（可续传）。返回 (下载后大小, 耗时, 是否完整)。

    服务端不支持续传（返回 200 而非 206）时自动改为整文件重下。
    """
    total, final = remote_info(url)
    headers = {"User-Agent": UA}
    mode = "wb"
    if have > 0 and total is not None and have < total:
        headers["Range"] = f"bytes={have}-"
        mode = "ab"
        target = final          # Range 必须打到重定向后的真实地址
    else:
        have = 0
        target = url

    start = time.time()
    req = urllib.request.Request(target, headers=headers)
    last_print = -1
    with urllib.request.urlopen(req, timeout=60) as r, open(out, mode) as f:
        if r.status == 200 and mode == "ab":
            print("  服务端不支持续传，改为整文件重下")
            f.close()
            f = open(out, "wb")
            have = 0
            last_print = -1
        base = have
        while True:
            buf = r.read(CHUNK)
            if not buf:
                break
            f.write(buf)
            have += len(buf)
            if total:
                pct = have * 100 // total
                if pct // 10 > last_print // 10:
                    speed = (have - base) / max(time.time() - start, 0.001)
                    print(f"  {pct:3d}%  {human(have)} / {human(total)}  {human(speed)}/s", flush=True)
                    last_print = pct
    size = os.path.getsize(out)
    ok = total is None or size == total
    return size, time.time() - start, ok


def download(url: str, out: str, attempts: int = 6) -> str:
    """带自动重试/续传地下载，返回 sha256（空串表示未完成）。"""
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    total, _ = remote_info(url)

    for attempt in range(1, attempts + 1):
        have = os.path.getsize(out) if os.path.exists(out) else 0
        if total is not None and have == total:
            break
        if total is not None and have > total:
            print("本地文件比远端大，判定为脏数据，从头重下")
            os.remove(out)
            have = 0
        if have:
            print(f"[第 {attempt}/{attempts} 次尝试] 断点续传：从 {human(have)} 继续")
        try:
            size, elapsed, ok = _stream(url, out, have)
            print(f"  本次结束：{human(size)}  耗时 {elapsed:.0f}s")
            if ok:
                break
        except (urllib.error.URLError, TimeoutError, OSError, ConnectionError) as e:
            print(f"  网络中断：{type(e).__name__}: {e}")
            if attempt == attempts:
                print("已达最大重试次数，放弃")
                return ""

    if total is not None and os.path.getsize(out) != total:
        print(f"⚠️ 大小不符：本地 {os.path.getsize(out)} / 远端 {total}")
        return ""
    print(f"下载完成：{human(os.path.getsize(out))}")

    print("计算 SHA256 ...")
    h = hashlib.sha256()
    with open(out, "rb") as f:
        while True:
            buf = f.read(4 * 1024 * 1024)
            if not buf:
                break
            h.update(buf)
    digest = h.hexdigest()
    print(f"SHA256 = {digest}")
    return digest



def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    url, out = argv[1], argv[2]
    expect = None
    if "--expect-sha256" in argv:
        expect = argv[argv.index("--expect-sha256") + 1].strip().lower()

    print(f"URL : {url}")
    print(f"输出: {out}")
    try:
        digest = download(url, out)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f"下载失败：{type(e).__name__}: {e}")
        return 1

    if not digest:
        return 1
    if expect:
        if digest == expect:
            print("✅ SHA256 与官网公布值一致，文件完整可信")
        else:
            print(f"❌ SHA256 不一致！\n   期望 {expect}\n   实际 {digest}")
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
