# Phase 2 Frontend - Project Module

## Scope

- Add Vue pages for project module create/list/detail.
- Keep backend business logic unchanged.
- Use only `/api/v1` endpoints.

## Implemented Pages

- `/projects` project list
- `/projects/new` project create
- `/projects/:projectId` project detail

## Feature Coverage

- Project list query by keyword/status.
- Create project record.
- Detail display and operation logs.
- File upload for kml/field_photo/misc_zip/archaeology_report.
- Spatial safety verification trigger.
- Workflow action execution.
- Misc zip download.

## Compatibility

- Existing admin pages remain online.
- Existing old APIs remain online.
- No database or model change.

## Rollback

1. Remove new routes from `frontend/src/router/index.js`.
2. Remove views under `frontend/src/views/projects/` if needed.
3. Keep backend v1 API routes active or disable independently.

## Pending Environment Gap

- Current machine has no Node/npm, frontend runtime build cannot be executed yet.
- Backend check passed and migration files are ready for environments with Node toolchain.
