# Practice schedule: move three blocks to their real classrooms

One-off operator that republishes the II/2026 practice schedule (publication 5) with three blocks moved to the correct catalog rooms, effective from a future date, and deactivates the three wrong classroom rows.
Branch `fix/practice-room-codes` (worktree `planilla-docentes-upds-worktrees/practice-room-fix`, base master 13a4df2). Precedent: `deploy/operators/practicas_octubre_2026.py`.

## Specs

- **S1 Room mapping (user answers).** In publication 5 (program 1, II/2026, effective 2026-09-21):
  - Anatomía Humana I, group T-01, Thursday 15:10-17:25, `COB-NUEVO-P3-A1` → "Aula 1 (Antiguo, piso 1)" = `COB-ANTIGUO-P1-A1`.
  - Introducción a la Cirugía I, group N-01, Wednesday 19:10-22:20, `COB-ANTIGUO-P3-A20` → "Sí, es el Aula 20 (Nuevo, piso 3)" = `COB-NUEVO-P3-A20`.
  - Anatomía Humana I, group N-02, Friday 17:30-19:55, `COB-ANTIGUO-P4-A26` → "Sí, es el Aula 26 (Nuevo, piso 4)" = `COB-NUEVO-P4-A26` (created by the admin catalog sync, which must run first).
- **S2 Effective from a future date.** Agent proposal accepted with "ok dale": the new publication is effective from tomorrow (a date `>=` Bolivia today) so October payroll, attendance and billing are untouched; earlier days keep publication 5.
- **S3 Only the rooms change.** Every other block and assignment field of the new publication equals publication 5; the operator proves it before publishing and aborts otherwise.
- **S4 Deactivate the wrong rooms** `COB-NUEVO-P3-A1`, `COB-ANTIGUO-P3-A20`, `COB-ANTIGUO-P4-A26` after the publication, so they stop being reservable.
- **S5 Safe operation.** `preview` rolls everything back and prints the plan; `apply` commits once (all or nothing); rerunning detects completed steps; fail closed on any unexpected state; narrow, documented guard bypass only for the missing historical teacher availability; a pre-migration-style backup is taken before `apply`.

## Tasks

| ID | Specs | Route | Commit |
|----|-------|-------|--------|
| P1 | S1-S5 | gentle-ai-worker: operator `deploy/operators/practice_room_codes_2026_11.py` + tests | |
| P2 | S1-S5 | gentle-ai-verify: independent review (items 1 data, 6) | |
| P3 | S1-S5 | parent: user runs catalog sync; agent runs `preview` on production, then `apply` after backup and the user's go | |

## Log

- **L1** (user): "ok dale" to the agent's catalog review proposal ("¿Querés que arranque por el catálogo? Lo primero sería ver en solo lectura qué horarios publicados usan las aulas duplicadas").
- **L2** (evidence, read-only production queries): publications 1, 2, 3, 5 (II/2026, program 1, practice only); publication 5 effective 2026-09-21 is current. Wrong codes used once each in publication 5 (rows listed in S1). Active period II/2026. Theory classes carry no classroom in SIPAD.
- **L3** (user answers): Aula 1 → "Aula 1 (Antiguo, piso 1)"; Aula 20 → "Sí, es el Aula 20 (Nuevo, piso 3)"; Aula 26 → "Sí, es el Aula 26 (Nuevo, piso 4)".
- **L4** (user): "ok dale" to "¿Querés que prepare el script del paso 2 (clonar la publicación #5, mover las 3 aulas y publicar vigente desde mañana) con backup previo y verificación independiente?"
- **L5** (explore): published drafts cannot be edited; cloned blocks with assignments refuse room changes (`save_schedule_block`); `publish()` requires teacher availability, which II/2026 likely lacks; precedent bypass via `_materialize_publication` with `EXPECTED_BLOCKERS`. Deactivating a classroom has no cascade.
- **L6** (verify finding, fixed): the operator did not check the target rooms for conflicts. `check_preconditions` now aborts (preview and apply, before any write) on a confirmed reservation from the effective date overlapping the moved slot, on a class of another program's effective publication in the target room, or on another publication-5 block already in it.
