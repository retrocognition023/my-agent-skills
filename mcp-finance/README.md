# Personal Finance MCP Server

一个通用的个人财经 MCP（Model Context Protocol）服务器参考实现：通过 Playwright 维持登录态，读取某一财经数据源的持仓、收益与交易数据，并以标准 MCP 工具暴露给 AI 客户端（WorkBuddy / ChatGPT / Claude 等）。

> **定位**：本项目是一个**可复用的架构模板**。默认示例对接某网页版基金平台，但登录、浏览器管理、Cookie 持久化、数据缓存、工具注册的方式是通用的。接其他数据源时，只需替换 API 封装层的接口路径与字段解析（详见「接入其他数据源」）。

## 特性

- **传输**：stdio（本地优先，各 AI 客户端通用）
- **运行**：Node.js ≥ 20.9
- **依赖**：`@modelcontextprotocol/sdk`、`zod`、`playwright`
- **登录态**：Playwright persistent context + Cookie 持久化到用户目录
- **数据缓存**：本地 JSON，自动创建
- **隐私优先**：所有路径、域名、登录页均可通过环境变量配置；不内置任何个人身份或真实账户数据

## 提供的工具

### 登录与连接
- `login_status` — 查询当前会话是否已登录
- `prepare_login` — 启动 Chromium 打开登录页，返回二维码截图
- `wait_for_login` — 轮询等待扫码登录完成

### 数据查询（示例数据源）
- `get_positions` — 获取持仓列表
- `get_total_profit` — 获取总资产收益分析
- `get_day_profit` — 获取当日各基金收益
- `get_fund_detail` — 获取基金产品详情

### 本地组合管理
- `list_local_transactions` — 列出本地记录的交易
- `add_local_transaction` — 手动录入交易

## 配置

所有配置项均为环境变量，**无硬编码个人路径**：

| 环境变量 | 说明 | 默认值 |
|---|---|---|
| `NODE_WORKSPACE_DIR` | 依赖解析目录（node_modules 所在目录） | 项目内 `./node_modules` |
| `MCP_FINANCE_PROFILE_DIR` | 浏览器 profile 目录 | `<用户目录>/.mcp-finance/profile` |
| `MCP_FINANCE_DATA_DIR` | 数据缓存目录（cookies.json / portfolio.json） | `<用户目录>/.mcp-finance/data` |
| `FINANCE_BASE_URL` | 数据源 API 域名 | 示例数据源域名 |
| `FINANCE_LOGIN_URL` | 扫码登录页地址 | 示例数据源登录页 |

### WorkBuddy 配置

把下面内容加入 MCP 配置文件，替换 `<...>` 占位符为你的实际路径：

```json
{
  "mcpServers": {
    "mcp-finance": {
      "command": "node",
      "args": ["<绝对路径>/mcp-finance/src/server.js"],
      "env": {
        "NODE_WORKSPACE_DIR": "<绝对路径>/mcp-finance/node_modules",
        "MCP_FINANCE_DATA_DIR": "<用户目录>/.mcp-finance/data",
        "FINANCE_BASE_URL": "https://<你的数据源域名>",
        "FINANCE_LOGIN_URL": "https://<你的数据源登录页>"
      }
    }
  }
}
```

### ChatGPT 桌面端 / Claude Desktop

配置结构与上一致，仅需把 `command` 改成你机器上的 Node 可执行文件路径、`args` 改成 server.js 的绝对路径。Windows 路径建议使用正斜杠 `/` 或双反斜杠 `\\`。

## 使用流程

1. 首次登录：调用 `prepare_login`，用手机扫描返回的二维码。
2. 登录确认：调用 `wait_for_login` 等待登录完成。
3. 读取数据：调用 `get_positions` / `get_total_profit` 等。
4. 本地记录：调用 `add_local_transaction` 手动补充交易。

Cookie 有效期取决于数据源（示例源约 30 天），过期后需重新扫码。登录态与 Cookie 只保存在你本机用户目录，不会上传。

## 接入其他数据源

本模板把「浏览器/登录/Cookie/缓存/工具注册」与「具体 API」解耦：

1. **改域名**：设置 `FINANCE_BASE_URL` / `FINANCE_LOGIN_URL`，无需改代码。
2. **改接口**：编辑 `src/licaitong.js`，把其中的接口路径与请求参数换成目标数据源的；字段解析函数按目标返回结构调整。
3. **改单位换算**：`src/server.js` 中的 `fenToYuan` / `bpToPercent` 等是按示例源的数据单位写的，按目标源调整或删除。
4. **改工具清单**：`src/server.js` 里 `server.tool(...)` 注册的工具可自由增删，接口保持不变。

## 安全与隐私

- 持久化 Cookie 文件位于本机用户目录，**请勿分享或上传至公网**。
- 登录凭证（支付密码、短信验证码等敏感操作）不在 MCP 工具范围内，仅在网页中由用户主动完成。
- 自动化访问应控制频率，避免触发数据源的风控策略。
- 本项目不含、也不应包含任何真实账户、真实姓名、真实持仓数据。示例文档中的数值均为占位说明。

## License

MIT
