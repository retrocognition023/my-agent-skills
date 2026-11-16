#!/usr/bin/env python3
"""在已有 PDF 上插入 LaTeX 数学公式 / 数理符号（渲染为高分辨率透明图像叠加）。

用法见 SKILL.md。依赖：pymupdf(fitz)、matplotlib(mathtext)、PIL。
支持四种模式：
  1) 单条插入   --page N --at x,y --formula "..."
  2) 覆盖替换   --replace x0,y0,x1,y1 --formula "..."   (抹掉原区域再插入)
  3) 批注框     --note "中文说明"                        (公式下方附中文说明)
  4) 批量注入   --batch batch.json
退出码：0 成功；2 依赖缺失；3 全部公式渲染失败；4 参数错误。
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: 缺少 pymupdf，请先 pip install pymupdf", file=sys.stderr)
    sys.exit(2)

CJK_FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/PingFang.ttc",
]


def find_cjk_font():
    for p in CJK_FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def render_formula_png(latex_body, fontsize_pt, rgb01, dpi=600):
    """用 matplotlib mathtext 把公式渲染成透明 PNG。返回 (png路径, 宽px, 高px)。失败抛异常。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tex = f"${latex_body}$"
    # 先校验语法，提前给出可读错误
    parser = matplotlib.mathtext.MathTextParser("agg")
    parser.parse(tex, dpi=100)

    fig = plt.figure(figsize=(0.1, 0.1))
    fig.patch.set_alpha(0.0)
    fig.text(0.0, 0.0, tex, fontsize=fontsize_pt, color=rgb01)
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    fig.savefig(path, dpi=dpi, transparent=True,
                bbox_inches="tight", pad_inches=0.01)
    plt.close(fig)

    from PIL import Image
    with Image.open(path) as im:
        w, h = im.size
    if w == 0 or h == 0:
        raise ValueError("渲染结果为空")
    return path, w, h


def find_tectonic():
    """定位 tectonic：环境变量 > PATH > 本机已知安装路径。"""
    import shutil
    p = os.environ.get("TECTONIC_PATH")
    if p and os.path.exists(p):
        return p
    w = shutil.which("tectonic")
    if w:
        return w
    for cand in [
        "tectonic",  # tectonic 可执行文件；也可用环境变量 TECTONIC_BIN 指定绝对路径
        os.path.expanduser("~/.workbuddy/binaries/tectonic/tectonic.exe"),
    ]:
        if os.path.exists(cand):
            return cand
    return None


TECTONIC_TEMPLATE = r"""\documentclass[border=0.5pt]{standalone}
\usepackage{amsmath,amssymb}
\usepackage{xcolor}
\definecolor{fcolor}{RGB}{%d,%d,%d}
\begin{document}
\color{fcolor}
$%s$
\end{document}
"""


def render_tectonic_png(latex_body, c255, workdir, dpi=600):
    """用 tectonic 渲染公式（支持 aligned/cases/matrix 等多行环境）。
    返回 (png路径, 宽pt, 高pt)。"""
    import fitz

    tex = TECTONIC_TEMPLATE % (c255[0], c255[1], c255[2], latex_body)
    base = os.path.join(workdir, "f%d" % os.getpid())
    tex_path = base + ".tex"
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex)

    exe = find_tectonic()
    if not exe:
        raise RuntimeError("未找到 tectonic（安装于 ~/.workbuddy/binaries/tectonic/）")
    env = dict(os.environ)
    cache = os.path.join(os.path.dirname(exe), "cache")
    if os.path.isdir(cache):
        env["TECTONIC_CACHE_DIR"] = cache
    r = subprocess.run(
        [exe, "-X", "compile", tex_path, "-o", workdir],
        capture_output=True, text=True, timeout=600, env=env,
    )
    pdf_path = base + ".pdf"
    if r.returncode != 0 or not os.path.exists(pdf_path):
        msg = (r.stdout + r.stderr).strip()
        raise ValueError("tectonic 编译失败: " + msg[-400:])
    doc = fitz.open(pdf_path)
    page = doc[0]
    w_pt, h_pt = page.rect.width, page.rect.height
    pix = page.get_pixmap(dpi=dpi, alpha=True)
    png = base + ".png"
    pix.save(png)
    doc.close()
    for p in (tex_path, pdf_path):
        try:
            os.unlink(p)
        except OSError:
            pass
    return png, w_pt, h_pt


def anchor_rect(w_pt, h_pt, at_x, at_y, anchor, scale):
    """由 pt 尺寸与锚点计算插入矩形。anchor: lt/lm/lb/ct。"""
    w = w_pt * scale
    h = h_pt * scale
    x = at_x
    if anchor.startswith("c"):
        x = at_x - w / 2.0
    if anchor.endswith("t"):
        y_top = at_y
    elif anchor.endswith("m"):
        y_top = at_y - h / 2.0
    else:  # b
        y_top = at_y - h
    return fitz.Rect(x, y_top, x + w, y_top + h)


def parse_color(s):
    """'r,g,b' (0-255) 或颜色名 -> (r,g,b) 0-1 与 (r,g,b) 0-255。"""
    named = {
        "black": (0, 0, 0), "blue": (0, 0, 200), "red": (200, 0, 0),
        "green": (0, 128, 0), "darkblue": (0, 0, 139), "darkred": (139, 0, 0),
        "darkgreen": (0, 100, 0), "orange": (230, 120, 0), "purple": (128, 0, 128),
    }
    if s.lower() in named:
        c255 = named[s.lower()]
    else:
        parts = [float(v) for v in s.split(",")]
        if len(parts) != 3:
            raise ValueError(f"颜色格式应为 r,g,b 或颜色名，收到: {s}")
        c255 = tuple(max(0, min(255, int(v))) for v in parts)
    return tuple(v / 255.0 for v in c255), c255


def apply_replace(doc, page_no, rect_pts, keep_text=False):
    """在指定区域抹除原内容：文字层用 redact（真删除），并画白矩形兜底。"""
    page = doc[page_no]
    if not keep_text:
        page.add_redact_annot(rect_pts, fill=(1, 1, 1))
        page.apply_redactions()
    else:
        page.draw_rect(rect_pts, color=None, fill=(1, 1, 1))


def insert_note(page, rect, note_text, fontsize):
    """在公式矩形下方插入中文说明文字。用 PyMuPDF 内置 CJK 字体（自动子集，约 1KB）；
    不用系统 msyh.ttc——全量嵌入可达 20MB 且 subset_fonts 对 .ttc 静默失效。
    注意：insert_textbox 在高度不足时静默不渲染，必须按字符宽度精确估算高度。"""
    import math
    width = max(rect.width, 200.0)
    # 有效宽度：CJK 全角≈fontsize，ASCII≈0.55*fontsize
    eff = sum(fontsize if ord(c) > 0x2E80 else fontsize * 0.55 for c in note_text)
    n_lines = max(1, math.ceil(eff / (width - 4)))
    note_h = n_lines * fontsize * 1.5 + 6
    nrect = fitz.Rect(rect.x0, rect.y1 + 2, rect.x0 + width, rect.y1 + 2 + note_h)
    page.insert_textbox(nrect, note_text, fontsize=fontsize,
                        fontname="china-ss", color=(0.15, 0.15, 0.15))
    return nrect


def process_items(doc, items, default_color, default_size, scale, keep_text,
                  default_engine="mathtext", workdir="."):
    ok, fail = 0, []
    for it in items:
        page_no = it["page"] - 1
        if page_no < 0 or page_no >= doc.page_count:
            fail.append((it.get("formula", "?"), f"页码越界: {it['page']}"))
            continue
        try:
            rgb01, _c255 = parse_color(it.get("color", default_color))
            fsize = float(it.get("fontsize", default_size))
            engine = it.get("engine", default_engine)
            if engine == "tectonic":
                png, w_pt, h_pt = render_tectonic_png(it["formula"], _c255, workdir)
                rect = anchor_rect(w_pt, h_pt, it["at"][0], it["at"][1],
                                   it.get("anchor", "lt"), scale)
            else:
                png, w, h = render_formula_png(it["formula"], fsize, rgb01)
                rect = anchor_rect(w / 600.0 * 72.0, h / 600.0 * 72.0,
                                   it["at"][0], it["at"][1],
                                   it.get("anchor", "lt"), scale)
            page = doc[page_no]
            if it.get("replace_rect"):
                rx0, ry0, rx1, ry1 = it["replace_rect"]
                apply_replace(doc, page_no, fitz.Rect(rx0, ry0, rx1, ry1), keep_text)
            page.insert_image(rect, filename=png)
            if it.get("note"):
                insert_note(page, rect, it["note"], fsize)
            os.unlink(png)
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail.append((it.get("formula", "?"), str(e)))
    return ok, fail


def main():
    ap = argparse.ArgumentParser(description="在 PDF 上插入 LaTeX 公式（mathtext 渲染）")
    ap.add_argument("pdf", help="输入 PDF")
    ap.add_argument("-o", "--output", default=None, help="输出路径（默认 *_formula.pdf）")
    ap.add_argument("--page", type=int, default=None, help="页码（1-based）")
    ap.add_argument("--at", default=None, help="插入位置 x,y（pt，1-based 页内坐标）")
    ap.add_argument("--anchor", default="lt", choices=["lt", "lm", "lb", "ct"],
                    help="锚点：lt 左上 / lm 左中 / lb 左下 / ct 水平居中")
    ap.add_argument("--formula", default=None, help="LaTeX 公式（mathtext 语法，不带 $）")
    ap.add_argument("--fontsize", type=float, default=12.0, help="公式字号 pt（默认 12）")
    ap.add_argument("--color", default="black", help="颜色：r,g,b (0-255) 或颜色名")
    ap.add_argument("--scale", type=float, default=1.0, help="整体缩放")
    ap.add_argument("--note", default=None, help="公式下方的中文说明（批注框模式）")
    ap.add_argument("--replace", default=None,
                    help="替换模式：先抹掉区域 x0,y0,x1,y1 再插入公式")
    ap.add_argument("--keep-text", action="store_true",
                    help="替换时只盖白矩形不删除文字层（扫描件兜底）")
    ap.add_argument("--engine", default="mathtext", choices=["mathtext", "tectonic"],
                    help="渲染引擎：mathtext（快，单行公式）或 tectonic（完整 LaTeX，"
                         "支持 aligned/cases/matrix 多行环境，需已装 tectonic）")
    ap.add_argument("--batch", default=None, help="批量 JSON 文件路径")
    args = ap.parse_args()

    if not args.batch and not (args.formula and args.page and args.at):
        ap.error("需要 --batch，或同时给出 --page/--at/--formula")

    out = args.output or os.path.splitext(args.pdf)[0] + "_formula.pdf"
    doc = fitz.open(args.pdf)
    workdir = os.path.dirname(os.path.abspath(args.pdf)) or "."

    if args.batch:
        with open(args.batch, encoding="utf-8") as f:
            items = json.load(f)
        for it in items:
            it["page"] = int(it.get("page", 1))
            it["at"] = [float(v) for v in it["at"]]
            if it.get("replace_rect"):
                it["replace_rect"] = [float(v) for v in it["replace_rect"]]
        ok, fail = process_items(doc, items, args.color, args.fontsize,
                                 args.scale, args.keep_text, args.engine, workdir)
    else:
        at = [float(v) for v in args.at.split(",")]
        item = {"page": args.page, "at": at, "formula": args.formula,
                "fontsize": args.fontsize, "color": args.color,
                "anchor": args.anchor, "note": args.note,
                "engine": args.engine}
        if args.replace:
            item["replace_rect"] = [float(v) for v in args.replace.split(",")]
        ok, fail = process_items(doc, [item], args.color, args.fontsize,
                                 args.scale, args.keep_text, args.engine, workdir)

    # 中文字体全量嵌入可达 20MB+，保存前必须子集化（只保留用到的字形）
    try:
        doc.subset_fonts()
    except Exception as e:  # noqa: BLE001
        print(f"WARN: 字体子集化失败（输出可能偏大）: {e}", file=sys.stderr)

    doc.save(out, garbage=4, deflate=True)
    doc.close()

    print(f"OK: {ok} 条公式已注入 -> {out}")
    for formula, err in fail:
        print(f"FAIL: [{formula[:50]}] {err}", file=sys.stderr)
    if ok == 0 and fail:
        sys.exit(3)


if __name__ == "__main__":
    main()
