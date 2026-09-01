"""Tool definitions, execution context, and dispatcher for the Agentic Reasoning Engine."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.core.llm import ToolDefinition
from app.core.logging import get_logger
from app.indexer.embeddings import EmbeddingProvider, get_embedding_provider
from app.indexer.storage import CrawlStorage, get_crawl_storage
from app.search.service import SearchService

logger = get_logger("panopticon.agent.tools")

MAX_TOOL_OUTPUT_CHARS = 2500


@dataclass
class AgentToolContext:
    """Dependency injection container for tool execution."""

    storage: CrawlStorage
    search_service: SearchService | None = None
    embedding_provider: EmbeddingProvider | None = None


# ------------------------------------------------------------------------------
# Tool Definitions (OpenAI-compatible JSON Schema)
# ------------------------------------------------------------------------------

SEARCH_INDEX_TOOL = ToolDefinition(
    name="search_index",
    description=(
        "Search the local document catalog by keywords, file names, or project tags. "
        "Returns matching document records including file_id, name, owners, project_tags, and content snippet."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search terms or keywords (e.g. 'Falcon OAuth', 'Budget spreadsheet')",
            },
            "project_tag": {
                "type": "string",
                "description": "Optional project tag filter (e.g. 'Falcon', 'SmartTrade')",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of search results to return (default: 5)",
                "default": 5,
            },
        },
        "required": ["query"],
    },
)

GET_DOCUMENT_DIFF_TOOL = ToolDefinition(
    name="get_document_diff",
    description=(
        "Fetch the temporal change log and unified text patch for a specific document. "
        "Shows exactly what text lines were added (+), removed (-), or modified across versions."
    ),
    parameters={
        "type": "object",
        "properties": {
            "file_id": {
                "type": "string",
                "description": "The unique Google Drive file ID",
            },
            "version_id": {
                "type": "integer",
                "description": "Optional specific version number to inspect. If omitted, returns latest diff.",
            },
        },
        "required": ["file_id"],
    },
)

GET_FILE_METADATA_TOOL = ToolDefinition(
    name="get_file_metadata",
    description=(
        "Retrieve complete metadata for a document including owners, modified date, "
        "creation date, MIME type, sharing status, and direct web link."
    ),
    parameters={
        "type": "object",
        "properties": {
            "file_id": {
                "type": "string",
                "description": "The unique Google Drive file ID",
            },
        },
        "required": ["file_id"],
    },
)

SEMANTIC_CHUNK_SEARCH_TOOL = ToolDefinition(
    name="semantic_chunk_search",
    description=(
        "Perform deep semantic vector search over document paragraph chunks. "
        "Best for conceptual questions, finding specific technical paragraphs, or locating policies."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language question or concept to search semantically",
            },
            "project_tag": {
                "type": "string",
                "description": "Optional project filter to restrict vector search",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of paragraph chunks to return (default: 3)",
                "default": 3,
            },
        },
        "required": ["query"],
    },
)

PANOPTICON_TOOLS: list[ToolDefinition] = [
    SEARCH_INDEX_TOOL,
    GET_DOCUMENT_DIFF_TOOL,
    GET_FILE_METADATA_TOOL,
    SEMANTIC_CHUNK_SEARCH_TOOL,
]


# ------------------------------------------------------------------------------
# Tool Handlers
# ------------------------------------------------------------------------------

def _handle_search_index(args: dict[str, Any], ctx: AgentToolContext) -> str:
    query = str(args.get("query", "")).strip()
    if not query:
        return json.dumps({"error": "Missing required argument 'query'."})

    project_tag = args.get("project_tag")
    limit = min(int(args.get("limit", 5)), 10)

    # 1. Try Meilisearch search_service if configured
    if ctx.search_service:
        try:
            res = ctx.search_service.search(query=query, project_tag=project_tag, limit=limit)
            hits = [
                {
                    "file_id": h.id,
                    "name": h.name,
                    "mime_type": h.mime_type,
                    "owners": h.owners,
                    "project_tags": h.project_tags,
                    "snippet": h.content_snippet,
                    "modified_time": h.modified_time.isoformat() if h.modified_time else None,
                }
                for h in res.hits
            ]
            return json.dumps({"results_count": len(hits), "hits": hits})
        except Exception as exc:
            logger.warning("SearchService error in tool, falling back to SQLite: %s", exc)

    # 2. SQLite fallback
    files = ctx.storage.list_files(limit=50)
    matched = []
    q_lower = query.lower()
    for f in files:
        if project_tag and project_tag.lower() not in [t.lower() for t in f.project_tags]:
            continue
        if q_lower in f.name.lower() or (f.content_snippet and q_lower in f.content_snippet.lower()):
            matched.append(
                {
                    "file_id": f.id,
                    "name": f.name,
                    "mime_type": f.mime_type,
                    "owners": f.owners,
                    "project_tags": f.project_tags,
                    "snippet": f.content_snippet,
                    "modified_time": f.modified_time.isoformat() if f.modified_time else None,
                }
            )
            if len(matched) >= limit:
                break

    return json.dumps({"results_count": len(matched), "hits": matched})


def _handle_get_document_diff(args: dict[str, Any], ctx: AgentToolContext) -> str:
    file_id = str(args.get("file_id", "")).strip()
    if not file_id:
        return json.dumps({"error": "Missing required argument 'file_id'."})

    diffs = ctx.storage.get_diffs(file_id)
    if not diffs:
        return json.dumps({
            "file_id": file_id,
            "status": "no_diffs_found",
            "message": "No version changes recorded for this document yet.",
        })

    version_id = args.get("version_id")
    target_diffs = diffs
    if version_id is not None:
        target_diffs = [d for d in diffs if str(version_id) in (d.to_version_id, str(d.id))]

    if not target_diffs:
        return json.dumps({
            "file_id": file_id,
            "status": "version_not_found",
            "message": f"Version {version_id} not found for this document.",
        })

    serialized = []
    for d in target_diffs[:3]:
        # Truncate patch text if too long
        patch_snippet = d.patch_text[:1200] if d.patch_text else None
        serialized.append({
            "diff_id": d.id,
            "from_version_id": d.from_version_id,
            "to_version_id": d.to_version_id,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "lines_added": d.lines_added,
            "lines_removed": d.lines_removed,
            "ai_summary": d.ai_summary,
            "patch_snippet": patch_snippet,
        })

    return json.dumps({"file_id": file_id, "diffs": serialized})


def _handle_get_file_metadata(args: dict[str, Any], ctx: AgentToolContext) -> str:
    file_id = str(args.get("file_id", "")).strip()
    if not file_id:
        return json.dumps({"error": "Missing required argument 'file_id'."})

    f = ctx.storage.get_file(file_id)
    if not f:
        return json.dumps({
            "file_id": file_id,
            "status": "not_found",
            "message": f"Document '{file_id}' does not exist in local repository.",
        })

    return json.dumps({
        "file_id": f.id,
        "name": f.name,
        "mime_type": f.mime_type,
        "owners": f.owners,
        "last_modifying_user": f.last_modifying_user,
        "modified_time": f.modified_time.isoformat() if f.modified_time else None,
        "created_time": f.created_time.isoformat() if f.created_time else None,
        "sharing_status": f.sharing_status,
        "project_tags": f.project_tags,
        "web_view_link": f.web_view_link,
        "size_bytes": f.size_bytes,
    })


def _handle_semantic_chunk_search(args: dict[str, Any], ctx: AgentToolContext) -> str:
    query = str(args.get("query", "")).strip()
    if not query:
        return json.dumps({"error": "Missing required argument 'query'."})

    limit = min(int(args.get("limit", 3)), 5)
    file_id = args.get("file_id")

    provider = ctx.embedding_provider or get_embedding_provider()
    query_vector = provider.embed_query(query)

    chunks = ctx.storage.search_similar_chunks(
        query_vector=query_vector,
        limit=limit,
        file_id_filter=file_id,
    )

    results = []
    for chunk, similarity in chunks:
        results.append({
            "chunk_id": chunk.id,
            "file_id": chunk.file_id,
            "section_heading": chunk.section_heading,
            "similarity_score": round(similarity, 3),
            "text": chunk.content_text[:800],
        })

    return json.dumps({
        "query": query,
        "chunks_count": len(results),
        "chunks": results,
    })


# ------------------------------------------------------------------------------
# Dispatcher
# ------------------------------------------------------------------------------

_TOOL_DISPATCH_TABLE = {
    "search_index": _handle_search_index,
    "get_document_diff": _handle_get_document_diff,
    "get_file_metadata": _handle_get_file_metadata,
    "semantic_chunk_search": _handle_semantic_chunk_search,
}


def execute_tool(name: str, arguments: dict[str, Any], context: AgentToolContext) -> str:
    """Safely route and execute a tool call with character bounds enforcement."""
    handler = _TOOL_DISPATCH_TABLE.get(name)
    if not handler:
        logger.warning("Agent requested unknown tool: %s", name)
        return json.dumps({
            "error": f"Unknown tool '{name}'. Available tools: {list(_TOOL_DISPATCH_TABLE.keys())}"
        })

    try:
        raw_output = handler(arguments, context)
    except Exception as exc:
        logger.error("Error executing tool '%s': %s", name, exc, exc_info=True)
        return json.dumps({"error": f"Tool execution failed: {exc}"})

    if len(raw_output) > MAX_TOOL_OUTPUT_CHARS:
        logger.debug("Truncating tool output for '%s' from %d to %d chars", name, len(raw_output), MAX_TOOL_OUTPUT_CHARS)
        return raw_output[:MAX_TOOL_OUTPUT_CHARS] + '... [output truncated for context limit]"}'

    return raw_output
