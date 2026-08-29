# Panopticon Backend API Reference & Contract

---

## 1. API Overview & Conventions

The Panopticon FastAPI backend exposes high-speed REST endpoints designed specifically for the React Dashboard.

### 1.1 Base Configuration & Headers
- **Base URL:** `http://localhost:8000` (configurable via `API_HOST` and `API_PORT`)
- **Default Content-Type:** `application/json`
- **CORS Allowed Origins:** `http://localhost:5173`, `http://127.0.0.1:5173` (supports credentials)
- **Response Headers:**
  - `X-Process-Time-Ms`: High-precision float string (e.g. `"4.15"`) representing server processing time in milliseconds.

### 1.2 Authentication Seam
The backend includes a pluggable dependency `CurrentUser` on all protected routes. In local development mode, this resolves to a default local principal (`local-developer@panopticon.internal`). When transitioning to enterprise deployment, this dependency connects to OAuth2/OIDC JWT validation without requiring modifications to route handlers or frontend payload shapes.

---

## 2. Endpoint Reference

### 2.1 Search API

#### `GET /api/search`
Executes typo-tolerant, hybrid document search over Google Docs and Sheets indexed in Meilisearch.

##### Query Parameters
| Parameter | Type | Required | Default | Description | Example |
|---|---|---|---|---|---|
| `q` | `string` | **Yes** | — | Search query string (supports keywords, full titles, and typos). | `Falcn RFC` |
| `mode` | `string` | No | `"fuzzy"` | Search mode: `"fuzzy"` (typo-tolerant), `"tag"` (prioritizes Drive labels), or `"exact"` (strict phrase). | `fuzzy` |
| `file_type` | `string` | No | `null` | Facet filter: `"document"`, `"spreadsheet"`, or `"other"`. | `document` |
| `mime_type` | `string` | No | `null` | Filter by exact Google Workspace MIME type. | `application/vnd.google-apps.document` |
| `sharing_status` | `string` | No | `null` | Filter by sharing scope: `"private"`, `"shared"`, or `"domain"`. | `domain` |
| `project_tag` | `string` | No | `null` | Filter by specific Google Drive Workspace project label tag. | `Falcon` |
| `primary_owner` | `string` | No | `null` | Filter by primary owner email address. | `alex@company.com` |
| `sort_by` | `string` | No | `null` | Sort expression (e.g. `modified_time:desc` or `name:asc`). | `modified_time:desc` |
| `limit` | `integer` | No | `20` | Results per page (min: `1`, max: `100`). | `20` |
| `offset` | `integer` | No | `0` | Pagination offset. | `0` |

##### Successful Response (`200 OK`)
```json
{
  "query": "Falcn",
  "total_hits": 2,
  "processing_time_ms": 11.45,
  "limit": 20,
  "offset": 0,
  "facet_distribution": {
    "file_type": {
      "document": 1,
      "spreadsheet": 1
    },
    "sharing_status": {
      "domain": 1,
      "shared": 1
    }
  },
  "results": [
    {
      "id": "1v8K9_DocFalconIDExample9912",
      "name": "Project Falcon - Architecture & System Design",
      "type": "document",
      "mime_type": "application/vnd.google-apps.document",
      "owner": "alex.architect@company.com",
      "owners": ["alex.architect@company.com"],
      "last_modifying_user": "alex.architect@company.com",
      "modified_time": "2026-08-25T14:30:00Z",
      "created_time": "2026-05-12T08:00:00Z",
      "sharing_status": "domain",
      "shared_with": "domain",
      "project_tags": ["Falcon", "RFC", "Architecture"],
      "snippet": "This document outlines the core architectural blueprint for Project Falcon...",
      "view_url": "https://docs.google.com/document/d/1v8K9_DocFalconIDExample9912/edit",
      "icon_link": "https://drive-thirdparty.googleusercontent.com/16/type/application/vnd.google-apps.document",
      "size_bytes": 45120,
      "export_status": "success",
      "export_links": {
        "pdf": "https://docs.google.com/document/d/1v8K9_DocFalconIDExample9912/export?format=pdf",
        "docx": "https://docs.google.com/document/d/1v8K9_DocFalconIDExample9912/export?format=docx",
        "txt": "https://docs.google.com/document/d/1v8K9_DocFalconIDExample9912/export?format=txt"
      },
      "matched_via": "tag",
      "confidence": "high",
      "highlighted_name": "Project <mark>Falcon</mark> - Architecture & System Design",
      "highlighted_snippet": "This document outlines the core architectural blueprint for Project <mark>Falcon</mark>..."
    }
  ]
}
```

##### Error Responses
- `400 Bad Request`: Invalid parameters (e.g. `limit > 100` or `q` empty).
- `503 Service Unavailable`: Meilisearch engine offline or search index missing.

---

### 2.2 Background Drive Sync & Re-Indexing API

#### `POST /api/sync`
Initiates a background crawler run to discover new/modified Google Drive files, extract project tags, export text snippets, commit to SQLite, and batch-upsert into Meilisearch.

##### Request Body (`application/json`, optional)
```json
{
  "full_refresh": false,
  "export_content": true,
  "page_size": 50
}
```

##### Successful Response (`202 Accepted`)
```json
{
  "status": "started",
  "message": "Background Drive sync job started successfully.",
  "job_id": "sync-20260829-220015",
  "sync_mode": "incremental",
  "started_at": "2026-08-29T22:00:15.123456Z"
}
```

##### Error Responses
- `409 Conflict`: A sync job is already active.
  ```json
  {
    "detail": {
      "error": "sync_in_progress",
      "message": "A synchronization job is already running. Please wait for it to complete."
    }
  }
  ```

---

#### `GET /api/sync/status`
Queries the live telemetry, active phase, and metrics of the synchronization worker. Designed for UI polling.

##### Successful Response (`200 OK`)
```json
{
  "is_syncing": true,
  "job_id": "sync-20260829-220015",
  "sync_mode": "incremental",
  "current_phase": "exporting",
  "progress_message": "Exporting text content (File 12 of 35)...",
  "started_at": "2026-08-29T22:00:15.123456Z",
  "duration_seconds": 4.25,
  "last_sync_time": "2026-08-29T21:45:00Z",
  "last_sync_stats": {
    "sync_mode": "incremental",
    "added": 5,
    "updated": 2,
    "deleted": 0,
    "unchanged": 48,
    "total_stored": 55,
    "total_indexed": 55,
    "duration_seconds": 6.82
  },
  "last_error": null
}
```

##### Pipeline Phases (`current_phase`)
1. `"idle"`: No job running; ready for requests.
2. `"crawling"`: Discovering files via Google Drive API list endpoint.
3. `"exporting"`: Downloading text snippets (respecting 10MB cap).
4. `"updating_sqlite"`: Writing records and watermark timestamp to SQLite database.
5. `"indexing_meilisearch"`: Pushing batch documents into Meilisearch.
6. `"failed"`: Previous job failed with error recorded in `last_error`.

---

#### `POST /api/sync/reindex`
Re-indexes all document records stored in local SQLite into Meilisearch without contacting Google Drive.

##### Successful Response (`202 Accepted`)
```json
{
  "status": "started",
  "message": "Search index rebuild job started successfully.",
  "job_id": "reindex-20260829-220500",
  "started_at": "2026-08-29T22:05:00.000000Z"
}
```

---

### 2.3 Google Drive Authentication Management API

#### `GET /api/auth/config`
Inspects configured credential files, token validity, and active provider mode.

##### Successful Response (`200 OK`)
```json
{
  "auth_mode": "oauth",
  "client_secrets_path": "c:\\Users\\Mubashar\\Desktop\\Panopticon\\credentials.json",
  "client_secrets_found": true,
  "token_cache_path": "c:\\Users\\Mubashar\\Desktop\\Panopticon\\token.json",
  "token_cache_found": true,
  "token_valid": true,
  "token_expired": false,
  "token_expiry": "2026-08-30T04:15:00Z",
  "service_account_path": "c:\\Users\\Mubashar\\Desktop\\Panopticon\\service_account.json",
  "service_account_found": false,
  "delegated_user_email": null,
  "scopes": [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/drive.labels.readonly"
  ]
}
```

---

#### `POST /api/auth/config`
Hot-switches the active Google Drive authentication mode between `"oauth"` and `"service_account"` without restarting the server.

##### Request Body (`application/json`)
```json
{
  "auth_mode": "service_account",
  "delegated_user_email": "admin@company.com"
}
```

##### Successful Response (`200 OK`)
```json
{
  "status": "switched",
  "auth_mode": "service_account",
  "delegated_user_email": "admin@company.com",
  "message": "Drive authentication provider switched to 'service_account'."
}
```

---

#### `POST /api/auth/oauth/start`
Generates a Google OAuth authorization URL for opening in a browser popup.

##### Successful Response (`200 OK`)
```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id=...",
  "state": "a8fbc3948e918237",
  "redirect_uri": "http://localhost:8000/api/auth/oauth/callback"
}
```

---

#### `GET /api/auth/oauth/callback`
Receives the OAuth redirect from Google, writes `token.json`, invalidates the provider cache, and returns an auto-closing HTML window that notifies the opener via `postMessage`:
```javascript
window.opener.postMessage({ type: 'PANOPTICON_OAUTH_SUCCESS' }, '*');
```

---

#### `POST /api/auth/credentials/upload`
Accepts multipart form-data JSON file upload for `credentials.json` (OAuth) or `service_account.json` (Domain-Wide Delegation).

##### Request (Multipart Form-Data)
- `file`: `credentials.json` or `service_account.json`

##### Successful Response (`200 OK`)
```json
{
  "status": "saved",
  "file_type": "credentials",
  "saved_path": "c:\\Users\\Mubashar\\Desktop\\Panopticon\\credentials.json",
  "message": "OAuth Client Secrets (credentials.json) saved successfully."
}
```

---

### 2.4 Health & System Diagnostics API

#### `GET /health`
Basic liveness probe.

##### Successful Response (`200 OK`)
```json
{
  "status": "ok",
  "app_name": "Panopticon",
  "version": "0.1.0",
  "timestamp": "2026-08-29T22:15:00.000000Z",
  "auth_mode": "oauth"
}
```

---

#### `GET /api/system/status`
Comprehensive diagnostics reporting backend state, Meilisearch connectivity, total indexed documents, and process supervisor status.

##### Successful Response (`200 OK`)
```json
{
  "status": "healthy",
  "app_name": "Panopticon",
  "version": "0.1.0",
  "auth_mode": "oauth",
  "api_endpoint": "http://127.0.0.1:8000",
  "meilisearch_connected": true,
  "meilisearch_health": "available",
  "meilisearch_host": "http://127.0.0.1:7700",
  "index_name": "panopticon_documents",
  "document_count": 55,
  "is_indexing": false,
  "is_managed_process": true,
  "process_pid": 14920,
  "details": {
    "meilisearch_version": "1.12.0",
    "supervisor": {
      "is_managed_process": true,
      "process_pid": 14920,
      "binary_path": "c:\\Users\\Mubashar\\Desktop\\Panopticon\\bin\\meilisearch.exe"
    }
  }
}
```

---

## 3. TypeScript Type Definitions (`frontend/src/types/api.ts`)

Frontend developers can directly copy-paste these types into the React application:

```typescript
export type AuthMode = 'oauth' | 'service_account';

export type SyncPhase =
  | 'idle'
  | 'crawling'
  | 'exporting'
  | 'updating_sqlite'
  | 'indexing_meilisearch'
  | 'failed';

export type SyncMode = 'incremental' | 'full_refresh' | 'reindex';

export type MatchedVia = 'tag' | 'title' | 'content' | 'owner';
export type MatchConfidence = 'high' | 'medium' | 'low';
export type SharingStatus = 'private' | 'shared' | 'domain' | 'anyone';
export type DocumentType = 'document' | 'spreadsheet' | 'other';

export interface SearchItemResponse {
  id: string;
  name: string;
  type: DocumentType;
  mime_type: string;
  owner: string;
  owners: string[];
  last_modifying_user: string | null;
  modified_time: string | null;
  created_time: string | null;
  sharing_status: SharingStatus;
  shared_with: string;
  project_tags: string[];
  snippet: string | null;
  view_url: string | null;
  icon_link: string | null;
  size_bytes: number | null;
  export_status: string | null;
  export_links: Record<string, string> | null;
  matched_via: MatchedVia;
  confidence: MatchConfidence;
  highlighted_name: string | null;
  highlighted_snippet: string | null;
}

export interface SearchResponse {
  query: string;
  total_hits: number;
  processing_time_ms: number;
  limit: number;
  offset: number;
  facet_distribution: Record<string, Record<string, number>>;
  results: SearchItemResponse[];
}

export interface SyncStats {
  sync_mode: string;
  added: number;
  updated: number;
  deleted: number;
  unchanged: number;
  total_stored: number;
  total_indexed: number;
  duration_seconds: number;
}

export interface SyncStatusResponse {
  is_syncing: boolean;
  job_id: string | null;
  sync_mode: SyncMode | null;
  current_phase: SyncPhase;
  progress_message: string;
  started_at: string | null;
  duration_seconds: number | null;
  last_sync_time: string | null;
  last_sync_stats: SyncStats | null;
  last_error: string | null;
}

export interface SyncTriggerRequest {
  full_refresh?: boolean;
  export_content?: boolean;
  page_size?: number;
}

export interface SyncTriggerResponse {
  status: string;
  message: string;
  job_id: string;
  sync_mode: SyncMode;
  started_at: string;
}

export interface AuthConfigResponse {
  auth_mode: AuthMode;
  client_secrets_path: string;
  client_secrets_found: boolean;
  token_cache_path: string;
  token_cache_found: boolean;
  token_valid: boolean;
  token_expired: boolean;
  token_expiry: string | null;
  service_account_path: string;
  service_account_found: boolean;
  delegated_user_email: string | null;
  scopes: string[];
}

export interface SystemStatusResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  app_name: string;
  version: string;
  auth_mode: string;
  api_endpoint: string;
  meilisearch_connected: boolean;
  meilisearch_health: string;
  meilisearch_host: string;
  index_name: string;
  document_count: number;
  is_indexing: boolean;
  is_managed_process: boolean;
  process_pid: number | null;
  details: Record<string, unknown>;
}
```

---

## 4. Frontend Integration Patterns & Examples

### 4.1 Debounced Search Hook Pattern
```typescript
import { useState, useEffect } from 'react';
import type { SearchResponse } from '../types/api';

export function useDocumentSearch(query: string, mode = 'fuzzy', tag?: string) {
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!query.trim()) {
      setData(null);
      return;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({ q: query, mode });
        if (tag) params.append('project_tag', tag);

        const res = await fetch(`http://localhost:8000/api/search?${params}`, {
          signal: controller.signal,
        });

        if (!res.ok) throw new Error(`Search failed: HTTP ${res.status}`);
        const result: SearchResponse = await res.json();
        setData(result);
      } catch (err: unknown) {
        if ((err as Error).name !== 'AbortError') {
          setError((err as Error).message);
        }
      } finally {
        setLoading(false);
      }
    }, 250); // 250ms debounce

    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, [query, mode, tag]);

  return { data, loading, error };
}
```

### 4.2 Sync Polling Manager Pattern
```typescript
import { useState, useEffect, useCallback } from 'react';
import type { SyncStatusResponse } from '../types/api';

export function useSyncManager() {
  const [status, setStatus] = useState<SyncStatusResponse | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch('http://localhost:8000/api/sync/status');
      if (res.ok) {
        const data: SyncStatusResponse = await res.json();
        setStatus(data);
      }
    } catch {
      // Degraded connectivity handling
    }
  }, []);

  const triggerSync = async (fullRefresh = false) => {
    const res = await fetch('http://localhost:8000/api/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ full_refresh: fullRefresh, export_content: true }),
    });
    if (res.status === 409) {
      throw new Error('Sync already in progress');
    }
    fetchStatus();
  };

  useEffect(() => {
    fetchStatus();
    // Poll every 1 second when active sync is running, else every 10 seconds
    const intervalTime = status?.is_syncing ? 1000 : 10000;
    const timer = setInterval(fetchStatus, intervalTime);
    return () => clearInterval(timer);
  }, [fetchStatus, status?.is_syncing]);

  return { status, triggerSync, refreshStatus: fetchStatus };
}
```

### 4.3 OAuth Popup Flow Handler
```typescript
export function startGoogleAuthPopup(onSuccess: () => void) {
  fetch('http://localhost:8000/api/auth/oauth/start', { method: 'POST' })
    .then((res) => res.json())
    .then((data) => {
      const popup = window.open(
        data.authorization_url,
        'panopticon_auth',
        'width=600,height=700,status=no,toolbar=no,menubar=no'
      );

      const messageHandler = (event: MessageEvent) => {
        if (event.data?.type === 'PANOPTICON_OAUTH_SUCCESS') {
          window.removeEventListener('message', messageHandler);
          if (popup) popup.close();
          onSuccess();
        }
      };

      window.addEventListener('message', messageHandler);
    });
}
```
