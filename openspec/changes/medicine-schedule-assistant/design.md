# Design: Medicine Schedule Assistant

## Technical Approach

Add an admin-only `/api/medicine-schedules` compatibility slice beside the existing designation/payroll pipeline. It imports the referenced workbook with in-process `openpyxl`, but never writes `Designation`, `Designation.schedule_json`, teachers, attendance, or payroll data. Medicine tables are authoritative only for Medicine queries and simulations in V1. `Designation.schedule_json` remains authoritative for designations, attendance, and payroll; unchanged `scheduling-module` does not govern Medicine in V1. No adapter, sync, or migration crosses these boundaries in V1; any future migration requires a separate OpenSpec change.

## Architecture Decisions

| Option | Tradeoff | Decision and rationale |
|---|---|---|
| Reuse `Designation` | Less storage, but silently changes payroll truth | Reject; isolated Medicine tables preserve approved authority. V1 has no adapter, sync, or migration; future migration requires a separate OpenSpec change. |
| Mutable import rows | Simple, but destroys lineage | Store immutable raw cells/source coordinates plus corrected canonical fields and append-only issues, corrections, and events. Lock data after activation. |
| Persist every candidate | Easy paging, excessive transient data | Deterministically recompute bounded candidates; persist only the selected immutable snapshot. |
| Existing `ActivityLog` only | Familiar, insufficient domain reconstruction | Keep domain events transactionally and mirror lifecycle summaries through `log_activity`. |

## Data Flow

```text
XLSX → parser/validator → preview version → corrections/acceptance → atomic activation
                                      admin query → recommendation engine → selected snapshot → PDF
```

The parser stores workbook SHA-256, parser schema version, file path, raw cell payload, and canonical offering/meeting values. `MedicineScheduleVersion` owns `MedicineOffering` (category `regular|convalidacion`, semester, subject key, group, shift) and its complete `MedicineMeeting` set (activity, teacher key, day, start/end). Semester 7 is represented as unsupported and never extracted; Convalidación has its own category and can be queried with regular semesters.

`MedicineImportIssue` records severity/code/location/state; `MedicineCorrection` records field, before/after, actor/time; `MedicineVersionEvent` records upload, acceptance, correction, activation, and restore. A PostgreSQL partial unique index on `is_active=true`, plus transactional row locking, enforces one active version. Restore reactivates an already validated, locked version without deleting or cloning history.

## Interfaces / Contracts

Admin APIs: `POST /versions` (multipart), `GET /versions[/{id}]`, `POST /versions/{id}/corrections`, `/warning-acceptances`, `/activate`, `/restore`; `GET /active/offerings`; `POST /recommendations`; `POST/GET /simulations`, `GET /simulations/{id}`, `POST /simulations/{id}/duplicate|archive`, and `GET /simulations/{id}/pdf`. Every route uses `require_admin`; disabled feature routes return 404.

Recommendation input contains source version, mandatory/optional subject keys, shifts, unavailable windows, forced/excluded groups/teachers, conflict-count/duration limits, and equal-weight day/time/group/teacher preference predicates. Contradictions return 422. The pure engine first removes hard-constraint violations, builds one complete group per included subject, and admits only positive-duration overlaps within both limits (touching endpoints are allowed). Rank key is `(conflicts ASC, overlap_minutes ASC, optional_count DESC, preference_matches DESC, gap_minutes ASC, distinct_groups ASC, fingerprint ASC)`. Canonical JSON, workbook hash, and `engine_version` produce the fingerprint. Caps are 12 mandatory subjects, 8 optionals, 20 groups/subject, and 50,000 explored candidates; excess returns 422 rather than partial rankings. Stateless signed cursors bind version/input/engine hash and offset; pages contain 10, maximum 100, without reordering.

Snapshots store name/note, canonical inputs, exact selected result/meetings, metrics, warnings, hashes, source version, engine version, creator/time. Selection payload is immutable; archive metadata is append-only audited lifecycle state. Duplicate returns an unsaved editable input draft. PDF reads only the snapshot and includes period, subjects/groups, weekly calendar, gaps, conflicts, and warnings using ReportLab.

## File Changes

| Files | Action | Description |
|---|---|---|
| `backend/app/{models,schemas}/medicine_schedule.py`, `backend/app/services/medicine_schedule_{parser,version_service,recommendation,pdf}.py`, `backend/app/routers/medicine_schedules.py`, `backend/alembic/versions/d9e4a1b6c2f0_add_medicine_schedule_assistant.py` | Create | Domain, parser, engine, PDF, API, migration. |
| `backend/app/{models,routers}/__init__.py`, `backend/app/main.py`, `backend/app/services/app_settings_service.py`, `backend/app/routers/admin_settings.py` | Modify | Register slice and default-disabled `MEDICINE_SCHEDULE_ASSISTANT_ENABLED`. |
| `frontend/src/pages/MedicineSchedule{Import,Assistant}Page.tsx`, `frontend/src/components/medicine-schedule/{VersionWorkspace,ScheduleFilters,ScheduleViews,RecommendationResults}.tsx`, `frontend/src/api/hooks/useMedicineSchedules.ts` | Create | Admin import/query/simulation workflow. |
| `frontend/src/{App.tsx,api/client.ts,api/types.ts}`, `frontend/src/components/layout/Sidebar.tsx`, `frontend/src/api/hooks/useAppSettings.ts` | Modify | Routes, safe return root, types, flag-gated navigation. |
| `backend/tests/test_medicine_schedule_{parser,versioning,recommendation,api}.py`, `frontend/e2e/medicine-schedule.spec.ts` | Create | Automated coverage. |
| `frontend/e2e/support/api.ts` | Modify | Admin API mocks. |

## Testing Strategy

| Layer | Approach |
|---|---|
| Unit | Pytest parser fixtures and engine boundary, rank, gap, cap, hash reproducibility tests. |
| Integration | SQLite/FastAPI tests for roles, lineage, activation race/rollback, restore, immutability, PDF contract, and the invariant that Medicine operations never change designation, attendance, or payroll rows. |
| E2E | Playwright desktop/mobile mocked flows for preview correction, disabled semester 7, synchronized views, ranking, save/archive/PDF; no frontend unit runner. |

## Threat Matrix

N/A — HTTP routing and in-process workbook parsing add no documentation execution, Git selection/state, push, PR, shell, subprocess, executable-file classification, or process-integration boundary.

## Migration / Rollout

Deploy additive tables and code dark; validate the approved coexistence boundary with parser fixtures and payroll/designation regression tests, then enable the default-disabled app setting globally for the deployment/environment so every administrator authorized by `require_admin` can use the feature. Monitor structured version/input hash, issue counts, candidate/prune counts, cap failures, latency, and audit events. Rollback disables the flag and restores a prior active Medicine version; legacy payroll remains untouched. Retain tables/audits; downgrade only before production data exists.

## Open Questions

None.
