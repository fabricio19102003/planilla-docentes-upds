# Tasks: Medicine Schedule Assistant

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 1,350–1,850 across 31 files (20 new, 11 modified) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | Gate → PR 1 merged → PR 2 → PR 3 → PR 4 → PR 5 → PR 6 |
| Delivery strategy / chain strategy | ask-on-risk / stacked-to-main |

Workload decision: Resolved; size:exception: not approved.
Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal / likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|
| 0 | Ownership gate approved / no PR | N/A | Engram #4246 | No code |
| 1 | Foundation merged / PR 1 | Completed | Flag returns 404 | Merged foundation |
| 2 | Schemas/parser / PR 2 #9 ≤400 | `cd backend && pytest tests/test_medicine_schedule_parser.py` | Valid/invalid XLSX | Schemas/parser/tests |
| 3 | Lifecycle / PR 3 ≤400 | `cd backend && pytest tests/test_medicine_schedule_versioning.py tests/test_medicine_schedule_api.py` | Activate/restore | Service/API/tests |
| 4 | Recommendations/PDF / PR 4 ≤400 | `cd backend && pytest tests/test_medicine_schedule_recommendation.py tests/test_medicine_schedule_api.py` | Select/PDF | Engine/router/PDF/tests |
| 5 | Import UI / PR 5 ≤400 | `cd frontend && npx playwright test e2e/medicine-schedule.spec.ts` | Mocked import | Import/workspace/hooks |
| 6 | Assistant UI/E2E / PR 6 ≤400 | `cd frontend && npx playwright test e2e/medicine-schedule.spec.ts` | Filter-to-PDF | Assistant/routes/mocks |

## Phase 1: Reconciliation and Foundation

- [x] 1.1 Approved boundary (Engram #4246): Medicine owns V1 queries/simulations; `Designation.schedule_json` owns payroll/attendance/designations; no `scheduling-module` adapter, sync, or migration in V1.
- [x] 1.2 Add isolated Medicine models in `backend/app/models/medicine_schedule.py` and additive migration `backend/alembic/versions/d9e4a1b6c2f0_add_medicine_schedule_assistant.py`.
- [x] 1.3 Register models/routes in `backend/app/{models,routers}/__init__.py` and `backend/app/main.py`; add default-disabled `MEDICINE_SCHEDULE_ASSISTANT_ENABLED` through settings service/admin settings.
- [x] 1.4 Add Medicine API schemas in `backend/app/schemas/medicine_schedule.py` before lifecycle endpoints.

## Phase 2: Import Lifecycle and Recommendation Backend

- [x] 2.1 Write strict-parser tests in `backend/tests/test_medicine_schedule_parser.py` for shape, raw cells, coordinates, canonical values, and unsupported files.
- [x] 2.2 Implement only `backend/app/services/medicine_schedule_parser.py`; reject approximate extraction and exclude semester 7.
- [ ] 2.3 Write lifecycle tests in `backend/tests/test_medicine_schedule_{versioning,api}.py` for lineage, warnings/errors, audit, activation/restore, and unchanged designation/payroll.
- [ ] 2.4 Implement `medicine_schedule_version_service.py` and lifecycle routes in `routers/medicine_schedules.py` using the schemas after parser completion.
- [ ] 2.5 Write recommendation/API/PDF tests in `backend/tests/test_medicine_schedule_{recommendation,api}.py` for constraints, ranking, cursors, snapshots, archive, roles/404, and PDF.
- [ ] 2.6 Implement `medicine_schedule_{recommendation,pdf}.py` and remaining `routers/medicine_schedules.py` endpoints.

## Phase 3: Admin UI and Verification

- [ ] 3.1 Create `MedicineScheduleImportPage.tsx`, `VersionWorkspace.tsx`, and import lifecycle hooks in `frontend/src/api/hooks/useMedicineSchedules.ts`.
- [ ] 3.2 Create `MedicineScheduleAssistantPage.tsx` with `ScheduleFilters`, `ScheduleViews`, and `RecommendationResults` components.
- [ ] 3.3 Wire typed client/routes/sidebar and flag gating in `frontend/src/{App.tsx,api/client.ts,api/types.ts,components/layout/Sidebar.tsx,api/hooks/useAppSettings.ts}`.
- [ ] 3.4 Add `frontend/e2e/support/api.ts` mocks and `medicine-schedule.spec.ts` correction, semester 7, retry, sync, ranking, snapshot, archive, and PDF flows.
- [ ] 3.5 Run focused pytest/Playwright, `cd frontend && npm run build`, designation/payroll regressions, flag-disable, and restore checks.
