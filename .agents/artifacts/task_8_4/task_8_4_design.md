# Stage 2: Codebase Design — Task 8.4: React Diff Viewer & Version History Modal

**Task ID:** `8.4`  
**Task Title:** React Diff Viewer & Version History Modal  
**Epic:** Epic 8 — Document Version Diffing & Temporal Change Engine  
**Target Files:**
- Backend API:
  - `[NEW]` [`app/api/schemas/diffs.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/api/schemas/diffs.py)
  - `[MODIFY]` [`app/api/routes/documents.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/api/routes/documents.py)
  - `[MODIFY]` [`tests/test_api_documents.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/tests/test_api_documents.py)
- Frontend UI:
  - `[MODIFY]` [`frontend/src/types/api.ts`](file:///c:/Users/Mubashar/Desktop/Panopticon/frontend/src/types/api.ts)
  - `[NEW]` [`frontend/src/hooks/useVersionHistory.ts`](file:///c:/Users/Mubashar/Desktop/Panopticon/frontend/src/hooks/useVersionHistory.ts)
  - `[NEW]` [`frontend/src/components/diff/DiffViewer.tsx`](file:///c:/Users/Mubashar/Desktop/Panopticon/frontend/src/components/diff/DiffViewer.tsx)
  - `[NEW]` [`frontend/src/components/diff/VersionHistoryModal.tsx`](file:///c:/Users/Mubashar/Desktop/Panopticon/frontend/src/components/diff/VersionHistoryModal.tsx)
  - `[MODIFY]` [`frontend/src/components/directory/DenseDocumentTable.tsx`](file:///c:/Users/Mubashar/Desktop/Panopticon/frontend/src/components/directory/DenseDocumentTable.tsx)
  - `[MODIFY]` [`frontend/src/App.tsx`](file:///c:/Users/Mubashar/Desktop/Panopticon/frontend/src/App.tsx)
**Artifact Version:** 1.0.0  
**Status:** READY FOR IMPLEMENTATION  

---

## 1. Current State Snapshot

In Tasks 8.1–8.3, we built the backend storage and diff engine, and populated `document_versions` and `document_diffs` in SQLite. However:
1. The FastAPI backend does not yet expose REST endpoints to retrieve version snapshots or diff records for a given document.
2. The React frontend table only shows the latest metadata row without any way to click and open a historical diff view or read the AI summary.

---

## 2. Proposed State

Task 8.4 delivers the full visual and data flow:
1. **Backend REST Endpoints (`/api/documents/{file_id}/versions` & `/api/documents/{file_id}/diffs`)**:
   Exposes strongly typed Pydantic models for versions and diff records with pagination support.
2. **Frontend UI Components**:
   - `VersionHistoryModal`: Accessible dialog displaying a timeline list on the left and a syntax-highlighted diff viewer with AI summary badge on the right.
   - `DiffViewer`: Color-coded line additions (`+`), removals (`-`), hunk headers (`@@`), and context lines.
   - `DenseDocumentTable`: History action button to open the modal for any document.

```mermaid
graph TD
    subgraph Frontend ["React 18 Frontend"]
        DenseTable["DenseDocumentTable.tsx\n(Action: History Icon)"]
        Modal["VersionHistoryModal.tsx [NEW]\n(Dual-Pane Dialog)"]
        Viewer["DiffViewer.tsx [NEW]\n(Syntax Highlighter)"]
        Hook["useVersionHistory.ts [NEW]"]
    end

    subgraph Backend ["FastAPI Backend"]
        Route["app/api/routes/documents.py"]
        Schema["app/api/schemas/diffs.py [NEW]"]
        Storage["app/indexer/storage.py"]
    end

    DenseTable -->|Open History| Modal
    Modal --> Hook
    Hook -->|HTTP GET /api/documents/{id}/versions & diffs| Route
    Route --> Schema
    Route --> Storage
    Hook --> Modal
    Modal --> Viewer
```

---

## 3. File-Level Impact Analysis

### Backend

#### `[NEW]` [`app/api/schemas/diffs.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/api/schemas/diffs.py)
- **Purpose:** Public Pydantic API response models for versions and diffs:
  - `DocumentVersionResponse`: `id`, `file_id`, `version_number`, `content_hash`, `editor`, `modified_time`, `char_count`, `word_count`, `created_at`
  - `DocumentDiffResponse`: `id`, `file_id`, `from_version_id`, `to_version_id`, `patch_text`, `ai_summary`, `lines_added`, `lines_removed`, `created_at`
  - `VersionHistoryResponse`: `items`, `total`, `file_id`
  - `DiffListResponse`: `items`, `total`, `file_id`

#### `[MODIFY]` [`app/api/routes/documents.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/app/api/routes/documents.py)
- **What changes:** Add two endpoints:
  - `GET /api/documents/{file_id}/versions`: Calls `storage.get_version_history(file_id, limit, offset)` and `storage.count_versions(file_id)`.
  - `GET /api/documents/{file_id}/diffs`: Calls `storage.get_diffs(file_id, limit, offset)` and `storage.count_diffs(file_id)`.
- **Why:** Provide clean, typed JSON contracts for frontend consumption.

#### `[MODIFY]` [`tests/test_api_documents.py`](file:///c:/Users/Mubashar/Desktop/Panopticon/tests/test_api_documents.py)
- **What changes:** Add test cases testing `GET /api/documents/{file_id}/versions` and `GET /api/documents/{file_id}/diffs` with 200 OK and 404 Not Found handling.

---

### Frontend

#### `[MODIFY]` [`frontend/src/types/api.ts`](file:///c:/Users/Mubashar/Desktop/Panopticon/frontend/src/types/api.ts)
- **What changes:** Add TypeScript interfaces for `DocumentVersion`, `DocumentDiff`, `VersionHistoryResponse`, `DiffListResponse`.

#### `[NEW]` [`frontend/src/hooks/useVersionHistory.ts`](file:///c:/Users/Mubashar/Desktop/Panopticon/frontend/src/hooks/useVersionHistory.ts)
- **Purpose:** Custom React hook managing asynchronous fetching of versions and diffs for a given `fileId`, tracking active selected diff, loading states, and error retries.

#### `[NEW]` [`frontend/src/components/diff/DiffViewer.tsx`](file:///c:/Users/Mubashar/Desktop/Panopticon/frontend/src/components/diff/DiffViewer.tsx)
- **Purpose:** Syntax-highlighted unified diff renderer with AI summary badge, line additions/deletions, hunk indicators, line count badges, and empty/single-snapshot state notices.

#### `[NEW]` [`frontend/src/components/diff/VersionHistoryModal.tsx`](file:///c:/Users/Mubashar/Desktop/Panopticon/frontend/src/components/diff/VersionHistoryModal.tsx)
- **Purpose:** Accessible modal dialog (Escape listener, backdrop, close button, dual-pane layout) rendering the revision list timeline on the left and `DiffViewer` on the right.

#### `[MODIFY]` [`frontend/src/components/directory/DenseDocumentTable.tsx`](file:///c:/Users/Mubashar/Desktop/Panopticon/frontend/src/components/directory/DenseDocumentTable.tsx)
- **What changes:** Add `onViewHistory(doc)` prop and render a History revision icon button in the action column.

#### `[MODIFY]` [`frontend/src/App.tsx`](file:///c:/Users/Mubashar/Desktop/Panopticon/frontend/src/App.tsx)
- **What changes:** Add state `activeHistoryDoc: DriveDocument | null` and conditionally render `VersionHistoryModal` when active.

---

## 4. Regression Risk Matrix

| Risk ID | Risk Description | Severity | Affected Area | Mitigation Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **R-01** | Empty diff list on documents with only 1 version snapshot | 🟢 Low | `DiffViewer.tsx` | Show clear informative banner: *"Initial version snapshot. Future modifications in Drive will appear here."* |
| **R-02** | Keyboard navigation trap or accessibility violations | 🟢 Low | `VersionHistoryModal.tsx` | Follow Vermeer 10-heuristic checklist: `role="dialog"`, `aria-modal="true"`, `Escape` keydown handler. |
| **R-03** | Missing / non-existent `file_id` on API lookup | 🟢 Low | `documents.py` | Return 404 with standard RFC 7807 problem details if file not found in storage. |

---

## 5. Rollback Plan

### If Changes Are Uncommitted:
```bash
git checkout -- app/api/routes/documents.py frontend/src/ frontend/src/App.tsx tests/test_api_documents.py
rm app/api/schemas/diffs.py frontend/src/components/diff/ frontend/src/hooks/useVersionHistory.ts
```

### If Changes Are Committed:
```bash
git revert HEAD --no-edit
pytest tests/
npm run build --prefix frontend
```
