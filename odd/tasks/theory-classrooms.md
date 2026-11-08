# Theory classes mark their classroom as occupied

Store the classroom of each theory designation (filled from the designation workbook's AULA column, editable in Designaciones) and use it only for classroom occupancy, so classroom reservations see theory classes. Payroll never reads it.
Branch `feat/theory-classrooms` (worktree `planilla-docentes-upds-worktrees/theory-classrooms`, base master 13a4df2, Alembic head b5c7d9e1f3a6). Delivery: feature-branch-chain (cached from the reservations feature). Deploy needs the supervised migration flow.

## Specs

- **S1 Theory occupancy.** "ok resolvamos lo de las clases de teoria primero" (context: "las aulas que se encuentren ocupadas por clases deben de etiquetarse como ocupadas"). Every effective theory slot of a designation with a classroom marks that classroom busy in the reservation views (`/availability`, `/day`) with label "Ocupada" and the subject as detail, and `POST` reservations overlapping it are rejected with the existing class-conflict message. Designations without a classroom mark nothing.
- **S2 Storage, payroll untouched.** "Sí, opción B (recomendado)": a nullable `designations.classroom_id` (FK classrooms, ON DELETE SET NULL). No payroll, attendance, contract or billing code reads it; their outputs stay identical.
- **S3 Importer in Designaciones.** "Importador en Designaciones (recomendado)": the admin uploads the designation workbook, sees a preview (which classroom each designation of the active period gets, rows that do not match a designation, AULA values that are not in the catalog, designations without a row) and applies; apply only sets `classroom_id` (and is audited). Reusable every semester.
- **S4 Manual edit.** The Designaciones list shows the classroom and the designation form lets the admin set or clear it.
- **S5 Source file.** "designacion-update.xlsx": the current workbook is `designacion-update.xlsx` (sheet "DOCENTES TEORICOS", AULA column holds the room number, e.g. 1, 20, "B"); the catalog maps a room number to exactly one classroom (`classroom_catalog_service.catalog_room`).

## Tasks

| ID | Specs | Route | Commit |
|----|-------|-------|--------|
| T1 | S1, S2, S3 backend | gentle-ai-worker: migration + model, occupancy of legacy theory slots, room import preview/apply endpoints, admin schema/service field, tests | 30802a8 |
| T2 | S3, S4 frontend | gentle-ai-worker: Designaciones importer wizard, list column, form field, node tests | e0cee9c |
| T3 | all | gentle-ai-verify (items 1 data/migration, 3 contract) + full suites + rehearsal | 30802a8, e0cee9c |
| T4 | all | parent: chain PRs, supervised deploy with migration, import on production with the user | |

## Log

- **L1** (user): "ok resolvamos lo de las clases de teoria primero".
- **L2** (evidence): `designacion-update.xlsx` "DOCENTES TEORICOS" has AULA per row; `aulas-por-confirmar-II-2026.xlsx` lists rooms 1 and 20 as ambiguous and several as missing, all resolved by the 2026-11-08 catalog sync (room numbers now unique). `aulas.xlsx` places rooms 20 and 26 in the Antiguo building, contradicting the user: not a source.
- **L3** (explore): no column stores a designation's room; `designation_schedule_loader_service.read_rooms` already parses AULA by (CI, subject, semester, group) with `catalog_room`, used only for planner drafts. Publishing theory would move payroll/attendance sources (rejected). `EffectiveScheduleSlot` legacy slots carry `designation_id`; `_current_blocks` sets `classroom_code` only for published slots.
- **L4** (user answers): design "Sí, opción B (recomendado)"; loading "Importador en Designaciones (recomendado)"; file "designacion-update.xlsx".
- **L5** (evidence): T1 02d45cb (backend: migration c8d0e2f4a6b9, occupancy fallback in `_current_blocks`, importer `designation_room_import_service`, admin field). The real workbook has no CI column: rows match by teacher name (folded), subject, semester and group. T2 17c7942 (frontend importer, list column, form picker; 10 + 11 node tests, every frontend check green).
- **L6** (rehearsal on a production copy restored from a fresh dump, local Postgres 16): `alembic upgrade head` b5c7d9e1f3a6 → c8d0e2f4a6b9 OK; FK `fk_designations_classroom_id_classrooms` ON DELETE SET NULL and index present. Importer with `designacion-update.xlsx`: 432 matched and changed, 0 unknown rooms, 14 unmatched rows (all group "EXTRA CONV"), 34 designations without a row. After apply, rooms with classes on Wed 2026-11-11 went from 4 to 25 of 31.
- **L7** (verify): S1, S2, S3, S5, migration PASS (Postgres path proven by the L6 rehearsal); S4 FAIL: B1 classroom-only save of a paid imported designation hit the payroll lock (server rebuilt `schedule_raw`); B2 an unchanged deactivated room blocked unrelated edits; A2 teacher change dropped `classroom_id`. Fixed test-first (RED 8 backend + 2 frontend, GREEN 110 + 26 backend, 11 + 11 frontend) with a dedicated `PUT /api/admin/designations/{id}/classroom` used by the form for classroom-only changes; folded into 30802a8 and e0cee9c. Advisory A1 accepted: the historical assistential import digest now includes `classroom_id` (any designation edit already changes it).
- **L8** (evidence): full backend suite before the fixes 1639 passed / 0 failed; after the fixes 1648 passed / 0 failed.
