# Tasks: Medicine Schedule Assistant

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 1,350–1,850 across 31 files (20 new, 11 modified) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | Gate → PR 1 → PR 2 → PR 3 → PR 4 |
| Delivery strategy / chain strategy | ask-on-risk / stacked-to-main |

Workload decision: Resolved; size:exception: not approved.
Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal / likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|
| 0 | Ownership gate approved / no PR | N/A—decision recorded | Engram #4246 boundary | No code changed |
| 1 | Isolated models and dark rollout / PR 1 | `cd backend && pytest tests/test_medicine_schedule_versioning.py` | Admin flag disabled returns 404 | Migration, models, setting/route registration |
| 2 | Schemas and import lifecycle / PR 2 (target ≤400; split API if needed) | `cd backend && pytest tests/test_medicine_schedule_parser.py tests/test_medicine_schedule_versioning.py tests/test_medicine_schedule_api.py` | Upload, correct, accept, activate, restore | Schemas, parser, version service, lifecycle routes/tests |
| 3 | Recommendation and snapshots / PR 3 (target ≤400; split PDF if needed) | `cd backend && pytest tests/test_medicine_schedule_recommendation.py tests/test_medicine_schedule_api.py` | Query, select, archive, download PDF | Engine, PDF, recommendation routes/tests |
| 4 | Admin UI and E2E / PR 4 (target ≤400; split pages if needed) | `cd frontend && npx playwright test e2e/medicine-schedule.spec.ts` | Desktop/mobile mocked import-to-PDF flow | Medicine pages, components, hooks, mocks, E2E |

## Phase 1: Reconciliation and Foundation

- [x] 1.1 Approved boundary (Engram #4246): Medicine owns V1 queries/simulations; `Designation.schedule_json` owns payroll/attendance/designations; no `scheduling-module` adapter, sync, or migration in V1.
- [x] 1.2 Add isolated Medicine models in `backend/app/models/medicine_schedule.py` and additive migration `backend/alembic/versions/d9e4a1b6c2f0_add_medicine_schedule_assistant.py`.
- [x] 1.3 Register models/routes in `backend/app/{models,routers}/__init__.py` and `backend/app/main.py`; add default-disabled `MEDICINE_SCHEDULE_ASSISTANT_ENABLED` through settings service/admin settings.
- [ ] 1.4 Add Medicine API schemas in `backend/app/schemas/medicine_schedule.py` at the start of the next backend work unit, before lifecycle endpoints.

## Phase 2: Import Lifecycle and Recommendation Backend

- [ ] 2.1 Write parser/versioning behavior tests in `backend/tests/test_medicine_schedule_{parser,versioning}.py`: strict workbook, raw/canonical lineage, warning acceptance, error block, atomic activate/restore, audit, and unchanged designation/payroll rows.
- [ ] 2.2 Implement `medicine_schedule_{parser,version_service}.py` with immutable raw cells, corrections/events, active-version locking, `log_activity`, and semester-7 exclusion.
- [ ] 2.3 Write engine/API/PDF tests in `backend/tests/test_medicine_schedule_{recommendation,api}.py`: complete groups, constraints, boundary overlaps, caps, deterministic cursors, roles/404, immutable snapshots, archive/duplicate, and PDF contract.
- [ ] 2.4 Implement `medicine_schedule_recommendation.py`, `medicine_schedule_pdf.py`, and `routers/medicine_schedules.py` for flagged admin APIs, active queries, snapshots, and ReportLab export.

## Phase 3: Admin UI and Verification

- [ ] 3.1 Create `MedicineSchedule{Import,Assistant}Page.tsx`, four `components/medicine-schedule/*` components, and `useMedicineSchedules.ts` for lifecycle, filters, synchronized views, recommendations, and save/archive/PDF.
- [ ] 3.2 Wire routes, safe API root/types, and flag-gated sidebar in `frontend/src/{App.tsx,api/client.ts,api/types.ts,components/layout/Sidebar.tsx,api/hooks/useAppSettings.ts}`.
- [ ] 3.3 Add Playwright mocks in `frontend/e2e/support/api.ts` and flows in `frontend/e2e/medicine-schedule.spec.ts` for correction, disabled semester 7, no-match/error retry, view sync, ranking, snapshot, archive, and PDF.
- [ ] 3.4 Run focused pytest and Playwright suites, `cd frontend && npm run build`, designation/payroll regressions, and dark rollout/flag-disable plus version-restore checks.
