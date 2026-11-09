# Fast individual contract issuing with a teacher combobox

Opening the individual contract form takes ~13 s because the contract terms of one teacher recompute the whole institution's schedule day by day; fix the cause without changing any payroll result, and replace the generic teacher Select with a coss Combobox.
Branch `fix/contract-issue-dialog-speed` (worktree `planilla-docentes-upds-worktrees/contract-issue-speed`, base master 6999dae). No migration: the agent deployer can deploy it.

## Specs

- **S1 Fast opening.** "en el modulo de contratos en sipad admin al momento querer emitir un contrato individual con fechas se tarda en abrir y eso no me gusta revisa porque pasa y solucionalo". Choosing a teacher in "Emitir contrato individual" must show the date fields quickly: `GET /api/contracts/terms/{ci}` (and `POST /api/contracts/issue/{ci}`) must stop resolving the institution's schedule once per day of the period.
- **S2 Identical results.** Contract snapshots, contract terms and every payroll/planilla/attendance output that uses `payroll_schedule_sources` must be identical before and after (proved by tests and by a differential run on a restored production copy).
- **S3 Teacher combobox.** "quiero que usemos otro tipo de select que no sea el generico para seleccion un docente para elegir sun contrato individual, usa un combo box de shadcn o coss ui". The individual contract teacher picker is a coss Combobox with search by name or CI.
- **S4 Visible progress.** While the teacher's terms load, the card shows a loading state instead of nothing.

## Tasks

| ID | Specs | Route | Commit |
|----|-------|-------|--------|
| T1 | S1, S2 | gentle-ai-worker: resolve schedule sources from data loaded once per period, tests | 3df76a0 |
| T2 | S3, S4 | gentle-ai-worker (parallel, disjoint surfaces): combobox + loading state, node tests | 0f2adc9 |
| T3 | S1, S2 | parent: differential run old vs new on a restored production copy; gentle-ai-verify (payroll item 1/6) | 3df76a0, 0f2adc9 |
| T4 | all | parent: PR, merge, deploy with the agent deployer, timing in production | |

## Log

- **L1** (user): "ok perfecto ahora quiero que en el modulo de contratos en sipad admin al momento querer emitir un contrato individual con fechas se tarda en abrir y eso no me gusta revisa porque pasa y solucionalo, tambien quiero que usemos otro tipo de select que no sea el generico para seleccion un docente para elegir sun contrato individual, usa un combo box de shadcn o coss ui"
- **L2** (explore): the "Emitir contratos" Sheet renders `IndividualContractCard` with a coss `Select` of up to 500 teachers; the date fields appear only after `GET /contracts/terms/{ci}` returns. That route calls `build_contract_snapshot` without `schedule_sources_cache`; `payroll_schedule_sources` loops over every day of the period calling `effective_schedule_slots`, which reloads all publications and all designations each time. PR #198 shares a cache only in the batch path.
- **L3** (measurement, production, read-only, 2026-11-09): `build_contract_snapshot` for three teachers of II/2026 took 13.24 s, 14.37 s and 12.75 s; each made 368 `effective_schedule_slots` calls and 752 SQL statements.
- **L4** (evidence): T1 RED 3 failed (362 period loads), GREEN 20 + 2 regression tests (issue route ≤2 loads; invalid legacy hours raise on the same days); terms route 745 → 23 statements. T2 RED on missing lib then 8/8; every frontend check green.
- **L5** (differential, local Postgres 16 restored from a fresh production dump): old 6999dae vs new branch over 533 outputs (payroll_schedule_sources II/2026 and I/2026 theory/practice; cut-off windows Aug-Nov 2026 with explicit_cutoff; effective_schedule_slots every day of II/2026 with and without practice; build_contract_snapshot for every II/2026 teacher): byte-identical (sha256 1773baac…); whole run 43.0 s → 21.6 s. One teacher without cache: 7.3-10.4 s → 2.2-2.3 s.
- **L6** (verify): S1-S4 PASS, no blockers; advisories A1 (block/assignment order inside a publication is unordered in SQL, unchanged from baseline), A2 (one call now reads a consistent snapshot), A3 (combobox trigger shows the placeholder if the selected teacher leaves the list).
- **L7** (evidence): first full suite run collided with concurrent short runs sharing the default SQLite test file (33 errors, the failing file passes 11/11 alone on branch and master); rerun alone with an isolated database: 1670 passed / 0 failed.
