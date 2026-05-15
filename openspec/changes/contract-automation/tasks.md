# Contract Automation — Tasks

> Change: `contract-automation`  
> Status: Implemented  
> Commit: `d39624c feat: automate contract rates and dates`

## 1. Backend data model

- [x] 1.1 Add nullable `contract_start_date` and `contract_end_date` to `Designation`.
- [x] 1.2 Add idempotent startup migration for both columns.
- [x] 1.3 Expose contract date fields in designation schemas.

## 2. Backend contract generation

- [x] 2.1 Remove reliance on manual contract rate payload fields.
- [x] 2.2 Resolve rate from `HOURLY_RATE` or `PRACTICE_HOURLY_RATE` per teacher.
- [x] 2.3 Generate numeric and literal Spanish rate values for the existing PDF.
- [x] 2.4 Remove reliance on manual contract date/duration payload fields.
- [x] 2.5 Resolve start/end/duration from active-period designation dates.
- [x] 2.6 Return clear errors for missing or invalid designation dates.

## 3. Backend import/update APIs

- [x] 3.1 Add endpoint for updating designation contract dates from teacher detail.
- [x] 3.2 Parse `FECHA INICIO` and `FECHA FIN` from UPDS official JSON imports.
- [x] 3.3 Preserve existing dates when non-UPDS import formats do not provide contract dates.
- [x] 3.4 Warn and null invalid imported dates instead of crashing the import.

## 4. Frontend UX

- [x] 4.1 Remove manual hourly rate and literal fields from contracts page.
- [x] 4.2 Remove manual duration/start/end fields from contracts page.
- [x] 4.3 Add explanatory contract page note for automatic rates/dates.
- [x] 4.4 Add per-designation contract date editing to teacher detail.
- [x] 4.5 Update TypeScript API types/hooks for contract request changes.

## 5. Verification and cleanup

- [x] 5.1 Fix frontend build blocker (`Clock` unused import).
- [x] 5.2 Clean frontend lint errors enough for `npm run lint` to pass.
- [x] 5.3 Verify `npm run build` passes.
- [x] 5.4 Commit implementation.

## 6. Follow-up candidates

- [ ] 6.1 Add bulk editing for designation contract dates.
- [ ] 6.2 Add automated tests for contract rate/date resolution.
- [ ] 6.3 Replace runtime column migration with formal Alembic migration if the project standard evolves.
