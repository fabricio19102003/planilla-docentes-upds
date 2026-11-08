# Classroom and laboratory reservations

Teachers reserve a classroom or laboratory for a single date from the teacher portal; admins see every reservation in a timetable grid.
Branch `feat/classroom-reservations` (worktree `planilla-docentes-upds-worktrees/classroom-reservations`, base `origin/master` a0d3062). Delivery strategy: ask-on-risk; chain_strategy=feature-branch-chain (forecast ~1300 authored lines). Slices: PR1 backend (T1-T2), PR2 portal (T3), PR3 admin + labs (T4-T5).

## Specs

- **S1 Availability (portal).** "los docentes puedan hacer, mi idea es que ellos en el portal docente puedan ver la disponibilidad del aula o laboratorio que deseen recervar". In the teacher portal a teacher picks an active classroom or laboratory and a date and sees that day's free and busy time ranges.
- **S2 Occupied by classes.** "las aulas que se encuentren ocupadas por clases deben de etiquetarse como ocupadas". Busy ranges coming from class schedules are labelled "Ocupada" (by class). Only published schedules count ("Solo horarios publicados"). Ranges already reserved by another reservation are also shown as busy.
- **S3 Reserve, confirmed immediately.** "si esta disponible en el horario que ellos desean que lo puedan recervar" and "la reserva queda confirmada al toque". If the requested range does not overlap a published class block or another active reservation of the same room, the reservation is created already confirmed; otherwise it is rejected with an explanation, and nothing is stored.
- **S4 Duration in academic periods.** "quiero que el docente pueda seleccione en cuanto a periodo academico el tiempo de utilizacion de espacio fisico que esta reservando". The teacher chooses a start time and a number of academic periods; end time = start + periods × the configured academic hour (`ACADEMIC_HOUR_MINUTES`, 45 min by default).
- **S5 One-off only.** "solo reservas puntuales". Each reservation is for one date; no recurrence.
- **S6 Catalog.** All active classrooms of the existing catalog are reservable, including rooms 20-29 ("Todas reservables"). The user's list (rooms 1-19, A, B, floors and capacities) already matches `classroom_catalog_service.CATALOG`.
- **S7 Laboratories.** "El admin los da de alta": the admin creates and edits laboratories (name, capacity) and they become reservable.
- **S8 Admin grid.** "del lado del admin ver en formato de grilla estilo calnedario u horario ver todos las recervas que los docentes vayan haciendo". The admin sees all reservations in a calendar/timetable grid.

## Tasks

| ID | Specs | Route | Commit |
|----|-------|-------|--------|
| T1 | S1-S6 | inline: `ClassroomReservation` model + migration, availability and create service (per-room row lock against double booking), portal endpoints, tests | 7eaf412 |
| T2 | S8 (+D3) | inline: own-reservation list/cancel (portal) and admin reservations listing endpoint, tests | 7eaf412 |
| T3 | S1-S5 | gentle-ai-worker (context backstop): portal page "Reservar aula" (availability timeline, form, my reservations), nav + route | f4f11f2 |
| T4 | S8 | gentle-ai-worker (context backstop): admin page "Reservas de aulas" day grid (rooms × time) with date navigation, nav + route | C3 (feat(admin)) |
| T5 | S7 | gentle-ai-worker: verified, no change needed (`frontend/src/pages/AcademicManagementPage.tsx:454`, capacity required for laboratory) | none |
| T6 | all | inline: full backend suite, frontend checks/tsc/lint, README; gentle-ai-verify (items 2 and 4) | C3 (feat(admin)) |

## Log

- **L1** (user, original request): "hola, necesito que me ayudes a implementar una feature de recerva de aulas o laboratorios que los docentes puedan hacer, mi idea es que ellos en el portal docente puedan ver la disponibilidad del aula o laboratorio que deseen recervar y si esta disponible en el horario que ellos desean que lo puedan recervar y del lado del admin ver en formato de grilla estilo calnedario u horario ver todos las recervas que los docentes vayan haciendo. ahora antes de empezar con eso quiero que veas que tan buena opcion es empezar a implementar microservicios ya que sipad ha crecido bastante, es viable eso? o no tiene sentido ahora mismo"
- **L2** (agent): microservices not recommended now; modular monolith instead, reservations born as its own module.
- **L3** (user): "ok sobre la feature, la reserva queda confirmada al toque, las aulas que se encuentren ocupadas por clases deben de etiquetarse como ocupadas, me gustaria manejarnos en periodos academicos, solo reservas puntuales, ahora con respecto al catalogo aqui esta el catalogo de aulas actualizado:" followed by the old-building table (1-10 floors 1-2 capacity 54, A and B floor 1 capacity 20) and the new-building table (11:35, 12:50, 13:50, 14:40, 15:40, 16:35, 17:20 on floor 2; 18:47, 19:51 on floor 3).
- **L4** (user answers): aulas 20-29 "Todas reservables"; laboratorios "El admin los da de alta"; ocupada por "Solo horarios publicados"; periodos: "quiero que el docente pueda seleccione en cuanto a periodo academico el tiempo de utilizacion de espacio fisico que esta reservando".
- **L5** (evidence): `Classroom` model and official catalog already exist (`backend/app/models/academic_management.py`, `backend/app/services/classroom_catalog_service.py`); admin classroom CRUD already exists (`backend/app/routers/academic_management.py:430-447`, types classroom|laboratory|virtual|other). Published class blocks with `classroom_code` come from `academic_schedule_view_service.schedule_blocks(source="current", reference=date)`.
- **L6** (agent decisions, reversible): D1 bookable types are `classroom` and `laboratory`, active only. D2 start time in 5-minute steps inside the existing day window 06:30-23:05; 1 to 8 periods; date not in the past and, for today, start later than now (Bolivia time). D3 a teacher may cancel their own future reservation (cancelled rows stay for audit, status `cancelled`); admin view is read-only. D4 overlap is strict half-open `[start, end)`. D5 concurrent double booking is prevented by locking the classroom row (`SELECT ... FOR UPDATE`) before the overlap check.
- **L7** (user): delivery "Cadena sobre rama de feature (recomendado)" → chain_strategy=feature-branch-chain.
- **L8** (evidence, T1-T2 backend contract, `backend/app/routers/classroom_reservations.py`, tests `backend/tests/test_classroom_reservations.py`):
  - `GET /api/portal/classroom-reservations/classrooms` (docente) → `[{id, code, name, capacity, classroom_type}]`, active `classroom` then `laboratory`, by code.
  - `GET /api/portal/classroom-reservations/availability?classroom_id=&date=YYYY-MM-DD` → `{classroom, date, academic_hour_minutes, day_start: "06:30", day_end: "23:05", busy: [{start_time, end_time, kind: "class"|"reservation", label: "Ocupada"|"Reservada", detail: subject|null, mine: bool}]}`; 404 `El aula o laboratorio no está disponible para reservas.`
  - `POST /api/portal/classroom-reservations` body `{classroom_id, date, start_time: "HH:MM", periods: 1..8}` → 201 reservation; 409 `El aula está ocupada por una clase de HH:MM a HH:MM.` / `El aula ya está reservada de HH:MM a HH:MM.`; 422 `No se puede reservar en una fecha u hora pasada.` / `La reserva debe quedar entre las 06:30 y las 23:05.` / `La hora de inicio debe ser múltiplo de 5 minutos.`
  - Reservation JSON: `{id, classroom: {id, code, name, capacity, classroom_type}, date, start_time, end_time, academic_periods, status: "confirmed"|"cancelled", teacher_ci, teacher_name}`.
  - `GET /api/portal/classroom-reservations/mine` → my confirmed reservations from today on, by date and start.
  - `POST /api/portal/classroom-reservations/{id}/cancel` → reservation (status cancelled); 404 `Reserva no encontrada.`, 409 `La reserva ya fue cancelada.`, 422 `No se puede cancelar una reserva que ya comenzó.`
  - `GET /api/admin/classroom-reservations?date_from=&date_to=` (admin) → `{classrooms: [...bookable rooms], reservations: [...confirmed, by date, start, room code]}`; 422 `La fecha final no puede ser anterior a la inicial.` / `El rango no puede superar 31 días.`
- **L9** (evidence): first full backend suite 1599 passed, 1 failed (`test_every_teacher_ci_foreign_key_is_moved_or_guarded`): reservations were added to `TeacherIdentityService.child_tables`. RED/GREEN: backend T1 RED on missing module then 19 passed; T2 RED 9 failed then 27 passed. Frontend T3 RED on missing module then 12/12; T4 RED then 13/13.
- **L10** (verify, gentle-ai-verify on 7eaf412's backend): S1-S6 PASS; permissions PASS (no IDOR, availability does not reveal who reserved); migration PASS (single head b5c7d9e1f3a6); CI change PASS; concurrency PASS by code reasoning, UNVERIFIED at runtime (no PostgreSQL test DB). Advisories fixed test-first: start time with seconds rejected; admin listing keeps rooms deactivated after being reserved. RDD is off for this clone (assess: rdd-off), so no native review ran.
- **L11** (delivery, feature-branch-chain): PR1 backend = 7eaf412; PR2 portal = f4f11f2; PR3 admin grid + README + feature document = the `feat(admin)` commit after f4f11f2. Push and PR creation remain the user's decision.
- **L12** (evidence): final full suite found `tests/services/test_teacher_identity_service.py` seeding one row per `child_tables` entry; a reservation was added to its seed (RED then 21 passed). Commits rebased: backend 7eaf412, portal f4f11f2.
