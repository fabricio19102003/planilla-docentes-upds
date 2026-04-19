## Exploration: scheduling-module

### Current State

**1. Current `Designation` model and consumers**

- `backend/app/models/designation.py`: `Designation` is a payroll-critical model, not a pure scheduling model. It stores `teacher_ci`, `subject`, `semester`, `group_code`, `academic_period`, `schedule_json`, `semester_hours`, `monthly_hours`, `weekly_hours`, `weekly_hours_calculated`, and `schedule_raw`.
- Direct backend imports of `Designation` exist in 13 files: `backend/app/services/designation_loader.py`, `backend/app/services/attendance_engine.py`, `backend/app/services/planilla_generator.py`, `backend/app/services/report_generator.py`, `backend/app/services/contract_pdf.py`, `backend/app/services/schedule_pdf.py`, `backend/app/services/audit_report_pdf.py`, `backend/app/routers/attendance.py`, `backend/app/routers/planilla.py`, `backend/app/routers/reports.py`, `backend/app/routers/contracts.py`, `backend/app/routers/docente_portal.py`, and `backend/app/models/__init__.py`.
- `DesignationLoader` is used by `backend/app/routers/designations.py` for designation uploads and by `backend/app/routers/biometric.py` for TEMP-teacher linking after biometric upload.
- `schedule_json` is read directly in attendance matching, absent-hour recovery, teacher schedule APIs, attendance audit APIs/PDFs, and schedule PDF generation.
- `Teacher` has a hard ORM relationship to `Designation` through `Teacher.designations` in `backend/app/models/teacher.py`, and teacher detail serialization depends on that relationship in `backend/app/routers/teachers.py` + `backend/app/schemas/teacher.py`.
- `AttendanceRecord.designation_id` is a hard FK to `designations.id` in `backend/app/models/attendance.py`, so payroll persistence is structurally coupled to the current designation table.

Dependency graph today:

```text
UploadPage/useBiometric -> /api/uploads/designations -> routers/designations.py
  -> normalizar_horarios.py (xlsx only)
  -> DesignationLoader.load_from_json()
    -> Teacher + Designation tables

Upload biometrico -> routers/biometric.py
  -> BiometricParser
  -> DesignationLoader.link_teachers_by_name()
    -> Teacher + Designation + AttendanceRecord + BiometricRecord + users/detail_requests

Attendance process -> AttendanceEngine
  -> Designation.schedule_json
  -> AttendanceRecord

Planilla/reporting/contracts/portal schedule
  -> Designation + AttendanceRecord + Teacher
  -> schedule_json or designation aggregates
```

**2. Current data flow: import -> attendance -> planilla**

- Designations enter the system only through `POST /api/uploads/designations` in `backend/app/routers/designations.py`.
- If the file is `.xlsx`, `routers/designations.py` runs `_normalize_designations_excel()`, which calls `normalizar_horarios.py`, emits normalized JSON, and then still delegates to `DesignationLoader.load_from_json()`.
- `DesignationLoader.load_from_json()` detects 3 formats (UPDS official array, new normalized array, old wrapper dict), normalizes group codes, calculates weekly academic hours, creates/reuses teachers, and creates/updates `Designation` rows scoped by `(teacher_ci, subject, semester, group_code, academic_period)`.
- For sources without CI, the loader creates deterministic TEMP teachers (`TEMP-xxxxxxxx`). Later, biometric upload in `backend/app/routers/biometric.py` calls `DesignationLoader.link_teachers_by_name()` to migrate TEMP teachers and update designations, attendance, biometric rows, users, and detail requests.
- Attendance processing in `backend/app/services/attendance_engine.py` loads ALL `Designation` rows for `settings.ACTIVE_ACADEMIC_PERIOD`, indexes them by `teacher_ci`, iterates dates, filters slots from `schedule_json` by weekday, and writes one `AttendanceRecord` per scheduled slot.
- Planilla generation in `backend/app/services/planilla_generator.py` loads ALL `Designation` rows for `settings.ACTIVE_ACADEMIC_PERIOD`, groups `AttendanceRecord`s by `(teacher_ci, designation_id)`, and computes payable hours. For ABSENT rows, it re-reads the scheduled hours from `Designation.schedule_json` because ABSENT attendance rows store `academic_hours = 0`.
- Reporting and docente portal billing repeat the same pattern: payroll reads `Designation` as the source of assigned load, then combines it with attendance and biometric evidence.

Critical implication: replacing JSON import is NOT only an intake change. It changes the source of truth used by attendance, planilla, reports, contracts, audit, and portal schedule features.

**3. `schedule_json` structure**

- Canonical stored shape from `DesignationLoader._transform_horario_detalle()` and `_parse_horario_string()` is:

```json
[
  {
    "dia": "lunes",
    "hora_inicio": "06:30",
    "hora_fin": "08:00",
    "duracion_minutos": 90,
    "horas_academicas": 2
  }
]
```

- Normalized characteristics:
  - `dia`: lowercase Spanish weekday, usually ASCII/unaccented (`miercoles`, `sabado`), although consumers still tolerate accented legacy values.
  - `hora_inicio` / `hora_fin`: `HH:MM` strings.
  - `duracion_minutos`: integer duration derived from times.
  - `horas_academicas`: integer result of `calc_academic_hours()`.
- Legacy tolerance exists in consumers:
  - `planilla_generator._get_slot_hours()` has a fallback when a slot lacks `dia`.
  - frontend `ScheduleSlot` accepts both `day/dia`, `start_time/hora_inicio`, `end_time/hora_fin`, `hours_academicas/horas_academicas`.
- `schedule_raw` stores the original unparsed text, and `weekly_hours_calculated` is derived from summing `horas_academicas` across slots.

This means the relational replacement must preserve, at minimum: weekday, start time, end time, derived duration, derived academic hours, and enough identity to recover absent-slot hours deterministically.

**4. Teacher model and relationships**

- `backend/app/models/teacher.py` defines `Teacher.designations` with `cascade="all, delete-orphan"` and `Teacher.attendance_records`.
- `backend/app/routers/teachers.py` loads teachers with `selectinload(Teacher.designations)` and exposes nested designation data directly in `TeacherDetailResponse`.
- Changing teacher CI is currently a raw-SQL cascade operation across `designations`, `attendance_records`, `biometric_records`, `detail_requests`, and `users` in `backend/app/routers/teachers.py`.
- `DesignationLoader.link_teachers_by_name()` and `_merge_temp_teacher_into_existing()` also mutate `Teacher`, `Designation`, `AttendanceRecord`, `BiometricRecord`, `users`, and `detail_requests` together.

Impact for modularization:

- `Teacher` belongs in `core`, but today scheduling and payroll both point directly at `teachers.ci`.
- If modules must communicate through services instead of direct model imports, the current ORM relationship strategy is too coupled.
- The highest-risk integration point is teacher identity migration (TEMP -> real CI), because it currently spans scheduling, payroll, auth/users, and requests in one service.

**5. Frontend pages touching designations/schedules**

- `frontend/src/pages/UploadPage.tsx` + `frontend/src/api/hooks/useBiometric.ts`: admin uploads designation files and manually enters `academic_period`; fetches `/config/active-period` only as a string default.
- `frontend/src/pages/TeacherDetailPage.tsx`: renders `teacher.designations[]` directly and formats `schedule_json` inline.
- `frontend/src/pages/SchedulePage.tsx` + `frontend/src/api/hooks/useAuth.ts`: docente schedule UI consumes `/portal/schedule` and assumes each designation includes `schedule[]`, `weekly_hours`, `monthly_hours`.
- `frontend/src/pages/AttendanceAuditPage.tsx`: shows assigned schedule chips from the audit response (`subject`, `group_code`, `semester`, `slots`).
- `frontend/src/pages/AdminRequestsPage.tsx` + `frontend/src/api/hooks/usePlanilla.ts`: loads teacher designations/schedule via `/teachers/{ci}/designations` and renders slot chips.
- `frontend/src/pages/MyProfilePage.tsx`: displays schedule summary (`designation_count`, `total_weekly_hours`).
- Indirect designation-count consumers also exist in `frontend/src/pages/PlanillaPage.tsx`, `frontend/src/pages/ReportsPage.tsx`, `frontend/src/pages/DashboardPage.tsx`, and `frontend/src/pages/BillingPage.tsx`.

Frontend consequence: V1 needs a compatibility API shape, or several screens break immediately even if backend tables are successfully normalized.

**6. Migration complexity assessment**

- Structural complexity is HIGH.
- Flat backend inventory to relocate: 11 models, 14 routers, 11 services, 6 schema files, plus `main.py`, `models/__init__.py`, and router registry files.
- Designation-specific coupling hotspots:
  - 13 direct backend `Designation` imports.
  - 23 direct filters against `Designation.academic_period == settings.ACTIVE_ACADEMIC_PERIOD`.
  - direct `schedule_json` reads in 8 backend files plus frontend DTOs/pages.
  - hard FK from `attendance_records.designation_id` to `designations.id`.
- Runtime migration risk is higher than normal because startup still relies on `create_all()` plus manual column migrations in `backend/app/main.py`; there is no fully modular migration boundary yet.
- The riskiest changes are:
  1. moving `Designation` out of the flat import graph without breaking attendance generation,
  2. replacing `schedule_json` while preserving absent-hour deduction behavior,
  3. normalizing `AcademicPeriod` while dozens of queries still rely on `settings.ACTIVE_ACADEMIC_PERIOD`,
  4. splitting `docente_portal.py`, which currently mixes core profile, scheduling views, and payroll billing concerns.

Estimated blast radius:

- Backend file moves/major import updates: ~45 files.
- Backend files with real designation-period logic changes: ~15-20.
- Frontend files needing API/type updates or compatibility validation: ~8-12.

**7. Proposed current -> target mapping**

Models

| Current | Proposed module | Notes |
|---|---|---|
| `backend/app/models/teacher.py` | `backend/app/core/models/teacher.py` | Core identity entity consumed by scheduling and payroll |
| `backend/app/models/user.py` | `backend/app/core/models/user.py` | Auth/identity |
| `backend/app/models/detail_request.py` | `backend/app/core/models/detail_request.py` | User workflow/support |
| `backend/app/models/notification.py` | `backend/app/core/models/notification.py` | User communication |
| `backend/app/models/activity_log.py` | `backend/app/core/models/activity_log.py` | Cross-cutting audit |
| `backend/app/models/designation.py` | `backend/app/scheduling/models/designation.py` | Scheduling source of truth |
| new | `backend/app/scheduling/models/academic_period.py` | normalized period table |
| new | `backend/app/scheduling/models/designation_slot.py` | relational replacement for `schedule_json` |
| new | `backend/app/scheduling/models/room.py` | room inventory |
| new | `backend/app/scheduling/models/room_type.py` | classroom/lab/amphitheater |
| new | `backend/app/scheduling/models/equipment.py` | projector/whiteboard/etc. |
| new | `backend/app/scheduling/models/room_equipment.py` | room-equipment join |
| new | `backend/app/scheduling/models/teacher_availability.py` | per-period availability |
| `backend/app/models/biometric.py` | `backend/app/payroll/models/biometric.py` | attendance input remains payroll |
| `backend/app/models/attendance.py` | `backend/app/payroll/models/attendance.py` | attendance output |
| `backend/app/models/planilla.py` | `backend/app/payroll/models/planilla.py` | generated payroll |
| `backend/app/models/billing_publication.py` | `backend/app/payroll/models/billing_publication.py` | payroll publication |
| `backend/app/models/report.py` | `backend/app/payroll/models/report.py` | payroll/reporting artifact |

Routers

| Current | Proposed module | Notes |
|---|---|---|
| `auth.py` | `core/routers/auth.py` | core |
| `users.py` | `core/routers/users.py` | core admin |
| `teachers.py` | `core/routers/teachers.py` | teacher master data in core |
| `detail_requests.py` | `core/routers/detail_requests.py` | core workflow |
| `activity_log.py` | `core/routers/activity_log.py` | core audit |
| `admin.py` | `core/routers/admin.py` | keep cross-cutting admin here initially |
| `designations.py` | `scheduling/routers/designations.py` | legacy upload endpoint during transition, then CRUD |
| new | `scheduling/routers/academic_periods.py` | CRUD + activate period |
| new | `scheduling/routers/rooms.py` | rooms/types/equipment CRUD |
| new | `scheduling/routers/availability.py` | teacher availability CRUD |
| scheduling slice of `docente_portal.py` | `scheduling/routers/portal_schedule.py` | docente schedule endpoints |
| `biometric.py` | `payroll/routers/biometric.py` | payroll input |
| `attendance.py` | `payroll/routers/attendance.py` | payroll processing/audit |
| `planilla.py` | `payroll/routers/planilla.py` | payroll outputs |
| `reports.py` | `payroll/routers/reports.py` | payroll/report previews |
| `billing_publication.py` | `payroll/routers/billing_publication.py` | payroll publication |
| `contracts.py` | `payroll/routers/contracts.py` | payroll-generated contracts |
| payroll slice of `docente_portal.py` | `payroll/routers/portal_billing.py` | billing/history/retention letter |
| core slice of `docente_portal.py` | `core/routers/portal_profile.py` | profile + notifications |

Services

| Current | Proposed module | Notes |
|---|---|---|
| `auth_service.py` | `core/services/auth_service.py` | core |
| `activity_logger.py` | `core/services/activity_logger.py` | cross-cutting |
| `designation_loader.py` | `scheduling/services/designation_import_legacy.py` | temporary bridge only |
| new | `scheduling/services/designation_service.py` | authoritative scheduling CRUD |
| new | `scheduling/services/slot_service.py` | slot lifecycle + DTOs |
| new | `scheduling/services/conflict_service.py` | teacher/room/group conflict validation |
| new | `scheduling/services/period_service.py` | active-period selection |
| new | `scheduling/services/room_service.py` | rooms/types/equipment |
| new | `scheduling/services/availability_service.py` | availability |
| `schedule_pdf.py` | `scheduling/services/schedule_pdf.py` | schedule rendering belongs to scheduling |
| `biometric_parser.py` | `payroll/services/biometric_parser.py` | payroll |
| `attendance_engine.py` | `payroll/services/attendance_engine.py` | should consume scheduling DTOs, not model imports |
| `planilla_generator.py` | `payroll/services/planilla_generator.py` | payroll |
| `report_generator.py` | `payroll/services/report_generator.py` | payroll/reporting |
| `contract_pdf.py` | `payroll/services/contract_pdf.py` | payroll artifact |
| `retention_letter_pdf.py` | `payroll/services/retention_letter_pdf.py` | payroll artifact |
| `audit_report_pdf.py` | `payroll/services/audit_report_pdf.py` | payroll artifact |

Shared/infrastructure

- `backend/app/config.py` -> `backend/app/shared/config.py`
- `backend/app/database.py` -> `backend/app/shared/database.py`
- `backend/app/utils/helpers.py` -> `backend/app/shared/utils/helpers.py`
- auth dependency helpers can move to `backend/app/core/api/auth.py` or `backend/app/shared/http/auth.py`, but they should no longer sit in a flat `utils/` package.

**8. `AcademicPeriod` normalization impact**

- Today `AcademicPeriod` is NOT an entity. It is just:
  - a config string in `backend/app/config.py` (`ACTIVE_ACADEMIC_PERIOD = "I/2026"`),
  - a varchar column on `Designation`,
  - a free-text query parameter in `POST /api/uploads/designations`,
  - a value returned by `/api/config/active-period`,
  - a frontend input on `UploadPage.tsx`.
- 23 backend queries hardcode the active-period filter by reading settings directly.
- `backend/app/main.py` also contains startup migration logic that adds the `academic_period` column and unique constraint using the config value.

Normalized-model impact:

- Add `academic_periods` table with at least: `id`, `code`, `name`, `start_date`, `end_date`, `is_active`, `status`, `created_at`.
- Change `Designation` to reference `academic_period_id` (and optionally keep a derived `code` accessor for API compatibility).
- Replace `settings.ACTIVE_ACADEMIC_PERIOD` reads with a `PeriodService.get_active_period()` query or cached provider.
- Update upload/designation creation flows so admin selects an existing period instead of typing arbitrary strings.
- Update `/config/active-period` into a scheduling endpoint that returns the active period entity, not just a string.
- Update reporting/attendance/planilla filters to join against active period or accept explicit period ids.

Without this normalization, the new scheduling module will still depend on a global string flag, which fights the modular-monolith goal.

**9. Proposed `DesignationSlot` relational design**

Recommended V1 model:

```text
Designation
- id
- teacher_ci (FK -> core.teacher.ci)
- academic_period_id (FK -> scheduling.academic_period.id)
- subject
- semester
- group_code
- semester_hours
- monthly_hours
- weekly_hours
- weekly_hours_calculated
- schedule_raw (temporary, optional)
- source = manual | legacy_import

DesignationSlot
- id
- designation_id (FK -> scheduling.designation.id, cascade delete)
- room_id (FK -> scheduling.room.id)
- day_of_week (smallint 0-6 or enum)
- start_time (time)
- end_time (time)
- duration_minutes
- academic_hours
- created_at

Unique constraints
- (designation_id, day_of_week, start_time, end_time)
- optionally (academic_period_id, room_id, day_of_week, start_time, end_time) via validation/query, not only DB
```

Supporting room models:

```text
RoomType(id, code, name)
Equipment(id, code, name)
Room(id, code, name, building, floor, capacity, room_type_id, is_active)
RoomEquipment(room_id, equipment_id)
TeacherAvailability(id, teacher_ci, academic_period_id, day_of_week, start_time, end_time, availability_type)
```

How payroll should read it:

- Introduce a scheduling read service that returns a flat slot DTO for payroll, for example:

```text
ScheduledSlotDTO
- designation_id
- teacher_ci
- academic_period_id
- subject
- group_code
- semester
- day_of_week
- start_time
- end_time
- academic_hours
```

- `AttendanceEngine` should consume those DTOs from `scheduling.services.slot_service` instead of importing `scheduling.models.Designation` directly.
- `PlanillaGenerator` absent-hour recovery should resolve against slot rows by `(designation_id, weekday, start_time)` instead of re-reading a JSON blob.
- For transition, a compatibility adapter can materialize `schedule_json` from `DesignationSlot` so existing APIs keep working while internals are refactored.

**10. Conflict detection requirements for V1**

Minimum validation set:

- `Room double-booking`: same academic period + same room + overlapping day/time between two slots.
- `Teacher overlap`: same teacher + same academic period + overlapping day/time across two designations.
- `Group overlap`: same group_code + same academic period + overlapping day/time across two designations.
- `Duplicate slot inside one designation`: same designation with duplicate weekday/start/end.
- `Room existence/active status`: assigned room must exist and be active.
- `Capacity/equipment validation`: not a time conflict, but V1 room assignment should still validate requested constraints against room metadata because equipment is explicitly in scope.

Suggested overlap rule:

```text
two slots conflict when
slot_a.start_time < slot_b.end_time
AND slot_b.start_time < slot_a.end_time
on the same day_of_week and academic_period
```

Suggested enforcement points:

- synchronous validation in scheduling create/update services,
- reusable `conflict_service` for admin UI previews,
- DB indexes on `(academic_period_id, teacher_ci, day_of_week)`, `(academic_period_id, room_id, day_of_week)`, `(academic_period_id, group_code, day_of_week)` to keep conflict queries cheap.

### Affected Areas

- `backend/app/models/designation.py` — current designation source of truth, includes `schedule_json` and `academic_period`
- `backend/app/services/designation_loader.py` — current import pipeline and TEMP-teacher reconciliation
- `backend/app/services/attendance_engine.py` — reads designation schedules to create attendance rows
- `backend/app/services/planilla_generator.py` — payroll calculation depends on designation load and absent-slot recovery
- `backend/app/routers/designations.py` — current JSON/Excel designation intake endpoint
- `backend/app/routers/biometric.py` — biometric upload triggers designation/teacher linking
- `backend/app/routers/planilla.py` — teacher designation API, dashboard metrics, active-period endpoint
- `backend/app/routers/docente_portal.py` — mixed core/scheduling/payroll concerns, including schedule and billing
- `backend/app/routers/teachers.py` — teacher detail nests designations; CI changes cascade across modules
- `backend/app/services/report_generator.py` — multiple reports assume direct designation table access
- `frontend/src/pages/UploadPage.tsx` — admin designation upload and free-text period selection
- `frontend/src/pages/SchedulePage.tsx` — docente schedule visualization consumes designation schedule DTOs
- `frontend/src/pages/TeacherDetailPage.tsx` — renders `schedule_json` directly
- `frontend/src/pages/AttendanceAuditPage.tsx` — shows assigned schedule per designation
- `frontend/src/pages/AdminRequestsPage.tsx` — loads teacher schedule detail through planilla hook
- `frontend/src/api/types.ts` — frontend DTO contract still models `schedule_json`

### Approaches

1. **Compatibility-first modular refactor** — move code into `core/`, `scheduling/`, `payroll/`, keep legacy APIs alive with adapters while replacing internals incrementally
   - Pros: lowest rollout risk; preserves attendance/planilla behavior; lets payroll consume scheduling through services; easier to validate against current outputs
   - Cons: temporary duplication/adapters; `schedule_json` may need short-lived compatibility projection; more transitional code
   - Effort: High

2. **Big-bang scheduling rewrite** — replace imports, APIs, DB model, and frontend contracts in one pass
   - Pros: cleaner final architecture immediately; no temporary compatibility layer
   - Cons: highest blast radius; likely breaks payroll/reporting flows; harder to isolate regressions; risky with current flat startup/migration setup
   - Effort: Very High

### Recommendation

Use the compatibility-first modular refactor.

Phase 1 should be structural: create `shared/`, `core/`, `scheduling/`, `payroll/`; move files; introduce module-level service interfaces; keep current endpoints working. Phase 2 should make scheduling the source of truth by adding `AcademicPeriod`, rooms, availability, `DesignationSlot`, and conflict validation, while payroll reads schedule data through a scheduling service/DTO instead of importing scheduling models directly. Phase 3 can remove legacy import paths and `schedule_json` storage after parity is proven.

### Risks

- `Teacher`/`Designation` coupling is stronger than it looks because CI migration logic updates five tables plus auth/request records.
- Attendance and planilla both rely on exact slot identity; if slot matching changes, ABSENT deductions can silently drift.
- `ACTIVE_ACADEMIC_PERIOD` is embedded across routers/services and will resist normalization until replaced by a real period service.
- `docente_portal.py` violates the target dependency boundaries today and will need to be split, not just moved.
- Frontend screens depend on current nested designation DTOs; backend normalization without compatibility responses will break admin and docente flows.

### Ready for Proposal

Yes — proposal should scope:

1. modular-monolith restructuring with dependency rules (`shared -> core -> scheduling -> payroll`),
2. normalized scheduling data model (`AcademicPeriod`, rooms, equipment, availability, `DesignationSlot`),
3. payroll read adapters from scheduling,
4. legacy designation-upload deprecation strategy,
5. compatibility API plan for frontend screens during the transition.
