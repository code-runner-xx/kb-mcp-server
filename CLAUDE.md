# CLAUDE.md — kb-mcp-server 开发手册(规则书)

> 独立于 ai-customer-service-saas(下称 aisc)的新项目:用官方 MCP Python SDK 把 aisc 的知识库检索能力封装成标准 MCP Server。
>
> 本文件是 Claude Code 的**权威执行指南**。每完成一个 Step 必须停下,输出"✅ 验收方案"让用户手动测试,用户回复"通过"后才能进入下一步。禁止跳步、禁止一次性写完多个 Step。
>
> 配套文档:**PLAN.md** — M1-M7 分步计划与验收标准。

---

## 0. 项目铁律(必读)

1. **stdio 模式下绝对禁止 `print()` 到 stdout**。stdout 就是 JSON-RPC 通道,一行 print 直接把协议打挂。调试日志一律用 `logging`(默认走 stderr)。这是本项目第一铁律。
2. **语言**:注释、commit message、工具 description 与返回文案使用简体中文;代码标识符使用英文。
3. **Secrets**:真实 key 永不进代码与 git,仓库只提交 `.env.example` 占位;日志不打印 key 和完整 chunk 内容。
4. **租户隔离**:所有 SQL/RPC 固定 `user_id = KB_TENANT_ID`(服务端从环境变量读取写死),**绝不**把 tenant_id 暴露为工具参数。Service Role Key 会绕过 RLS,这正是必须显式过滤的原因。
5. **全部工具只读幂等**:不暴露任何写入/删除操作(最小权限原则)。
6. **中文返回**:`json.dumps(..., ensure_ascii=False)`,否则模型看到 `\uXXXX`。
7. **零命中**:返回明确文案「知识库中没有与该问题相关的内容」,不返回空数组(模型对空数组解读不稳定)。
8. **不要自作主张**:本手册与 PLAN.md 未写清楚的细节,先在回答开头列出"❓ 待确认"问用户。
9. **不擅自升级依赖**:以下文版本锁定为准,遇到不一致的 API 写法以锁定版本为准。
10. **对 aisc 零改动**:本项目只读复用 aisc 的线上 Supabase RPC 与 SiliconFlow key,严禁修改 aisc 仓库的任何文件、表结构或 RPC 函数。

---

## 1. 版本与技术选型(锁定)

| 项 | 选择 | 说明 |
|---|---|---|
| 语言 | Python 3.11 | |
| SDK | 官方 `mcp` 包(内置 FastMCP),`pip install "mcp[cli]"` | 社区另有独立 FastMCP 2.x/3.x 包,**不用**,以官方 SDK 为准 |
| 传输 | stdio(本地) | Streamable HTTP 仅 M7 加分项 |
| Embedding | SiliconFlow `BAAI/bge-m3` | **1024 维**,与 aisc 同源,严禁换模型(RPC 不报错但检索静默错配) |
| 数据访问 | `supabase-py` 调 RPC `match_document_chunks` | 直连 aisc 线上库,零迁移 |
| 依赖管理 | uv | Claude Desktop 配置里直接写 `uv run` |
| 调试工具 | `npx @modelcontextprotocol/inspector` | 先 Inspector 后 Desktop,Desktop 报错信息极少 |

---

## 2. 环境变量(`.env.example`)

```
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SILICONFLOW_API_KEY=
KB_TENANT_ID=
```

`KB_TENANT_ID` = aisc 中你的 user_id,写死实现租户隔离。

注意:Claude Desktop 配置中的 `env` 字段需显式列出全部四个变量,Server 进程**不继承**终端环境变量。

---

## 3. 目录结构

```
kb-mcp-server/
├── server.py          # FastMCP 入口:工具/资源/提示词定义
├── kb.py              # embedding 调用 + Supabase 检索封装(纯函数,可独立测试)
├── .env.example       # 环境变量占位(真实 .env 不进 git)
├── pyproject.toml
├── README.md
├── CLAUDE.md          # 本文件
├── PLAN.md            # 分步计划
└── tests/manual_test.md  # 手测用例清单
```

---

## 4. 工具/资源/提示词设计(以此为准)

**Tool 1 · search_knowledge_base**:语义检索。参数 `query: string`(必填)、`top_k: integer`(默认 5,上限 20)。实现:`embed_query(query)` → `supabase.rpc("match_document_chunks", {query_embedding, tenant_id, match_count})`。返回 `[{content, similarity, document_title}]`。

**Tool 2 · list_documents**:列出全部文档(标题/类型/状态/片段数/创建时间/id)。无参数。空知识库返回「知识库暂无文档」。

**Tool 3 · get_document_content**:按 `document_id`(uuid)拼接全文。超 8000 字符截断并注明「已截断,共 N 字符」;uuid 非法或不存在返回可读错误。

**Resource**:`@mcp.resource("kb://documents")` 文档清单只读快照(客户端主动读取的数据,区别于模型决策调用的 Tool)。

**Prompt**:`@mcp.prompt()` 定义 `kb_qa` 模板:「基于知识库回答以下问题,先调用 search_knowledge_base 检索,回答末尾列出来源文档」。

description 写法原则:说清楚「什么时候用」,参数能约束就约束。

---

## 5. 与 Claude Code 协作约定

每个 Step 标准流程(与 aisc 5.1 相同):

1. **开始前报备**:计划修改的文件、要运行的命令、预计耗时,等用户回复"开始"
2. **完成后输出三块**:变更摘要 / ✅ 验收方案(手动步骤 + 命令)/ 下一步预告
3. **用户回复"通过"才进入下一 Step**;"不通过"必须先修复
4. 未定义的问题先问用户,不要发明方案

规划者 Claude(对话版)拆步与验收,Claude Code 按当前 Step 指令执行,不需要理解项目宏观目标。

**Claude Code 不得修改 CLAUDE.md / PLAN.md**,除非用户明确指示。

---

## 6. 常见坑(动手前先读)

1. stdio 下禁 print(铁律第 1 条)
2. Claude Desktop 改完配置必须**完全退出**(系统托盘右键退出)再启动,只关窗口不重载配置
3. Windows 配置 JSON 路径写双反斜杠 `\\`
4. 配置 `env` 字段需显式列全环境变量,不继承终端
5. 先 Inspector 后 Desktop,所有问题先在 Inspector 定位
6. 中文返回 `ensure_ascii=False`
7. bge-m3 是 1024 维,换模型 = 静默错配
8. Service Role Key 绕过 RLS → SQL 必须显式带 `user_id` 过滤