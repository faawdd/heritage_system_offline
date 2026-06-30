# Phase 2 - Project Module Migration (In Progress)

## Goal

Migrate project-management module APIs into `/api/v1` with zero behavior drift.

## Strategy

- Keep old APIs online.
- Reuse existing Django view functions for write/file/flow endpoints.
- Avoid rewriting business logic, permissions, upload/download, spatial checks.

## Implemented

The following `/api/v1` endpoints are now wired directly to existing project APIs:

- `GET /api/v1/projects/`
- `GET /api/v1/projects/<uuid:project_id>/`
- `POST /api/v1/projects/create/`
- `POST /api/v1/projects/<uuid:project_id>/upload/`
- `GET /api/v1/projects/<uuid:project_id>/download-misc-zip/`
- `POST /api/v1/projects/<uuid:project_id>/verify-spatial-safety/`
- `GET /api/v1/projects/next-shanshan-doc/`
- `POST /api/v1/projects/<uuid:project_id>/workflow-action/`
- `GET /api/v1/projects/<uuid:project_id>/controls/`

## Why This Is Safe

- Database schema unchanged.
- Model fields unchanged.
- FastAPI unchanged.
- Existing API behavior reused rather than reimplemented.

## Rollback

If needed, remove project routes from `core/api/urls.py` and keep old `/api/land-projects/*` endpoints only.

## Next

- Add Vue project detail/workflow pages.
- Add module regression test cases for project create/upload/workflow transitions.
