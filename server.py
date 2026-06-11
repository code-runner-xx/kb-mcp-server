"""kb-mcp-server 入口

M1 阶段:仅提供 echo 工具,用于验证 FastMCP + stdio 最小闭环。
铁律:stdio 传输下 stdout 是 JSON-RPC 通道,严禁 print();所有日志走 logging(默认 stderr)。
"""

import logging
import sys

from mcp.server.fastmcp import FastMCP

# 日志显式输出到 stderr,避免污染 stdout(JSON-RPC 通道)
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("kb-mcp-server")

mcp = FastMCP("kb-mcp-server")


@mcp.tool()
def echo(text: str) -> str:
    """回声测试工具:原样返回输入文本,用于验证 MCP 服务器连通性。

    使用场景:首次接入或排查传输问题时调用,确认 stdio 通道正常。
    """
    logger.info("echo 被调用,文本长度=%d", len(text))
    return text


if __name__ == "__main__":
    logger.info("kb-mcp-server 启动,传输模式=stdio")
    mcp.run()
