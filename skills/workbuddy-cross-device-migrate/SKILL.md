---
name: workbuddy-cross-device-migrate
version: 1.0.0
description: WorkBuddy 跨端（电脑→手机）任务与产物迁移。当用户反馈"手机端看不到电脑端的项目任务/会话"、要求把本地项目下的会话与产物迁移到手机端可查看、或要把本项目子任务批量登记为看板任务时使用。包含三层数据体系诊断、看板任务批量建档、本地独立会话构造、同步映射补齐的完整流程与实测参数。
agent_created: true
---

# WorkBuddy 跨端迁移（电脑 → 手机）

## 适用场景

- 用户报告：手机端（微信小程序 / 移动 App）看不到电脑端在项目下创建的任务 / 会话。
- 用户要求：把电脑本地某项目下的全部子任务、核心产物迁移到手机端可查看。
- 用户要求：把本项目的教学 / 工作成果批量登记为「正式看板任务」。

## 一、先诊断：三层数据体系（勿混淆）

| 层 | 存储 | 手机端可见性 |
|---|---|---|
| 本地会话 | `~/.workbuddy/workbuddy.db` sessions 表，`transport='local'` | 默认不可见；需「选择设备」建联 **且** 需 `edge-sync-mapping*.db` 有映射 |
| 云端会话 | 同上，`transport='cloud'`，`visibility='PRIVATE'` | 项目详情页「**任务**」栏 = 已共享进项目的云端会话（project_id 非空） |
| 看板任务 | wb-issues todo（云端 Teams） | 项目详情页「**计划**」栏，**两端实时可见**，最可靠 |

诊断命令（只读，安全）：

```python
import sqlite3
DB = r"C:\Users\<user>\.workbuddy\workbuddy.db"
conn = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("""SELECT id,title,project_id,transport,visibility,cwd,agent_last_synced,verified_at
               FROM sessions WHERE project_id=? ORDER BY created_at""", (PROJECT_ID,))
for r in cur.fetchall(): print(dict(r))
```

判据：
- 本项目会话 `transport` 全为 `local` 且 `agent_last_synced IS NULL` → 永不上云。
- 云端会话 `project_id IS NULL` → 未共享进项目 → 「任务」栏必空。

## 二、【决定性】手机端可见本地会话的唯一凭据

`~/.workbuddy/edge-sync-mapping-v4.db`（v3 并存）表：

```sql
edge_sync_mapping(session_id TEXT PK, conversation_id TEXT, msg_channel TEXT, created_at INTEGER)
```

- `msg_channel` 格式：`convmsg:<user_id>`。
- 被映射的会话**全部是 `transport=local` + `project_id=NULL` 的本地独立会话** —— 这是"本地独立任务手机端可见"的机制。
- **本项目下 10 条本地会话无一条被映射** → 手机端不可见的直接原因。
- 配套表 `edge_sync_artifact_cache(file_path, mtime_ms, size, file_hash, download_url, smh_path, ...)`：本地文件 → COS 下载 URL 缓存。

补齐映射（新建独立会话后必须做）：

```python
conn = sqlite3.connect(r"C:\Users\<user>\.workbuddy\edge-sync-mapping-v4.db")
conn.execute("INSERT INTO edge_sync_mapping (session_id,conversation_id,msg_channel,created_at) VALUES (?,?,?,?)",
             (sid, sid, f"convmsg:{uid}", int(time.time())))
conn.commit()
```

## 三、通路 A：批量创建看板任务（最稳）

用 `mcp__wb-issues__todo_create` + `mcp__wb-issues__todo_add_attachment`。

- 描述模板：会话 ID / 标题 / 时间范围 / 核心内容 / 核心产物清单（文件名+字节数+落盘目录）/ 附件位置。
- 附件：`provider="NETDISK"`，`external_id=<file_id>`，`file_type="md"`。
- 先 `todo_list_field_options` 查 priority / tags 合法值（常见：urgent/high/medium/low）。
- ⚠️ 描述文本**不要以反斜杠结尾**（JSON 转义会吞掉引号导致解析失败）；Windows 路径一律写正斜杠 `D:/学习资料/`。
- 校验：`todo_list` 应返回 total 与附件齐全。

## 四、通路 B：构造「本地独立会话」承载档案

1. **备份 DB**（务必）：`cp workbuddy.db _backup_<ts>/workbuddy.db.bak`
2. **写 jsonl**：`~/.workbuddy/projects/<编码目录>/<sid>.jsonl`
   - 目录编码规则：`D:\学习资料` → `d-学习资料`（小写盘符 + 路径转换）。
   - 每行一个 JSON，行类型 `message`(role=user/assistant，content=[{type:"input_text"/"text",text}]）、`ai-title`。
   - 档案正文可直接塞进 assistant 的 `text`，手机端即可阅读全文。
3. **写 .meta.json**：`{sessionId,cwd,createdAt,acpConnectionId:"",title,transport:"local"}`
4. **写 artifact-index**：`~/.workbuddy/artifact-index/<sid>.json`
   `{version,lastUpdated,artifacts:[{type:"media",uri:"file:///...",name,mimeType,size,_meta:{sourceTool:"FileWatcher"}}]}`
5. **INSERT sessions**：
   ```sql
   INSERT INTO sessions (id,cwd,user_id,title,custom_title,status,created_at,updated_at,
     last_activity_at,is_playground,mode,model,permission_mode,use_sandbox_cli,
     project_id,transport,unread)
   VALUES (?,?,?,?,?, 'completed',?,?,?,0,'craft','deepseek-v4.1-flash',
     'bypassPermissions',1, NULL,'local',0);
   ```
   `project_id` 必须为 NULL（独立任务）；`transport='local'`。
6. **补同步映射**（见第二节）→ 手机端「选择设备」后可见。
7. 确保 `workspaces` 表已注册该 cwd（path 存在则更新 `last_opened_at`）。

## 五、网盘上传三步流（附件来源）

```
1) mcp__netdrive__tdrive.file_upload(dir_id, file_name, file_size)
   → 返回 confirm_key / task_id / domain / path / headers
2) Bash: cp 中文名 ascii名 && curl -sSL -X PUT -H '<每个 header 原样一对>' -T ascii名 "<https://domain><path>" -w "\nHTTP_CODE=%{http_code}\n"
3) mcp__netdrive__tdrive.file_upload_complete(dir_id, file_name, file_size, confirm_key, task_id)
   → file_id
```

要点：
- 必须 `-T`（流式），不要 `--data-binary "<path>"`（会上传路径字符串）。
- 限频 **5 秒/次**（错误码 406450）→ 每次调用前 `sleep 5`。
- 中文文件名先 `cp` 成 ASCII 临时名再上传（Git Bash 对中文名易报 (23)/(26)）。
- 大文件（PDF/图片）不必上传，在描述中注明本地路径即可；文字产物合并为单份 `*_完整产物档案.md` 既绕限频又适配手机阅读。

## 六、环境注意

- Bash 需补 PATH：`export PATH="/c/Users/<user>/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"`
- 复杂脚本写成 `.py` 文件再执行（内联 heredoc 易被转义破坏）。
- SQLite 只读：`sqlite3.connect("file:...?mode=ro", uri=True)`。
- 直连 `workbuddy.db` 写入前**必须备份**；写入后校验 sessions / 文件 / 映射三处。

## 七、验证清单

- [ ] `todo_list` 返回全部任务且附件齐全
- [ ] `sessions` 表新记录：`project_id IS NULL`、`transport='local'`
- [ ] `edge_sync_mapping` 有该 sid（v3+v4 都查）
- [ ] jsonl / meta / artifact-index 三文件存在且非空
- [ ] 网盘 file_id 可下载
- [ ] 手机端实测：主页任务列表选中电脑 → 见到新任务
