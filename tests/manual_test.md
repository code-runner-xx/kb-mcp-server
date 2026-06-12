# kb-mcp-server 手测用例清单

> 用法:跟随 PLAN.md M5 验收。每条做完在「实测结果」打 ✅ 或写实际偏差。
> 推荐环境:Inspector(`npx @modelcontextprotocol/inspector uv run server.py`)+ PowerShell。
> 所有"如何制造"涉及改 `.env` 的步骤,**做完后务必改回真实值**。

## 一、正常路径(3 条)

| # | 操作步骤 | 预期结果 | 实测结果 |
|---|---|---|---|
| 1 | Inspector → Tools → `search_knowledge_base`,`query` 填「澜途 X10 支持哪些地面材质的清洁」,`top_k=5` | 返回中文 JSON 数组(**无 `\uXXXX`**),首项 `similarity` ≈ 0.72 ¹,`document_title` = `lantu-x10-manual` | ☐ |
| 2 | Inspector → Tools → `list_documents`,无参数 Run | 返回中文 JSON,1 条 `lantu-x10-manual`,含 `chunk_count` / `created_at` | ☐ |
| 3 | Inspector → Tools → `get_document_content`,`document_id` 填 `6aa0ff19-d923-402c-b314-ad81b38a5dd5` | 返回纯文本,**开头 `# 澜途 X10 智能扫地机器人 · 产品使用与服务手册`**,~7620 字符,未触发截断 | ☐ |

¹ **关于 similarity ≈ 0.72 的脚注**:该数值仅对查询原文「澜途 X10 支持哪些地面材质的清洁」成立,改一个字 similarity 就会变。判定标准是 **「内容相关 + 明显高于 0.3 + title 正确」**,不要把 0.72 当作硬性卡点(M4 验收时踩过这个误会)。

## 二、Resource + Prompt(2 条)

| # | 操作步骤 | 预期结果 | 实测结果 |
|---|---|---|---|
| 4 | Inspector → Resources → List → 点 `kb://documents` → Read | 内容区返回中文 JSON,结构与用例 2 一致 | ☐ |
| 5 | Inspector → Prompts → List → 选 `kb_qa`,`question` 填「扫地机器人卡住了怎么办?」→ Get Prompt | 右侧渲染完整模板:`基于知识库回答以下问题。请先调用 search_knowledge_base 检索相关片段...问题:扫地机器人卡住了怎么办?` | ☐ |

## 三、已覆盖的兜底分支(3 条)

| # | 操作步骤 | 预期结果 | 实测结果 |
|---|---|---|---|
| 6 | Inspector → Tools → `search_knowledge_base`,`query` 填乱码串「zzqq xkcd 0237 lorem」,`top_k=5` | 返回纯字符串「**知识库中没有与该问题相关的内容**」,**不是空数组**(命令行打桩:`kb.search('随便什么', min_similarity=0.99)` → `[]`,叠加 server 兜底 `if not hits` 即可得证) | ☐ |
| 7 | Inspector → Tools → `get_document_content`,`document_id` 填 `not-a-uuid` | 返回「**文档 ID 不是合法的 UUID 格式:'not-a-uuid'**」,无 Python 堆栈 | ☐ |
| 8 | Inspector → Tools → `get_document_content`,`document_id` 填合法但不存在的 uuid `00000000-0000-0000-0000-000000000000` | 返回「**未找到该文档,或该文档无可读内容(document_id=00000000-...)**」 | ☐ |

## 四、异常路径(关键 —— 验证 M5 兜底)

> ⚠️ 制造下列异常前先确认 Inspector 是 Connected;每条做完务必把 `.env` 改回真实值。

| # | 操作步骤(如何制造该故障) | 预期结果 | 实测结果 |
|---|---|---|---|
| 9 | **SiliconFlow key 失效**:把 `.env` 的 `SILICONFLOW_API_KEY` 改为 `sk-INVALID-FAKE`,**重启 Inspector**(Server 进程在启动时 load_dotenv);Tools → `search_knowledge_base("澜途 X10", 3)` | 返回「**检索服务暂时不可用:AuthenticationError**」,**不含 key 片段**,Inspector 保持 Connected,server 不退出 | ☐ |
| 10 | **Supabase 不可达**:把 `.env` 的 `SUPABASE_URL` 改为 `https://nonexistent-xxx-kb.supabase.co`,重启 Inspector;Tools → `search_knowledge_base("澜途 X10", 3)` | **15 秒内**返回「**检索服务暂时不可用:ConnectError**」(或 `ReadTimeout` / `ProxyError`,取决于本地网络),**不含 service_role_key**,Inspector 保持 Connected | ☐ |
| 11 | **RPC 名错(模拟数据库 schema 漂移)**:**命令行打桩验证**(不便临时改 SQL),已在 M5 自检中跑过:`kb.supabase_client.rpc = lambda n,p: orig('match_document_chunks_xxx', p)` → search → 返回「检索服务暂时不可用:APIError」 | 同左,APIError 兜底,server 不退出 | ☐(代码审查通过) |
| 12 | **超长 query 不挂死**:Tools → `search_knowledge_base`,`query` 粘贴 5000+ 中文字符(bge-m3 token 上限 8192,实际仍在限内);可粘贴用例 3 拉到的全文 | 5 秒内正常返回 JSON;若超 token 上限,返回「检索服务暂时不可用:BadRequestError」之类,server 不退出 | ☐ |
| 13 | **空知识库兜底**(可选,如不便清空可跳过):把 `.env` 的 `KB_TENANT_ID` 改为合法但无数据的 uuid(如 `11111111-1111-1111-1111-111111111111`),重启 Inspector;Tools → `list_documents()` | 返回「**知识库暂无文档**」,**不是空数组** | ☐ |

## 五、改完 .env 后的还原检查

| 操作 | 预期 |
|---|---|
| 把 `.env` 三个被改过的值改回真实值 → 重启 Inspector → 跑用例 1 | 与用例 1 完全一致,similarity 仍在 0.7+ |

---

**关于"检索服务暂时不可用:{ClassName}"的兜底设计**:
- 故意保留异常类名(`AuthenticationError` / `ConnectError` / `APITimeoutError` / `APIError` / `BadRequestError`),让模型和运维**粗略区分**故障类型,无需 isinstance 分支爆炸
- 完整堆栈走 `logger.exception` 进 stderr(不污染 stdout 的 JSON-RPC 通道,符合铁律 1),便于本地排查
- 不暴露 key、url、tenant_id 的值给 stdout
