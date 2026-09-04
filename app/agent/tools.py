"""Tool definitions, execution context, and dispatcher for the Agentic Reasoning Engine."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.core.llm import ToolDefinition
from app.core.logging import get_logger
from app.indexer.embeddings import EmbeddingProvider, get_embedding_provider
from app.indexer.storage import CrawlStorage, get_crawl_storage
from app.search.service import SearchService

logger = get_logger("panopticon.agent.tools")

MAX_TOOL_OUTPUT_CHARS = 4000

@dataclass
class AgentToolContext:
    """Dependency injection container for tool execution."""

    storage: CrawlStorage
    search_service: SearchService | None = None
    embedding_provider: EmbeddingProvider | None = None
    dossier_id: str | None = None
    allowed_file_ids: set[str] | None = None


# ------------------------------------------------------------------------------
# Tool Definitions (OpenAI-compatible JSON Schema)
# ------------------------------------------------------------------------------

SEARCH_INDEX_TOOL = ToolDefinition(
    name="search_index",
    description=(
        "Search the local document catalog by keywords, file names, or project tags. "
        "Supports optional dossier_id to restrict search strictly to documents within a project container. "
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
            "dossier_id": {
                "type": "string",
                "description": "Optional Project Dossier ID to restrict search exclusively to documents inside that container",
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
            "dossier_id": {
                "type": "string",
                "description": "Optional Project Dossier ID enforcing boundary access",
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
            "dossier_id": {
                "type": "string",
                "description": "Optional Project Dossier ID enforcing boundary access",
            },
        },
        "required": ["file_id"],
    },
)

SEMANTIC_CHUNK_SEARCH_TOOL = ToolDefinition(
    name="semantic_chunk_search",
    description=(
        "Perform deep semantic vector search over document paragraph chunks. "
        "Supports optional dossier_id to restrict vector similarity strictly to chunks within a project container. "
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
            "dossier_id": {
                "type": "string",
                "description": "Optional Project Dossier ID to isolate semantic retrieval",
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

GET_DOCUMENT_CATALOG_STATS_TOOL = ToolDefinition(
    name="get_document_catalog_stats",
    description=(
        "Retrieve statistics and inventory breakdown of indexed documents in the repository or a specific dossier. "
        "Returns total file count, Docs vs Sheets count, project tags distribution, versions count, "
        "chunk counts, and recent file activity."
    ),
    parameters={
        "type": "object",
        "properties": {
            "dossier_id": {
                "type": "string",
                "description": "Optional Project Dossier ID to retrieve isolated dossier inventory stats",
            },
        },
        "required": [],
    },
)

PANOPTICON_TOOLS: list[ToolDefinition] = [
    GET_DOCUMENT_CATALOG_STATS_TOOL,
    SEARCH_INDEX_TOOL,
    GET_DOCUMENT_DIFF_TOOL,
    GET_FILE_METADATA_TOOL,
    SEMANTIC_CHUNK_SEARCH_TOOL,
]


# ------------------------------------------------------------------------------
# Tool Handlers
# ------------------------------------------------------------------------------

def _resolve_allowed_files(args: dict[str, Any], ctx: AgentToolContext) -> tuple[str | None, set[str] | None]:
    """Resolve active dossier_id and its set of member file IDs.

    Prioritizes explicit tool argument over context fallback.
    Returns:
        (dossier_id, allowed_file_ids_set) or (None, None) if not scoped.
    """
    dossier_id = args.get("dossier_id") or ctx.dossier_id
    if not dossier_id:
        return None, None

    # Fast path: context already resolved this dossier
    if ctx.allowed_file_ids is not None and (not args.get("dossier_id") or args.get("dossier_id") == ctx.dossier_id):
        return dossier_id, ctx.allowed_file_ids

    # Query storage for dossier items
    try:
        files, _ = ctx.storage.list_dossier_items(dossier_id, limit=1000)
        return dossier_id, {f.id for f in files}
    except Exception as exc:
        logger.warning("Failed to resolve dossier items for '%s': %s", dossier_id, exc)
        return dossier_id, set()


def _handle_search_index(args: dict[str, Any], ctx: AgentToolContext) -> str:
    query = str(args.get("query", "")).strip()
    if not query:
        return json.dumps({"error": "Missing required argument 'query'."})

    dossier_id, allowed_files = _resolve_allowed_files(args, ctx)

    # Fast return if dossier is empty
    if dossier_id and allowed_files is not None and len(allowed_files) == 0:
        return json.dumps({
            "results_count": 0,
            "hits": [],
            "dossier_id": dossier_id,
            "notice": f"Project Dossier '{dossier_id}' contains no indexed documents.",
        })

    settings = get_settings()
    project_tag = args.get("project_tag")
    limit = min(int(args.get("limit", settings.AGENT_DEFAULT_SEARCH_LIMIT)), settings.AGENT_MAX_SEARCH_LIMIT)

    # 1. Try Meilisearch search_service if configured
    if ctx.search_service:
        try:
            res = ctx.search_service.search(
                query=query,
                project_tag=project_tag,
                limit=limit,
                allowed_file_ids=allowed_files,
            )
            hits = [
                {
                    "file_id": h.id,
                    "name": h.name,
                    "mime_type": h.mime_type,
                    "owners": h.owners,
                    "project_tags": h.project_tags,
                    "snippet": h.content_snippet,
                    "modified_time": (
                        h.modified_time.isoformat()
                        if hasattr(h.modified_time, "isoformat")
                        else (str(h.modified_time) if h.modified_time else None)
                    ),
                }
                for h in res.hits
            ]
            response_payload: dict[str, Any] = {"results_count": len(hits), "hits": hits}
            if dossier_id:
                response_payload["dossier_id"] = dossier_id
            return json.dumps(response_payload)
        except Exception as exc:
            logger.warning("SearchService error in tool, falling back to SQLite: %s", exc)

    # 2. SQLite fallback
    files = ctx.storage.list_files(limit=50)
    matched = []
    q_lower = query.lower()
    for f in files:
        if allowed_files is not None and f.id not in allowed_files:
            continue
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

    response_payload = {"results_count": len(matched), "hits": matched}
    if dossier_id:
        response_payload["dossier_id"] = dossier_id
    return json.dumps(response_payload)


def _handle_get_document_diff(args: dict[str, Any], ctx: AgentToolContext) -> str:
    file_id = str(args.get("file_id", "")).strip()
    if not file_id:
        return json.dumps({"error": "Missing required argument 'file_id'."})

    dossier_id, allowed_files = _resolve_allowed_files(args, ctx)
    if dossier_id and allowed_files is not None and file_id not in allowed_files:
        return json.dumps({
            "file_id": file_id,
            "dossier_id": dossier_id,
            "status": "permission_denied",
            "error": f"Access denied: Document '{file_id}' is outside the boundary of Project Dossier '{dossier_id}'.",
        })

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

    settings = get_settings()
    serialized = []
    for d in target_diffs[:3]:
        # Truncate patch text if too long using settings budget
        patch_snippet = d.patch_text[:settings.AGENT_DIFF_SNIPPET_CHARS] if d.patch_text else None
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

    result_payload: dict[str, Any] = {"file_id": file_id, "diffs": serialized}
    if dossier_id:
        result_payload["dossier_id"] = dossier_id
    return json.dumps(result_payload)


def _handle_get_file_metadata(args: dict[str, Any], ctx: AgentToolContext) -> str:
    file_id = str(args.get("file_id", "")).strip()
    if not file_id:
        return json.dumps({"error": "Missing required argument 'file_id'."})

    dossier_id, allowed_files = _resolve_allowed_files(args, ctx)
    if dossier_id and allowed_files is not None and file_id not in allowed_files:
        return json.dumps({
            "file_id": file_id,
            "dossier_id": dossier_id,
            "status": "permission_denied",
            "error": f"Access denied: Document '{file_id}' is outside the boundary of Project Dossier '{dossier_id}'.",
        })

    f = ctx.storage.get_file(file_id)
    if not f:
        return json.dumps({
            "file_id": file_id,
            "status": "not_found",
            "message": f"Document '{file_id}' does not exist in local repository.",
        })

    resp: dict[str, Any] = {
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
    }
    if dossier_id:
        resp["dossier_id"] = dossier_id
    return json.dumps(resp)


def _handle_semantic_chunk_search(args: dict[str, Any], ctx: AgentToolContext) -> str:
    query = str(args.get("query", "")).strip()
    if not query:
        return json.dumps({"error": "Missing required argument 'query'."})

    dossier_id, allowed_files = _resolve_allowed_files(args, ctx)

    # Fast early exit if empty container
    if dossier_id and allowed_files is not None and len(allowed_files) == 0:
        return json.dumps({
            "query": query,
            "chunks_count": 0,
            "chunks": [],
            "dossier_id": dossier_id,
            "notice": f"Project Dossier '{dossier_id}' contains no indexed documents.",
        })

    settings = get_settings()
    limit = min(int(args.get("limit", 3)), settings.AGENT_MAX_CHUNKS_LIMIT)
    file_id = args.get("file_id")

    # If file_id is provided along with a dossier scope, verify file_id is allowed
    if dossier_id and allowed_files is not None and file_id and file_id not in allowed_files:
        return json.dumps({
            "file_id": file_id,
            "dossier_id": dossier_id,
            "status": "permission_denied",
            "error": f"Access denied: Document '{file_id}' is outside the boundary of Project Dossier '{dossier_id}'.",
        })

    provider = ctx.embedding_provider or get_embedding_provider()
    query_vector = provider.embed_query(query)

    # 1. Try Meilisearch native vector index first (<3ms)
    if ctx.search_service:
        try:
            hits = ctx.search_service.search_chunks(
                query_vector=query_vector,
                limit=limit,
                file_id=file_id,
                query_text=query,
                allowed_file_ids=allowed_files,
            )
            if hits:
                results = []
                for h in hits:
                    score = h.get("_rankingScore")
                    score_float = round(float(score), 3) if score is not None else 1.0
                    results.append({
                        "chunk_id": h.get("id"),
                        "file_id": h.get("file_id"),
                        "section_heading": h.get("section_heading"),
                        "similarity_score": score_float,
                        "text": (h.get("content_text") or "")[:settings.AGENT_CHUNK_SNIPPET_CHARS],
                    })
                resp: dict[str, Any] = {
                    "query": query,
                    "engine": "meilisearch_vector",
                    "chunks_count": len(results),
                    "chunks": results,
                }
                if dossier_id:
                    resp["dossier_id"] = dossier_id
                return json.dumps(resp)
        except Exception as exc:
            logger.warning("Meilisearch chunk vector search failed, falling back to SQLite: %s", exc)

    # 2. Resilient fallback: SQLite in-memory cosine scan
    chunks = ctx.storage.search_similar_chunks(
        query_vector=query_vector,
        limit=limit * 2 if allowed_files is not None else limit,
        file_id_filter=file_id,
    )

    results = []
    for chunk, similarity in chunks:
        if allowed_files is not None and chunk.file_id not in allowed_files:
            continue
        results.append({
            "chunk_id": chunk.id,
            "file_id": chunk.file_id,
            "section_heading": chunk.section_heading,
            "similarity_score": round(similarity, 3),
            "text": chunk.content_text[:settings.AGENT_CHUNK_SNIPPET_CHARS],
        })
        if len(results) >= limit:
            break

    resp = {
        "query": query,
        "engine": "sqlite_fallback",
        "chunks_count": len(results),
        "chunks": results,
    }
    if dossier_id:
        resp["dossier_id"] = dossier_id
    return json.dumps(resp)


def _handle_get_document_catalog_stats(args: dict[str, Any], ctx: AgentToolContext) -> str:
    dossier_id, allowed_files = _resolve_allowed_files(args, ctx)
    stats = ctx.storage.get_catalog_stats(allowed_file_ids=allowed_files)
    resp: dict[str, Any] = {
        "status": "success",
        "inventory": stats,
    }
    if dossier_id:
        resp["dossier_id"] = dossier_id
    return json.dumps(resp)


# ------------------------------------------------------------------------------
# Dispatcher
# ------------------------------------------------------------------------------

_TOOL_DISPATCH_TABLE = {
    "get_document_catalog_stats": _handle_get_document_catalog_stats,
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

    settings = get_settings()
    max_chars = settings.AGENT_MAX_TOOL_OUTPUT_CHARS
    if len(raw_output) > max_chars:
        logger.debug("Truncating tool output for '%s' from %d to %d chars", name, len(raw_output), max_chars)
        return raw_output[:max_chars] + '... [output truncated for context limit]"}'

    return raw_output
