"""知识库纯函数封装。

只读复用 aisc 线上 Supabase(documents / document_chunks 表 + match_document_chunks RPC)
与 SiliconFlow 的 BAAI/bge-m3 embedding。本模块不 import mcp,可独立 python -c 调用。

铁律:
- 租户隔离:所有查询显式 eq("user_id", KB_TENANT_ID);Service Role Key 绕过 RLS,过滤必须自己做
- embedding 维度:bge-m3 = 1024,断言不通过即抛错(防模型换错导致静默错配)
- 错误处理边界:uuid 非法 / 文档查不到显式抛 ValueError(中文);网络/RPC 错误本层不兜底,M5 统一处理
"""

import os
import uuid
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv()

# 模块级单例,import 时即检查环境(失败得早比失败得隐蔽好)
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
SILICONFLOW_API_KEY = os.environ["SILICONFLOW_API_KEY"]
KB_TENANT_ID = os.environ["KB_TENANT_ID"]

EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
CONTENT_TRUNCATE_LIMIT = 8000

supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
openai_client = OpenAI(api_key=SILICONFLOW_API_KEY, base_url=SILICONFLOW_BASE_URL)


def embed_query(query: str) -> list[float]:
    """把查询文本编码为 1024 维向量,用于 pgvector 检索。"""
    resp = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=query)
    vec = resp.data[0].embedding
    if len(vec) != EMBEDDING_DIM:
        raise RuntimeError(
            f"embedding 维度异常:期望 {EMBEDDING_DIM},实际 {len(vec)}。"
            f"模型可能被换错(必须为 {EMBEDDING_MODEL}),否则与 aisc 已入库向量静默错配。"
        )
    return vec


def search(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """语义检索:返回最相关的 top_k 个片段。top_k 钳制到 [1, 20]。"""
    top_k = max(1, min(20, top_k))
    vec = embed_query(query)

    rpc_resp = supabase_client.rpc(
        "match_document_chunks",
        {
            "query_embedding": vec,
            "tenant_id": KB_TENANT_ID,
            "match_count": top_k,
        },
    ).execute()
    hits = rpc_resp.data or []
    if not hits:
        return []

    # 一次 in 查询拿 document_id → title 映射(避免逐条查)
    doc_ids = list({h["document_id"] for h in hits})
    title_resp = (
        supabase_client.table("documents")
        .select("id, title")
        .in_("id", doc_ids)
        .eq("user_id", KB_TENANT_ID)
        .execute()
    )
    id_to_title = {row["id"]: row["title"] for row in (title_resp.data or [])}

    return [
        {
            "content": h["content"],
            "similarity": h["similarity"],
            "document_title": id_to_title.get(h["document_id"], "(未知文档)"),
        }
        for h in hits
    ]


def list_docs() -> list[dict[str, Any]]:
    """列出当前租户全部文档(按 created_at 倒序)。"""
    resp = (
        supabase_client.table("documents")
        .select("id, title, content_type, status, chunk_count, created_at")
        .eq("user_id", KB_TENANT_ID)
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


def get_doc_content(document_id: str) -> str:
    """按 document_id 拼接全文(按 metadata.index 升序)。超 8000 字符截断并标注原始长度。"""
    try:
        uuid.UUID(document_id)
    except (ValueError, AttributeError, TypeError) as e:
        raise ValueError(f"文档 ID 不是合法的 UUID 格式:{document_id!r}") from e

    resp = (
        supabase_client.table("document_chunks")
        .select("content, metadata")
        .eq("document_id", document_id)
        .eq("user_id", KB_TENANT_ID)
        .execute()
    )
    chunks = resp.data or []
    if not chunks:
        raise ValueError(f"未找到该文档,或该文档无可读内容(document_id={document_id})")

    # aisc 的 ingest 写入 metadata: { index: i },按 index 升序拼接;
    # 缺 index 字段的 chunk 视作末尾(用 inf 兜底)
    chunks.sort(key=lambda c: (c.get("metadata") or {}).get("index", float("inf")))
    full_text = "\n\n".join(c["content"] for c in chunks)

    total = len(full_text)
    if total > CONTENT_TRUNCATE_LIMIT:
        return full_text[:CONTENT_TRUNCATE_LIMIT] + f"\n\n---\n[已截断,共 {total} 字符]"
    return full_text
