# Proposal: Contract Automation

## Intent

The intent of this change is to make contract generation reliable for both theory and practice teachers by removing manual contract rate/date entry from the contracts screen and deriving those values from authoritative system data. Contract text remains unchanged; only the data injected into the existing PDF template becomes automatic.

## Scope

### In Scope
- Automatically resolve contract hourly rate from admin configuration:
  - `HOURLY_RATE` for theory or mixed teachers.
  - `PRACTICE_HOURLY_RATE` for teachers whose active-period designations are all practice assignments.
- Persist contract start/end dates at the `Designation` level, because assignments can be reassigned when a teacher resigns.
- Allow admins to edit contract start/end dates per designation from teacher detail.
- Import `FECHA INICIO` and `FECHA FIN` from UPDS official designation JSON files into designation contract dates.
- Generate contract duration and date text automatically for the existing ReportLab contract PDF.
- Clean frontend build/lint blockers encountered during the change.

### Out of Scope
- Changing the legal contract text/template.
- Creating separate contract templates for theory and practice teachers.
- Modeling resignation/reassignment history as a separate workflow.
- Bulk editing designation contract dates.
- Reworking the larger lint architecture beyond minimal safe cleanup.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/models/designation.py` | Modified | Adds `contract_start_date` and `contract_end_date`. |
| `backend/app/main.py` | Modified | Adds idempotent runtime migration for new designation date columns. |
| `backend/app/routers/contracts.py` | Modified | Resolves automatic rates, dates, and duration before generating PDFs. |
| `backend/app/routers/teachers.py` | Modified | Adds endpoint to update contract dates per designation. |
| `backend/app/services/designation_loader.py` | Modified | Imports UPDS `FECHA INICIO`/`FECHA FIN` into designations. |
| `frontend/src/pages/ContractsPage.tsx` | Modified | Removes manual rate/date fields and explains automatic sources. |
| `frontend/src/pages/TeacherDetailPage.tsx` | Modified | Adds per-designation contract date editing. |
| Frontend lint/build files | Modified | Minimal cleanup so `npm run lint` and `npm run build` pass. |

## Approach

We keep `Designation` as the current assignment boundary. This is the right place for contract dates because a teacher may leave and the same subject/group can later be assigned to another teacher with different contract dates. Contract generation derives a teacher-level contract window from the teacher's active-period designations:

1. Validate every active-period designation has both contract dates.
2. Use the minimum `contract_start_date` as the contract start.
3. Use the maximum `contract_end_date` as the contract end.
4. Generate Spanish date strings and duration text for the unchanged PDF template.
5. Resolve the hourly rate per teacher using configured settings and designation type.

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Existing designations lack contract dates, blocking contract generation. | High | Clear error messages identify missing designation dates; UPDS JSON import now fills dates when present. |
| Mixed theory/practice teachers require two rates in one contract. | Medium | Current rule intentionally treats mixed teachers as theory to avoid ambiguous single-rate contract text. |
| Runtime column migrations drift from proper migration history. | Medium | Added idempotent startup migration consistent with existing project pattern; future Alembic migration can formalize it. |

## Rollback Plan

Revert the contract automation commit. Existing contract PDF generation will return to manual rate/date inputs. The added nullable database columns are non-destructive and can remain unused or be dropped in a follow-up migration if needed.

## Success Criteria

- [x] Contract generation no longer accepts manual rate/date inputs from the frontend.
- [x] Practice-only teachers receive the configured practice hourly rate in the contract.
- [x] Theory or mixed teachers receive the configured theory hourly rate in the contract.
- [x] Contract start/end dates come from designation-level data.
- [x] UPDS official JSON imports populate designation contract dates when `FECHA INICIO`/`FECHA FIN` exist.
- [x] `npm run lint` passes.
- [x] `npm run build` passes.
