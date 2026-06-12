"""kb-mcp-server 自写 Client(stdio 子进程拉起 server,走完四步)。

演示从协议两侧验证 MCP Server:
- 这个脚本不是 Claude Desktop / Inspector,而是用官方 SDK 的客户端 API 把 server.py
  作为子进程拉起,在同一 stdio 通道上跑完 list_tools / call_tool / read_resource /
  get_prompt 四个动作,把 Tools / Resources / Prompts 三类消息从客户端侧全覆盖。
- 本 client 进程的 stdout 不是 JSON-RPC 通道,这里可以随便 print()(子进程 server
  仍严守"stdio 禁 print"铁律)。
- 子进程 server 默认继承父进程环境,server.py 启动时会自己 load_dotenv()。

运行(仓库根目录,.env 已填真值):
    uv run python client_demo.py
"""

import asyncio
import json

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SERVER_PARAMS = StdioServerParameters(
    command="uv",
    args=["run", "server.py"],
)


async def main() -> None:
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("=" * 60)
            print("✅ 已连接 kb-mcp-server(stdio 子进程)")
            print("=" * 60)

            # [1/4] list_tools:确认三个工具齐全
            tools_resp = await session.list_tools()
            print("\n[1/4] list_tools → 工具清单:")
            for t in tools_resp.tools:
                first_line = (t.description or "").splitlines()[0]
                print(f"  - {t.name}: {first_line}")

            # [2/4] call_tool('search_knowledge_base'):用必命中查询,JSON 反序列化首条
            print("\n[2/4] call_tool('search_knowledge_base', ...) →")
            call_resp = await session.call_tool(
                "search_knowledge_base",
                {"query": "澜途 X10 支持哪些地面材质的清洁", "top_k": 3},
            )
            text = call_resp.content[0].text
            hits = json.loads(text)  # 必命中查询,直接反序列化即可
            first = hits[0]
            print(f"  命中 {len(hits)} 条")
            print(f"  首条 similarity     = {first['similarity']:.4f}")
            print(f"  首条 document_title = {first['document_title']}")
            print(f"  首条 content 前 100 字:{first['content'][:100]}")

            # [3/4] read_resource('kb://documents'):文档清单只读快照
            print("\n[3/4] read_resource('kb://documents') → 文档标题清单:")
            res_resp = await session.read_resource("kb://documents")
            docs_text = res_resp.contents[0].text
            docs = json.loads(docs_text)
            for d in docs:
                print(f"  - {d['title']}(chunk_count={d.get('chunk_count')})")

            # [4/4] get_prompt('kb_qa'):渲染后模板(单条用户消息)
            print("\n[4/4] get_prompt('kb_qa', question='滤网怎么保养?') → 渲染后模板:")
            prompt_resp = await session.get_prompt(
                "kb_qa", {"question": "滤网怎么保养?"}
            )
            for msg in prompt_resp.messages:
                content = msg.content
                text_val = getattr(content, "text", content)
                print(f"  [{msg.role}] {text_val}")

            print("\n" + "=" * 60)
            print("✅ 四步全跑完,退出")
            print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
