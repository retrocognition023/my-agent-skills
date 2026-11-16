---
name: pdf-formula-inject
version: 1.0.0
description: |
  在已有 PDF 上以美观格式插入、修改 LaTeX 数学公式与数理符号。公式经 matplotlib
  mathtext 渲染为高分辨率（600dpi）透明图像，无损叠加到原 PDF 任意页任意位置；
  支持「覆盖替换」模式（抹掉原公式区域后插入新公式，实现"改公式"）、批注框模式
  （公式下方附中文说明）与批量注入。Use when the user asks: 在 PDF 上加公式、
  PDF 插入数学公式、修改 PDF 里的公式、PDF 公式标注、插入数理符号、
  formula inject、add math to pdf、edit formula in pdf。
---

# PDF 公式注入（pdf-formula-inject）

在**原 PDF 基础上**插入/替换 LaTeX 数学公式。公式不重排原内容，以透明高清图像叠加，观感与排版公式一致。

## 与其他技能分工

| 场景 | 用谁 |
|---|---|
| 高亮/下划线/删除线/矩形框/批注图标/书签 | `pdf-annotate` |
| **插入 LaTeX 公式、数理符号、改公式** | **本技能** |
| 创建新 PDF / 合并拆分 / 表单 | 官方 `pdf` skill |
| 从零写整份 LaTeX 文档再转 PDF | `latex` 类技能 |

两者可组合：先 `pdf-annotate` 高亮原公式位置，再本技能替换。

## 环境依赖

- `pymupdf`（必装，本机已装）
- `matplotlib`（必装，本机已装）— mathtext 引擎，**无需 LaTeX 发行版**
- `Pillow`（必装，本机已装）
- **可选**：`tectonic`（已装于 `~/.workbuddy/binaries/tectonic/tectonic.exe`，bash 别名 `tectonic` 可直接调用）— 启用 `--engine tectonic` 后支持 aligned/cases/matrix 等**多行环境**

## 双引擎选择

| | `--engine mathtext`（默认） | `--engine tectonic` |
|---|---|---|
| 速度 | 毫秒级 | 首次编译 15-30s/条（包已缓存后） |
| 能力 | 单行公式（LaTeX 数学子集） | **完整 LaTeX**：aligned/cases/matrix/任意宏包 |
| 依赖 | 无 | tectonic（联网下载宏包，缓存后离线可用） |
| 适用 | 批量注入几十条单行公式 | 分段函数、方程组推导、矩阵 |

batch JSON 每条可单独指定 `"engine": "tectonic"`。

## 快速开始

```bash
PY="python"   # 或用你环境中已安装依赖的 Python 解释器绝对路径

# 1. 单条插入：第 3 页 (100,300) 处插入高斯积分，深蓝 12pt
"$PY" scripts/inject_formula.py 讲义.pdf \
  --page 3 --at "100,300" \
  --formula "\int_{-\infty}^{\infty} e^{-x^2}\,dx=\sqrt{\pi}" \
  --fontsize 12 --color darkblue -o 讲义_加公式.pdf

# 2. 覆盖替换：把原公式区域 (150,420,320,445) 抹掉，写上新公式
"$PY" scripts/inject_formula.py 讲义.pdf \
  --page 5 --replace "150,420,320,445" --at "150,420" \
  --formula "\frac{d}{dx}\left[\ln|x|\right]=\frac{1}{x}" -o 讲义_改.pdf

# 3. 批注框模式：公式 + 中文说明
"$PY" scripts/inject_formula.py 讲义.pdf \
  --page 2 --at "300,150" --formula "A=UDV^{T}" \
  --note "SVD 分解：U、V 正交，D 对角" -o 讲义_批注.pdf

# 4. 批量注入（推荐，一次写全所有公式）
"$PY" scripts/inject_formula.py 讲义.pdf --batch batch.json -o 讲义_成品.pdf
```

batch.json 格式：

```json
[
  {"page": 3, "at": [100, 300], "formula": "E=mc^2", "fontsize": 12, "color": "black"},
  {"page": 5, "at": [150, 420], "formula": "\frac{d}{dx}\left[e^x\right]=e^x", "replace_rect": [150, 420, 320, 445], "note": "修正后的公式"},
  {"page": 7, "at": [80, 500], "formula": "\binom{n}{k}=\frac{n!}{k!(n-k)!}", "anchor": "lt"}
]
```

## 参数

| 参数 | 说明 |
|---|---|
| `--page N` | 页码，1-based |
| `--at "x,y"` | 插入位置（pt，PDF 坐标，左上角为原点向下） |
| `--anchor` | 锚点语义：`lt` 左上（默认）/ `lm` 左中 / `lb` 左下 / `ct` 顶边水平居中 |
| `--formula` | LaTeX 数学子集（mathtext 语法，**不带** `$`） |
| `--fontsize` | 公式字号 pt（默认 12，与正文匹配） |
| `--color` | `r,g,b`（0-255）或颜色名（black/blue/darkred/darkgreen/orange/purple 等） |
| `--scale` | 整体缩放（默认 1.0） |
| `--note` | 公式下方中文说明（微软雅黑，自动找 CJK 字体） |
| `--replace` | 替换模式：`x0,y0,x1,y1` 区域先抹除再插入 |
| `--keep-text` | 替换时只盖白矩形不删文字层（扫描件用） |
| `--batch` | JSON 批量文件 |

## mathtext 支持范围（重要）

**支持**：上下标、分式 `\frac{}{}`、根号 `\sqrt{}`/`\sqrt[]{}`、积分 `\int`/`\oint`（含上下限）、求和 `\sum`、连乘 `\prod`、极限 `\lim`、希腊字母（`\alpha \beta \Gamma \nabla \partial ...`）、关系符（`\leq \geq \neq \approx \equiv \sim \propto`）、箭头（`\rightarrow \Rightarrow \leftrightarrow \mapsto`）、装饰（`\hat \bar \vec \tilde \dot \ddot \widehat \overline`）、定界符自适应（`\left( \right)`）、`\binom`、`\genfrac`、矩阵片段 `\binom` 级、集合（`\in \subset \cup \cap \emptyset \infty`）、范数 `\|`、省略号 `\cdots \ldots \vdots`、手写体 `\mathbb{}`（黑板粗体）`\mathcal{}` `\mathbf{}` `\boldsymbol{}`。

**多行环境**（`\begin{aligned}`、`\begin{cases}`、矩阵）mathtext 不支持——用 `--engine tectonic` 直接渲染（推荐），或将多行拆成多条 mathtext 注入（每行一条，`--at` 上下错开 1.6×字号 pt）。

tectonic 引擎用法：

```bash
"$PY" scripts/inject_formula.py 讲义.pdf --engine tectonic \
  --page 5 --at "150,420" \
  --formula "f(x)=\begin{cases} x^{2}, & x\geq 0 \\ -x, & x<0 \end{cases}" \
  -o 讲义_加公式.pdf
```

**坐标获取**：用 PyMuPDF 渲染页面为 PNG 后目检定位，或 `page.search_for("原文片段")` 拿原文字的精确 Rect，再据此计算 `--at` 与 `--replace`。

## 「修改原公式」标准工作流

1. `page.search_for("原公式文本")` 或渲染 PNG 目检，确定原公式 Rect
2. `--replace x0,y0,x1,y1 --at x0,y0`：redact 抹除文字层 + 白矩形兜底 + 新公式原位插入
3. 扫描件（无文字层）加 `--keep-text`（redact 无效，仅白矩形覆盖）
4. 回读渲染新 PNG 目检：位置、大小、遮挡是否合格

## 限制与注意

- mathtext 引擎 600dpi 渲染；tectonic 引擎 standalone 裁剪 + alpha 通道透明渲染
- 中文 note 用 PyMuPDF 内置 `china-ss`（宋体，自动子集约 1KB）；**勿用系统 msyh.ttc**（全量嵌入 20MB 且 subset_fonts 对 .ttc 静默失效）
- PDF 坐标系 y 轴向下；`--at` 是公式锚点，先小范围试插再微调
- 修改不可逆地写入输出文件；**一律另存新文件**，不覆盖原件
- 加密 PDF 先用官方 pdf skill 解密
- tectonic 首次编译新宏包需联网；缓存于 `~/.workbuddy/binaries/tectonic/cache/`，之后离线可用
