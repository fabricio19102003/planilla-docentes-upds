# Tasks: Medicine Schedule Assistant

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 1,350–1,850 across 31 files (20 new, 11 modified) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1/2 merged → PR 3 → PR 4 → PR 5 → PR 6 → PR 7 |
| Delivery strategy / chain strategy | ask-on-risk / stacked-to-main |

Workload decision: Resolved; size:exception: not approved.
Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal / likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|
| 0 | Gate approved/no PR | N/A | Engram #4246 | N/A |
| 1 | Foundation merged/PR 1 | Completed | Flag 404 | Merged |
| 2 | Schemas/parser merged / PR 2 | Completed | Valid/invalid XLSX | Merged |
| 3 | Version service / PR 3 #11 ≤400 | `cd backend && pytest tests/test_medicine_schedule_versioning.py` | Service activate/restore | Service/tests |
| 4 | Lifecycle endpoints / PR 4 ≤400 | `cd backend && pytest tests/test_medicine_schedule_api.py` | HTTP lifecycle | Routes/API tests |
| 5 | Recommendations/PDF / PR 5 ≤400 | `cd backend && pytest tests/test_medicine_schedule_recommendation.py` | Select/PDF | Engine/router/PDF/tests |
| 6 | Import UI / PR 6 ≤400 | `cd frontend && npx playwright test e2e/medicine-schedule.spec.ts` | Mocked import | Import/workspace/hooks |
| 7 | Assistant UI/E2E / PR 7 ≤400 | `cd frontend && npx playwright test e2e/medicine-schedule.spec.ts` | Filter-to-PDF | Assistant/routes/mocks |

## Phase 1: Reconciliation and Foundation

- [x] 1.1 Approved V1 source boundary; see Engram #4246.
- [x] 1.2 Add models/migration in `backend/app/models/medicine_schedule.py` and `backend/alembic/versions/d9e4a1b6c2f0_add_medicine_schedule_assistant.py`.
- [x] 1.3 Register routes and flag in `backend/app/main.py`.
- [x] 1.4 Add schemas in `backend/app/schemas/medicine_schedule.py`.

## Phase 2: Import Lifecycle and Recommendation Backend

- [x] 2.1 Write strict-parser tests in `backend/tests/test_medicine_schedule_parser.py` for shape, raw cells, coordinates, canonical values, and unsupported files.
- [x] 2.2 Implement only `backend/app/services/medicine_schedule_parser.py`; reject approximate extraction and exclude semester 7.
- [x] 2.3 Write version-service tests in `backend/tests/test_medicine_schedule_versioning.py` for lineage, validation, audit, locking, restore, and unchanged designation/payroll.
- [x] 2.4 Implement only `backend/app/services/medicine_schedule_version_service.py` for corrections, acceptance, activation, and restoration.
- [ ] 2.5 Write lifecycle route tests in `backend/tests/test_medicine_schedule_api.py` for roles, flag 404, upload, corrections, acceptance, activation, and restore.
- [ ] 2.6 Implement lifecycle endpoints in `backend/app/routers/medicine_schedules.py` after version-service completion.
- [ ] 2.7 Write recommendation/API/PDF tests in `backend/tests/test_medicine_schedule_{recommendation,api}.py` for constraints, ranking, cursors, snapshots, archive, roles, and PDF.
- [ ] 2.8 Implement `medicine_schedule_{recommendation,pdf}.py` and remaining `routers/medicine_schedules.py` endpoints.

## Phase 3: Admin UI and Verification

- [ ] 3.1 Create `frontend/src/{pages/MedicineScheduleImportPage.tsx,components/medicine-schedule/VersionWorkspace.tsx,api/hooks/useMedicineSchedules.ts}`.
- [ ] 3.2 Create `frontend/src/{pages/MedicineScheduleAssistantPage.tsx,components/medicine-schedule/{ScheduleFilters,ScheduleViews,RecommendationResults}.tsx}`.
- [ ] 3.3 Wire typed client/routes/sidebar and flag gating in `frontend/src/{App.tsx,api/client.ts,api/types.ts,components/layout/Sidebar.tsx,api/hooks/useAppSettings.ts}`.
- [ ] 3.4 Add `frontend/e2e/{support/api.ts,medicine-schedule.spec.ts}` correction, semester 7, retry, sync, ranking, snapshot, archive, and PDF flows.
- [ ] 3.5 Run pytest/Playwright, `cd frontend && npm run build`, designation/payroll regressions, flag-disable, and restore checks.
