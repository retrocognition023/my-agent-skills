# My Agent Skills

个人 Agent Skill 与 MCP 连接器作品集。这里收录了 10 个自建 Agent Skill 和 1 个通用个人财经 MCP 服务器模板，覆盖**教学辅助**、**文件与图形工具**、**环境运维**、**跨端迁移**四类场景。

> 所有项目均已完成脱敏与普适化：不含任何个人路径、真实身份、真实账户或隐私数据；涉及的个人化学生画像已统一改写为「希望自主推进学习进度的本科大学生」。

## 目录结构

```
my-agent-skills/
├── README.md                     本文件（作品集首页）
├── CHANGELOG.md                  变更日志
├── VERSION                       版本信息
├── skills/                       10 个 Agent Skill
│   ├── tiered-question-gen/      分层出题
│   ├── review-material-gen/      复习材料生成
│   ├── error-attribution/        错题归因
│   ├── teaching-flow/            五阶段教学流程
│   ├── pdf-formula-inject/       PDF 公式注入
│   ├── research-figure/          学术配图（TikZ + Blender）
│   ├── tikz-figure-code/         TikZ 代码工程规范
│   ├── svg-creator/              手绘风格 SVG 流程图
│   ├── pycharm-python-env-repair-windows/  PyCharm/Python 环境修复
│   └── workbuddy-cross-device-migrate/    跨端任务迁移
└── mcp-finance/                  通用个人财经 MCP 服务器模板
    ├── README.md                 使用与配置说明
    ├── ARCHITECTURE.md           架构与实现说明
    ├── mcp-config.example.json   配置示例（占位符）
    ├── package.json              包信息
    └── src/                      server.js / browser.js / licaitong.js
```

## 技能一览

### 教学辅助（4 个，纯规则型）

这四个技能共享一套面向「希望自主推进学习进度的本科大学生」的教学方法论，彼此职责互补、互不重叠。

| 技能 | 版本 | 用途 |
|---|---|---|
| [tiered-question-gen](skills/tiered-question-gen/) | 1.2.0 | 按 Bloom 认知层级出三层难度题目（基础/中等/挑战），题目与答案分离，含范围闸门与强制自检 |
| [review-material-gen](skills/review-material-gen/) | 1.1.0 | 生成六种结构化复习材料（知识框架、关键词表、必背必会、易错易混、题型方法、学习建议） |
| [error-attribution](skills/error-attribution/) | 1.1.0 | 错题四分类归因（概念/方法/思维/计算）+ 环节定位 + 可执行改进策略 |
| [teaching-flow](skills/teaching-flow/) | 1.1.0 | 五阶段苏格拉底式教学流程，含新概念七件套、证明零跳步、交付前机器检查 |

### 文件与图形工具（4 个）

| 技能 | 版本 | 用途 |
|---|---|---|
| [pdf-formula-inject](skills/pdf-formula-inject/) | 1.0.0 | 在原 PDF 上叠加/替换 LaTeX 公式，matplotlib mathtext 600dpi 渲染，支持覆盖替换与批量注入 |
| [research-figure](skills/research-figure/) | 1.0.0 | 学术论文配图：TikZ 方法流程图 + Blender 3D 渲染，含模板与两阶段预览流程 |
| [tikz-figure-code](skills/tikz-figure-code/) | 1.0.0 | TikZ 代码工程规范：按构造布局（而非手填坐标）、8 条硬约束、自包含静态检查入口 |
| [svg-creator](skills/svg-creator/) | 1.0.0 | 手绘风格 SVG 流程图，支持宽高比预设、笔画扰动滤镜与箭头自检 |

### 环境与运维（2 个）

| 技能 | 版本 | 用途 |
|---|---|---|
| [pycharm-python-env-repair-windows](skills/pycharm-python-env-repair-windows/) | 1.0.0 | Windows 上 PyCharm/Python 环境疑难杂症诊断修复，含 14 个实测辅助脚本 |
| [workbuddy-cross-device-migrate](skills/workbuddy-cross-device-migrate/) | 1.0.0 | WorkBuddy 电脑→手机任务与产物迁移，三层数据体系诊断 + 看板建档 + 同步映射 |

### MCP 连接器（1 个）

| 项目 | 版本 | 用途 |
|---|---|---|
| [mcp-finance](mcp-finance/) | 0.1.0 | 通用个人财经 MCP 服务器模板：Playwright 登录态 + Cookie 持久化 + 本地缓存 + 标准 MCP 工具，域名/路径全部可配置 |

## 安装与使用

### Agent Skill

每个技能目录的核心是 `SKILL.md`（含 YAML frontmatter 的 name / version / description）。安装方式取决于你的 Agent 平台：

- **WorkBuddy**：把对应技能目录放入 `~/.workbuddy/skills/` 即可被识别。
- **其他兼容 Agent**：把技能目录放入平台约定的 skills 目录；确保 `SKILL.md` 位于目录根部。

带 `scripts/` 或 `references/` 的技能需一并保留整个目录（部分脚本有相对路径依赖）。其中 `tikz-figure-code` 的静态检查器已随技能打包在 `references/checkers/`，开箱即用，不依赖外部技能。

### mcp-finance

见 [mcp-finance/README.md](mcp-finance/README.md)。简要步骤：

1. 安装 Node.js ≥ 20.9 与依赖 `@modelcontextprotocol/sdk`、`zod`、`playwright`。
2. 复制 `mcp-config.example.json` 到你的 AI 客户端 MCP 配置，替换占位符。
3. 重启客户端，触发 `prepare_login` 扫码登录。

## 设计原则

- **单一职责**：技能之间职责互斥，通过 description 的触发/不触发条件明确边界。
- **确定性优先**：能量化检查的（版本号、JSON/脚本语法、依赖完整性、脱敏）一律用脚本验证，不靠人工判断。
- **隐私默认**：所有个人化信息在打包前统一脱敏；连接器不内置任何真实账户数据。
- **可移植**：路径、域名等环境相关参数通过环境变量或占位符配置，避免硬编码。

## 质量与验收

本次发布对全部 11 个项目执行了统一验收，结果全部通过：

- frontmatter 完整性（name / version / description）：10/10
- JSON 语法有效：11/11
- Python 脚本语法可编译：30/30
- evals 版本一致性：4/4
- 隐私脱敏残留：0
- tikz 检查器自包含：1/1
- mcp-finance 协议握手与工具注册：10 个工具全部成功

## License

各项目保留其原有许可证信息；未标注者默认为 MIT。本项目集合的整体说明见各子目录。
