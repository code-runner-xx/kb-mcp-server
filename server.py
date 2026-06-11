"""kb-mcp-server 入口

把 kb.py 的四个纯函数包装成三个 MCP Tool,供 Claude Desktop / Inspector 调用。

铁律:
- stdio 传输下 stdout 是 JSON-RPC 通道,严禁 print();所有日志走 logging(默认 stderr)
- 中文返回 json.dumps(ensure_ascii=False),避免模型看到 \\uXXXX 转义
- 零命中返回明确文案而非空数组(模型对空数组解读不稳定)
- 任何异常不得让 Python 堆栈泄漏给 LLM,统一兜底成可读中文
"""

import json
import logging
import sys

from mcp.server.fastmcp import FastMCP

import kb

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("kb-mcp-server")

mcp = FastMCP("kb-mcp-server")


@mcp.tool()
def search_knowledge_base(query: str, top_k: int = 5) -> str:
    """语义检索知识库,返回与查询最相关的若干片段(含相似度与所属文档标题)。

    何时使用:用户提问涉及具体业务、产品、政策等知识库内容时,先调用本工具拿到
    相关片段再作答,并在回答中标注片段来源文档。

    参数:
    - query(必填):用户原话或主题关键词
    - top_k(默认 5):返回片段数,上限 20(超过会被自动钳制)
    """
    logger.info("search_knowledge_base 调用: query_len=%d top_k=%d", len(query), top_k)
    try:
        hits = kb.search(query, top_k=top_k)
        if not hits:
            return "知识库中没有与该问题相关的内容"
        return json.dumps(hits, ensure_ascii=False)
    except ValueError as e:
        return str(e)
    except Exception as e:
        logger.exception("search_knowledge_base 失败")
        return f"检索服务暂时不可用:{type(e).__name__}"


@mcp.tool()
def list_documents() -> str:
    """列出当前知识库的全部文档及元数据(id、标题、类型、状态、片段数、创建时间)。

    何时使用:用户询问"知识库里有什么"、需要清单概览,或在调用 get_document_content
    前需要先获取 document_id 时。无参数。
    """
    logger.info("list_documents 调用")
    try:
        docs = kb.list_docs()
        if not docs:
            return "知识库暂无文档"
        return json.dumps(docs, ensure_ascii=False, default=str)
    except ValueError as e:
        return str(e)
    except Exception as e:
        logger.exception("list_documents 失败")
        return f"检索服务暂时不可用:{type(e).__name__}"


@mcp.tool()
def get_document_content(document_id: str) -> str:
    """按 document_id 拉取并拼接单篇文档全文。

    何时使用:用户要看某文档完整内容,或 search 命中后需要更完整上下文时。
    参数 document_id 必须是合法 UUID(可从 list_documents 或 search_knowledge_base
    的返回中获取)。超 8000 字符会自动截断并在末尾标注原始字符数。
    """
    logger.info("get_document_content 调用: document_id=%s", document_id)
    try:
        return kb.get_doc_content(document_id)
    except ValueError as e:
        return str(e)
    except Exception as e:
        logger.exception("get_document_content 失败")
        return f"检索服务暂时不可用:{type(e).__name__}"


if __name__ == "__main__":
    logger.info("kb-mcp-server 启动,传输模式=stdio")
    mcp.run()
