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

export interface DocumentResponseItem {
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
}

export interface DocumentListResponse {
  total_count: number;
  limit: number;
  offset: number;
  processing_time_ms: number;
  documents: DocumentResponseItem[];
}

export interface LiveSyncEvent {
  id: string;
  event_type: 'connected' | 'heartbeat' | 'sync_started' | 'sync_progress' | 'sync_completed' | 'sync_failed' | 'file_modified' | 'file_created';
  data: Record<string, any>;
  timestamp: string;
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

export interface DocumentVersion {
  id: string;
  file_id: string;
  version_number: number;
  content_hash: string;
  editor: string | null;
  modified_time: string | null;
  char_count: number;
  word_count: number;
  created_at: string;
}

export interface DocumentDiff {
  id: string;
  file_id: string;
  from_version_id: string | null;
  to_version_id: string;
  patch_text: string;
  ai_summary: string | null;
  lines_added: number;
  lines_removed: number;
  created_at: string;
}

export interface VersionHistoryResponse {
  file_id: string;
  total: number;
  items: DocumentVersion[];
}

export interface DiffListResponse {
  file_id: string;
  total: number;
  items: DocumentDiff[];
}

export interface DossierSummary {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  color: string | null;
  icon: string | null;
  status: string;
  item_count: number;
  member_count: number;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface DossierMemberItem {
  id: string;
  dossier_id: string;
  user_email: string;
  role: string;
  added_at: string;
}

export interface DossierDetail {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  color: string | null;
  icon: string | null;
  status: string;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface DossierCreatePayload {
  name: string;
  slug?: string;
  description?: string;
  color?: string;
  icon?: string;
  initial_file_ids?: string[];
}


