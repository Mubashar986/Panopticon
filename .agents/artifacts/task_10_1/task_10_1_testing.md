# Stage 4 Testing & Verification: Task 10.1 — Project Dossiers Domain Model, Relational Schema & CRUD APIs

## Section 1: Pre-Test Environment Checklist

1. **Python Environment**: Confirm virtual environment is activated and dependencies (`pydantic>=2.0.0`, `fastapi>=0.110.0`, `pytest>=8.0.0`, `httpx>=0.27.0`) are installed.
2. **Git Branch**: Confirm active branch is `feat/task-10.1-project-dossiers`.
3. **Database State**: SQLite schema migration executes automatically via `init_db()` in `CrawlStorage` on first access.

---

## Section 2: Test Matrix & Verification Commands

### Automated Test Suite Execution

To execute the unit and integration tests created for this task, the user may run:

```bash
# Run isolated Dossiers storage repository tests
pytest tests/test_dossiers_storage.py -v

# Run Dossiers REST API endpoint integration tests
pytest tests/test_api_dossiers.py -v

# Run full project test suite to verify zero regressions across existing endpoints
pytest tests/ -v
```

### Test Case Coverage Matrix

| Test Suite | Test Case | Target / Function | Expected Outcome | Category |
|---|---|---|---|---|
| `test_dossiers_storage.py` | `test_dossier_create_and_get` | `CrawlStorage.create_dossier`, `get_dossier`, `get_dossier_by_slug` | Dossier created with UUID prefix `dos_`, URL-safe slug, default admin member registered | Unit |
| `test_dossiers_storage.py` | `test_dossier_slug_collision_resolution` | `CrawlStorage.create_dossier` | Identical titles resolve to `-2`, `-3` without collision | Unit |
| `test_dossiers_storage.py` | `test_dossier_list_with_aggregations` | `CrawlStorage.list_dossiers` | Paginated summaries return exact item and member count aggregations, status filtering works | Unit |
| `test_dossiers_storage.py` | `test_dossier_update` | `CrawlStorage.update_dossier` | Fields updated, timestamps updated, returns updated entity | Unit |
| `test_dossiers_storage.py` | `test_dossier_delete_cascade_and_file_preservation` | `CrawlStorage.delete_dossier` | Cascade removes items/members; underlying `file_records` preserved intact | Integrity |
| `test_dossiers_storage.py` | `test_dossier_items_management` | `add_dossier_items`, `list_dossier_items`, `remove_dossier_item` | Idempotent insertion (`INSERT OR IGNORE`), accurate total counts, clean removal | Unit |
| `test_dossiers_storage.py` | `test_dossier_members_management` | `add_dossier_member`, `remove_dossier_member`, `list_dossier_members` | Upsert member role (`viewer` $\rightarrow$ `editor`), clean deletion | Unit |
| `test_api_dossiers.py` | `test_create_dossier_endpoint` | `POST /api/dossiers` | Returns `201 Created` with `DossierResponse` shape | Contract / API |
| `test_api_dossiers.py` | `test_create_dossier_validation_error` | `POST /api/dossiers` (empty name) | Returns `422 Unprocessable Entity` | Validation |
| `test_api_dossiers.py` | `test_list_dossiers_endpoint` | `GET /api/dossiers` | Returns `200 OK` with `DossierListResponse` | Contract / API |
| `test_api_dossiers.py` | `test_get_dossier_by_id_and_by_slug` | `GET /api/dossiers/{id}` | Resolves both UUID and slug, returns details, populated files, and members | Contract / API |
| `test_api_dossiers.py` | `test_get_dossier_not_found` | `GET /api/dossiers/{unknown}` | Returns `404 Not Found` | Error Handling |
| `test_api_dossiers.py` | `test_update_dossier_endpoint` | `PATCH /api/dossiers/{id}` | Returns `200 OK` with updated attributes | Contract / API |
| `test_api_dossiers.py` | `test_delete_dossier_endpoint` | `DELETE /api/dossiers/{id}` | Returns `204 No Content` | Contract / API |
| `test_api_dossiers.py` | `test_add_and_remove_items_endpoint` | `POST/DELETE /api/dossiers/{id}/items` | Associating and dissociating files returns `200 OK` | Contract / API |
| `test_api_dossiers.py` | `test_members_management_endpoints` | `POST/DELETE /api/dossiers/{id}/members` | Adding and removing members returns `200 OK` (404 on missing member) | Contract / API |

---

## Section 3: Static Code Quality & Constraints Audit

- **Constraint 1 (Drive Auth Seam)**: Passed. Zero auth provider or OAuth logic touched.
- **Constraint 2 (Pointer-only Index)**: Passed. Items return `DocumentResponseItem` pointers (title, metadata, view URL, snippet) — no document bodies.
- **Constraint 3 (Search against local index only)**: Passed. Queries hit local SQLite relational tables only.
- **Constraint 4 (Untrusted Input)**: Passed. `sanitize_string()` applied across all dossier names, slugs, descriptions, and file IDs.
- **Constraint 6 (Pluggable API Auth)**: Passed. Endpoints depend on `CurrentUser` dependency (`app/api/deps.py`).
- **Constraint 9 (No Secrets)**: Passed. Zero credentials or keys in schema or responses.

---

## Section 4: Completion Summary

Task 10.1 is fully implemented and statically verified:
- `app/indexer/models.py`: Domain models added (`Dossier`, `DossierItem`, `DossierMember`, `DossierSummary`, `slugify`).
- `app/indexer/storage.py`: SQLite schemas for `dossiers`, `dossier_items`, `dossier_members` and complete CRUD repository methods added.
- `app/api/schemas/dossiers.py`: Request and response DTO schemas created.
- `app/api/routes/dossiers.py`: REST routes implemented with full validation.
- `app/api/routes/__init__.py`: Registered `dossiers_router`.
- `tests/test_dossiers_storage.py` & `tests/test_api_dossiers.py`: Comprehensive test suites created.
