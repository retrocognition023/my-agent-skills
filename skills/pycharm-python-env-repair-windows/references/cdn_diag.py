"""
CDN 状态诊断：判断 JetBrains 下载地址是"地址失效"还是"本机/代理被限流"。

对照设计：同时探测 ①目标安装包 ②同目录下的 .sha256 小文件 ③备用 CDN 域名 ④另一个版本，
以便区分是单个文件的问题、整个域名的问题，还是只有大文件被限。
"""

import urllib.error
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}

TARGETS = [
    ("主地址 大文件 HEAD", "https://download.jetbrains.com/python/pycharm-2026.2.2.exe", "HEAD"),
    ("主地址 大文件 GET", "https://download.jetbrains.com/python/pycharm-2026.2.2.exe", "GET"),
    ("同目录 .sha256", "https://download.jetbrains.com/python/pycharm-2026.2.2.exe.sha256", "GET"),
    ("备用域名 download-cdn", "https://download-cdn.jetbrains.com/python/pycharm-2026.2.2.exe", "HEAD"),
    ("另一版本 2026.1.5", "https://download.jetbrains.com/python/pycharm-2026.1.5.exe", "HEAD"),
    ("silent.config 小文件", "https://download.jetbrains.com/python/silent.config", "GET"),
]

for name, url, method in TARGETS:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method=method, headers=UA), timeout=25) as r:
            clen = r.headers.get("Content-Length")
            got = len(r.read(4096)) if method == "GET" else 0
            print(f"  {name:26} -> {r.status}  Content-Length={clen}  read={got}")
    except urllib.error.HTTPError as e:
        print(f"  {name:26} -> HTTP {e.code} {e.reason}")
    except Exception as e:
        print(f"  {name:26} -> {type(e).__name__}: {str(e)[:70]}")
