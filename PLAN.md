# PLAN.md — kb-mcp-server 分步计划

> 编号用 M 前缀,与 aisc 的 Step 1-28 体系完全独立。规则与铁律见本仓库 `CLAUDE.md`。
> 每个 Step:规划者给指令 → 用户审核 → Claude Code 执行 → 输出"✅ 验收方案" → 用户测试回复"通过"才进下一步。

## 总览

| Step | 内容 | 对应实施文档 | 预估 | 状态 |
|---|---|---|---|---|
| M1 | 仓库初始化 + 环境 + echo 最小闭环 | Day 0 | 半天 | ⬜ |
| M2 | kb.py 四个纯函数(不碰 MCP) | Day 1 前半 | 半天 | ⬜ |
| M3 | server.py 包装 3 个 Tool | Day 1 后半 | 半天 | ⬜ |
| M4 | Claude Desktop 接入 + Resource + Prompt | Day 2 前半 | 半天 | ⬜ |
| M5 | 错误处理 + 手测用例清单 | Day 2 后半 | 半天 | ⬜ |
| M6 | README + 架构图 + 演示 GIF + 公开仓库 | Day 3 | 半天-1天 | ⬜ |
| M7 | (加分,待定)Streamable HTTP + Python Client | Day 3 加分 | 半天 | ⏸ M6 验收后拍板 |

---

## M1 · 仓库初始化 + 环境 + echo 最小闭环

**做什么**

- 初始化 git 仓库与目录结构(见 CLAUDE.md 第 3 节),写 `.gitignore`(含 `.env`)、`.env.example`、`pyproject.toml`
- uv 环境,`pip install "mcp[cli]"`(或 uv add)
- `server.py` 先只写一个 echo 工具的最小 FastMCP server(stdio)

**✅ 验收**

- `npx @modelcontextprotocol/inspector uv run server.py` 能连上,列出 echo 工具
- Inspector 中调用 echo,中文输入原样返回
- `git status` 确认 `.env` 不在跟踪列表

## M2 · kb.py 四个纯函数

**做什么**

- `embed_query(query) -> list[float]`:调 SiliconFlow bge-m3,断言 1024 维
- `search(query, top_k)`:RPC `match_document_chunks`,固定 `KB_TENANT_ID`
- `list_docs()`:select documents 表(显式 `user_id` 过滤)
- `get_doc_content(document_id)`:拼接 chunks,8000 字符截断
- 全部纯函数,不 import mcp,可独立测试

**✅ 验收**

- `python -c` 逐一直调四个函数,能查到 aisc 线上真实数据
- 检索一个已知存在的主题,返回片段内容相关、similarity 数值合理(>0.3)
- 故意传不存在的 uuid,返回可读错误而非堆栈

## M3 · server.py 包装 3 个 Tool

**做什么**

- 用 `@mcp.tool()` 把 kb.py 包装成 `search_knowledge_base` / `list_documents` / `get_document_content`
- description 按 CLAUDE.md 第 4 节文案写(中文,说清"什么时候用")
- 返回 `json.dumps(..., ensure_ascii=False)`

**✅ 验收**

- Inspector 中 3 个工具全部可调
- 中文查询返回正确片段;`top_k` 超 20 被钳制;零命中返回明确文案

## M4 · Claude Desktop 接入 + Resource + Prompt

**做什么**

- 写 `claude_desktop_config.json` 配置(Windows 双反斜杠路径,env 显式列全 4 个变量)
- 补 `@mcp.resource("kb://documents")` 与 `@mcp.prompt()` kb_qa 模板

**✅ 验收**

- 完全重启 Claude Desktop 后,工具图标出现
- 自然对话提一个知识库问题,模型自动调用 search_knowledge_base 并基于结果回答、标注来源
- Resource 在客户端可读取;Prompt 模板可选用

## M5 · 错误处理 + 手测用例清单

**做什么**

- 逐一处理:零命中 / 网络超时(断网)/ 错误 key / 非法 uuid,全部返回可读中文信息而非崩溃
- 写 `tests/manual_test.md`:用例清单(输入、预期输出、实测结果三列)

**✅ 验收**

- 手动制造四类故障,逐一确认报错可读、server 不退出
- manual_test.md 全部用例打勾

## M6 · README + 交付

**做什么**

- README:mermaid 架构图、Tools/Resources/Prompts 三类消息设计说明、10 分钟配置步骤、踩坑记录、演示 GIF(ScreenToGif 录 Claude Desktop 调用过程)
- 公开 GitHub 仓库,加 description 与 topics(mcp、rag、pgvector)

**✅ 验收**

- 换台电脑(或同学)按 README 操作,10 分钟内跑通
- 仓库无任何真实 key 痕迹(含历史 commit)

## M7 · (待定)Streamable HTTP + Python Client

M6 验收通过后由用户拍板是否启动。内容:`mcp.run(transport="streamable-http")` 起 HTTP 模式;写约 20 行 Python Client 脚本连自己的 Server 跑通完整流程。

---

## 与 aisc 的关系(边界声明)

- 只读复用:线上 Supabase 的 `match_document_chunks` RPC、documents/document_chunks 表、SiliconFlow key
- 零改动:不修改 aisc 仓库任何文件、不加表、不改 RPC、不在 aisc 的 V2-PLAN.md 里加 Step
- 若 aisc 侧需要记录关联(如 HANDOFF.md 加一行),由用户自行决定与执行