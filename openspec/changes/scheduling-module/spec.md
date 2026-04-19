# Scheduling Module — Specification

> Change: `scheduling-module`  
> Status: Draft  
> Last updated: 2026-04-19  
> Depends on: Proposal (`openspec/changes/scheduling-module/proposal.md`)

---

## 1. Overview

This specification defines the complete data model, service layer, API surface, frontend pages, business rules, migration strategy, and test scenarios for the scheduling module. It is organized into four delivery phases:

| Phase | Name | Summary |
|-------|------|---------|
| 1 | Structural Refactor | Move files into `shared/`, `core/`, `scheduling/`, `payroll/`. Fix imports. No features. |
| 2 | Scheduling Models & Services | New models, CRUD services, conflict detection. |
| 3 | Payroll Integration | `attendance_engine` and `planilla_generator` consume scheduling DTOs. Compatibility adapters for frontend. |
| 4 | Legacy Deprecation | Remove JSON/Excel import pipeline, drop `schedule_json` column. |

---

## 2. Data Models

All models use SQLAlchemy 2.0 `Mapped` style (consistent with existing codebase). `Base` is the shared declarative base from `app.database`.

### 2.1 AcademicPeriod

**Table**: `academic_periods`  
**Module**: `scheduling/models/academic_period.py`  
**Phase**: 2

| Column | Type | Constraints | Default | Notes |
|--------|------|-------------|---------|-------|
| `id` | `Integer` | PK, autoincrement | — | |
| `code` | `String(20)` | NOT NULL, UNIQUE | — | e.g. `"I/2026"`, `"II/2026"` |
| `name` | `String(100)` | NOT NULL | — | e.g. `"Primer Semestre 2026"` |
| `year` | `Integer` | NOT NULL | — | e.g. `2026` |
| `semester_number` | `Integer` | NOT NULL | — | `1` or `2` (I or II) |
| `start_date` | `Date` | NOT NULL | — | Period start |
| `end_date` | `Date` | NOT NULL | — | Period end |
| `is_active` | `Boolean` | NOT NULL | `False` | Only ONE row can be `True` at a time |
| `status` | `String(20)` | NOT NULL | `"planning"` | Enum: `planning`, `active`, `closed` |
| `created_at` | `DateTime` | NOT NULL | `func.now()` | |
| `updated_at` | `DateTime` | nullable | `onupdate=func.now()` | |

**Indexes**: `ix_academic_periods_is_active` on `(is_active)` WHERE `is_active = True` (partial, if DB supports; otherwise regular).

**Relationships**:
- `designations` → `Designation[]` (back_populates `academic_period`)

**Business Rules**:
- BR-AP-1: Only ONE period can have `is_active = True`. Activating a period deactivates the current active one in a single transaction.
- BR-AP-2: `status` lifecycle: `planning` → `active` → `closed`. No backwards transitions.
- BR-AP-3: A period in `closed` status cannot be modified (no new designations, no edits).
- BR-AP-4: A period cannot be closed if it has designations with `status = 'draft'`.
- BR-AP-5: `start_date` must be before `end_date`.
- BR-AP-6: `code` format must match pattern `^(I|II)/\d{4}$`.

---

### 2.2 Career

**Table**: `careers`  
**Module**: `core/models/career.py`  
**Phase**: 2

| Column | Type | Constraints | Default | Notes |
|--------|------|-------------|---------|-------|
| `id` | `Integer` | PK, autoincrement | — | |
| `code` | `String(20)` | NOT NULL, UNIQUE | — | e.g. `"MED"`, `"ODO"`, `"ENF"` |
| `name` | `String(200)` | NOT NULL | — | e.g. `"Medicina"`, `"Odontologia"` |
| `description` | `Text` | nullable | `None` | |
| `is_active` | `Boolean` | NOT NULL | `True` | Soft delete |
| `created_at` | `DateTime` | NOT NULL | `func.now()` | |
| `updated_at` | `DateTime` | nullable | `onupdate=func.now()` | |

**Relationships**:
- `semesters` → `Semester[]` (back_populates `career`, cascade `all, delete-orphan`)

**Business Rules**:
- BR-CR-1: Cannot deactivate a career that has semesters with active designations. Return HTTP 409.
- BR-CR-2: `code` must be uppercase alphanumeric, max 20 chars.
- BR-CR-3: Career lives in `core/` because it's a foundational entity shared by scheduling and (potentially) payroll.

**Note**: Career is a `core/` entity, not `scheduling/`, because multiple modules may depend on it. A career defines the academic program; scheduling assigns schedules within that program.

---

### 2.3 Semester

**Table**: `semesters`  
**Module**: `core/models/semester.py`  
**Phase**: 2

| Column | Type | Constraints | Default | Notes |
|--------|------|-------------|---------|-------|
| `id` | `Integer` | PK, autoincrement | — | |
| `career_id` | `Integer` | FK → `careers.id`, NOT NULL | — | `ondelete="CASCADE"` |
| `number` | `Integer` | NOT NULL | — | 1-10 (or more, depends on career) |
| `name` | `String(100)` | NOT NULL | — | e.g. `"1er Semestre"`, `"5to Semestre"` |
| `is_active` | `Boolean` | NOT NULL | `True` | |
| `created_at` | `DateTime` | NOT NULL | `func.now()` | |

**Unique Constraint**: `uq_semester_career_number` on `(career_id, number)`.

**Relationships**:
- `career` → `Career` (back_populates `semesters`)
- `subjects` → `Subject[]` (back_populates `semester`, cascade `all, delete-orphan`)

**Business Rules**:
- BR-SM-1: `number` must be >= 1.
- BR-SM-2: Cannot delete a semester that has subjects with active designations. Return HTTP 409.
- BR-SM-3: The combination `(career_id, number)` must be unique.
- BR-SM-4: Semester lives in `core/` because it's part of the curriculum structure.

---

### 2.4 Subject

**Table**: `subjects`  
**Module**: `core/models/subject.py`  
**Phase**: 2

| Column | Type | Constraints | Default | Notes |
|--------|------|-------------|---------|-------|
| `id` | `Integer` | PK, autoincrement | — | |
| `semester_id` | `Integer` | FK → `semesters.id`, NOT NULL | — | `ondelete="CASCADE"` |
| `code` | `String(20)` | nullable, UNIQUE when not null | — | e.g. `"MRF 0100"`, `null` for electives |
| `name` | `String(200)` | NOT NULL | — | e.g. `"Anatomia Humana I"` |
| `theoretical_hours` | `Integer` | NOT NULL | `0` | HT from curriculum (semester total) |
| `practical_hours` | `Integer` | NOT NULL | `0` | HP from curriculum (semester total) |
| `credits` | `Integer` | NOT NULL | `0` | CR from curriculum |
| `is_elective` | `Boolean` | NOT NULL | `False` | True for "Electiva I", "Electiva II", etc. |
| `is_active` | `Boolean` | NOT NULL | `True` | |
| `created_at` | `DateTime` | NOT NULL | `func.now()` | |
| `updated_at` | `DateTime` | nullable | `onupdate=func.now()` | |

**Indexes**: `ix_subjects_semester` on `(semester_id)`.

**Relationships**:
- `semester` → `Semester` (back_populates `subjects`)
- `designations` → `Designation[]` (back_populates `subject_rel`)

**Business Rules**:
- BR-SJ-1: `code` can be NULL for elective subjects (e.g. "Electiva I" has no fixed code in the malla). When not null, must be unique.
- BR-SJ-2: Cannot delete a subject that has active designations. Return HTTP 409.
- BR-SJ-3: `theoretical_hours` and `practical_hours` must be >= 0.
- BR-SJ-4: `credits` must be >= 0.
- BR-SJ-5: Subjects are editable even after creation (to handle elective name/hour changes between periods).
- BR-SJ-6: Subject lives in `core/` because it's part of the curriculum (malla curricular), not a scheduling artifact.

**Curriculum Import**: The system should support bulk import of subjects from the malla curricular JSON format:
```json
{
    "carrera": "Medicina",
    "semestres": [
        {
            "semestre": 1,
            "materias": [
                {"codigo": "MRF 0100", "nombre": "Anatomía Humana I", "HT": 51, "HP": 51, "CR": 5}
            ]
        }
    ]
}
```

---

### 2.5 Shift

**Table**: `shifts`  
**Module**: `scheduling/models/shift.py`  
**Phase**: 2

| Column | Type | Constraints | Default | Notes |
|--------|------|-------------|---------|-------|
| `id` | `Integer` | PK, autoincrement | — | |
| `code` | `String(5)` | NOT NULL, UNIQUE | — | `"M"`, `"T"`, `"N"` |
| `name` | `String(50)` | NOT NULL | — | `"Mañana"`, `"Tarde"`, `"Noche"` |
| `start_time` | `Time` | NOT NULL | — | Typical start, e.g. `06:30` for morning |
| `end_time` | `Time` | NOT NULL | — | Typical end, e.g. `12:30` for morning |
| `display_order` | `Integer` | NOT NULL | `0` | For UI sorting: M=1, T=2, N=3 |

**Relationships**:
- `groups` → `Group[]` (back_populates `shift`)

**Business Rules**:
- BR-SH-1: System ships with 3 pre-seeded shifts: M (Mañana, 06:30-12:30), T (Tarde, 12:30-18:30), N (Noche, 18:30-22:00).
- BR-SH-2: Cannot delete a shift that has groups referencing it. Return HTTP 409.
- BR-SH-3: `start_time` and `end_time` are indicative ranges (not hard constraints on scheduling — a morning group could have a class ending at 13:00).

---

### 2.6 Group

**Table**: `groups`  
**Module**: `scheduling/models/group.py`  
**Phase**: 2

| Column | Type | Constraints | Default | Notes |
|--------|------|-------------|---------|-------|
| `id` | `Integer` | PK, autoincrement | — | |
| `academic_period_id` | `Integer` | FK → `academic_periods.id`, NOT NULL | — | `ondelete="CASCADE"` |
| `semester_id` | `Integer` | FK → `semesters.id`, NOT NULL | — | `ondelete="RESTRICT"` |
| `shift_id` | `Integer` | FK → `shifts.id`, NOT NULL | — | `ondelete="RESTRICT"` |
| `number` | `Integer` | NOT NULL | — | Parallel number within the shift (1, 2, 3...) |
| `code` | `String(20)` | NOT NULL | — | Auto-generated: `"{shift.code}-{number}"` e.g. `"M-1"`, `"T-2"`, `"N-1"` |
| `is_special` | `Boolean` | NOT NULL | `False` | True for G.E. (Grupos Especiales — convalidacion students) |
| `student_count` | `Integer` | nullable | `None` | Estimated students (for room capacity validation) |
| `is_active` | `Boolean` | NOT NULL | `True` | |
| `created_at` | `DateTime` | NOT NULL | `func.now()` | |

**Unique Constraint**: `uq_group_period_semester_code` on `(academic_period_id, semester_id, code)`.

**Indexes**: `ix_groups_period_semester` on `(academic_period_id, semester_id)`.

**Relationships**:
- `academic_period` → `AcademicPeriod`
- `semester` → `Semester`
- `shift` → `Shift` (back_populates `groups`)
- `designations` → `Designation[]` (back_populates `group_rel`)

**Business Rules**:
- BR-GR-1: `code` is auto-generated from `shift.code` + `-` + `number`. For special groups: `code = "G.E."` (or custom code).
- BR-GR-2: Groups are created PER academic period. Each period, the admin decides which groups exist for each semester.
- BR-GR-3: Cannot delete a group that has designations. Return HTTP 409.
- BR-GR-4: `number` must be >= 1.
- BR-GR-5: For `is_special = True` (G.E.), the group follows a separate curriculum and schedule. The `semester_id` still references the semester it's associated with, but the subjects may differ.
- BR-GR-6: `student_count` is used for room capacity validation when assigning rooms to slots. If null, capacity check is skipped.

**Special Group (G.E.) handling**:
- G.E. students come from other universities (convalidacion) and have a custom adapted curriculum
- G.E. groups have `is_special = True` and `code = "G.E."` (or "G.E.-1", "G.E.-2" if multiple)
- G.E. designations may reference subjects from any semester (not restricted to one semester's malla)
- G.E. scheduling follows the same conflict detection rules as regular groups

---

### 2.7 RoomType (was 2.2)

**Table**: `room_types`  
**Module**: `scheduling/models/room_type.py`  
**Phase**: 2

| Column | Type | Constraints | Default | Notes |
|--------|------|-------------|---------|-------|
| `id` | `Integer` | PK, autoincrement | — | |
| `code` | `String(20)` | NOT NULL, UNIQUE | — | e.g. `"AULA"`, `"LAB"`, `"ANFI"` |
| `name` | `String(100)` | NOT NULL | — | e.g. `"Aula Comun"`, `"Laboratorio"` |
| `description` | `Text` | nullable | `None` | |

**Relationships**:
- `rooms` → `Room[]` (back_populates `room_type`)

**Business Rules**:
- BR-RT-1: Cannot delete a `RoomType` that has rooms referencing it. Return HTTP 409.

---

### 2.8 Equipment (was 2.3)

**Table**: `equipment`  
**Module**: `scheduling/models/equipment.py`  
**Phase**: 2

| Column | Type | Constraints | Default | Notes |
|--------|------|-------------|---------|-------|
| `id` | `Integer` | PK, autoincrement | — | |
| `code` | `String(20)` | NOT NULL, UNIQUE | — | e.g. `"PROY"`, `"PIZ"`, `"PC"` |
| `name` | `String(100)` | NOT NULL | — | e.g. `"Proyector"`, `"Pizarra"` |
| `description` | `Text` | nullable | `None` | |

**Business Rules**:
- BR-EQ-1: Cannot delete an `Equipment` that is assigned to any room via `RoomEquipment`. Return HTTP 409.

---

### 2.9 Room (was 2.4)

**Table**: `rooms`  
**Module**: `scheduling/models/room.py`  
**Phase**: 2

| Column | Type | Constraints | Default | Notes |
|--------|------|-------------|---------|-------|
| `id` | `Integer` | PK, autoincrement | — | |
| `code` | `String(20)` | NOT NULL, UNIQUE | — | e.g. `"A-101"`, `"LAB-3"` |
| `name` | `String(100)` | NOT NULL | — | e.g. `"Aula 101"` |
| `building` | `String(100)` | NOT NULL | — | e.g. `"Edificio Central"` |
| `floor` | `String(20)` | NOT NULL | — | e.g. `"1"`, `"PB"`, `"2"` |
| `capacity` | `Integer` | NOT NULL | — | Max students |
| `room_type_id` | `Integer` | FK → `room_types.id`, NOT NULL | — | `ondelete="RESTRICT"` |
| `is_active` | `Boolean` | NOT NULL | `True` | Soft delete |
| `description` | `Text` | nullable | `None` | |
| `created_at` | `DateTime` | NOT NULL | `func.now()` | |
| `updated_at` | `DateTime` | nullable | `onupdate=func.now()` | |

**Indexes**: `ix_rooms_building_floor` on `(building, floor)`.

**Relationships**:
- `room_type` → `RoomType` (back_populates `rooms`)
- `equipment_items` → `RoomEquipment[]` (back_populates `room`, cascade `all, delete-orphan`)
- `designation_slots` → `DesignationSlot[]` (back_populates `room`)

**Business Rules**:
- BR-RM-1: Cannot deactivate a room (`is_active = False`) if it has `DesignationSlot` records in any non-closed period. Return HTTP 409 with list of conflicting slots.
- BR-RM-2: Rooms are never hard-deleted; use `is_active = False`.
- BR-RM-3: `capacity` must be >= 1.

---

### 2.10 RoomEquipment (was 2.5)

**Table**: `room_equipment`  
**Module**: `scheduling/models/room_equipment.py`  
**Phase**: 2

| Column | Type | Constraints | Default | Notes |
|--------|------|-------------|---------|-------|
| `id` | `Integer` | PK, autoincrement | — | |
| `room_id` | `Integer` | FK → `rooms.id`, NOT NULL | — | `ondelete="CASCADE"` |
| `equipment_id` | `Integer` | FK → `equipment.id`, NOT NULL | — | `ondelete="RESTRICT"` |
| `quantity` | `Integer` | NOT NULL | `1` | How many of this equipment |
| `notes` | `Text` | nullable | `None` | e.g. `"Solo funciona con adaptador HDMI"` |

**Unique Constraint**: `uq_room_equipment` on `(room_id, equipment_id)`.

**Relationships**:
- `room` → `Room` (back_populates `equipment_items`)
- `equipment` → `Equipment`

---

### 2.11 TeacherAvailability (was 2.6)

**Table**: `teacher_availabilities`  
**Module**: `scheduling/models/teacher_availability.py`  
**Phase**: 2

| Column | Type | Constraints | Default | Notes |
|--------|------|-------------|---------|-------|
| `id` | `Integer` | PK, autoincrement | — | |
| `teacher_ci` | `String(20)` | FK → `teachers.ci`, NOT NULL | — | `ondelete="CASCADE"` |
| `academic_period_id` | `Integer` | FK → `academic_periods.id`, NOT NULL | — | `ondelete="CASCADE"` |
| `created_at` | `DateTime` | NOT NULL | `func.now()` | |
| `updated_at` | `DateTime` | nullable | `onupdate=func.now()` | |

**Unique Constraint**: `uq_teacher_period_availability` on `(teacher_ci, academic_period_id)`.

**Relationships**:
- `slots` → `AvailabilitySlot[]` (back_populates `availability`, cascade `all, delete-orphan`)
- `teacher` → `Teacher` (core model, string resolution)
- `academic_period` → `AcademicPeriod`

---

### 2.12 AvailabilitySlot (was 2.7)

**Table**: `availability_slots`  
**Module**: `scheduling/models/availability_slot.py`  
**Phase**: 2

| Column | Type | Constraints | Default | Notes |
|--------|------|-------------|---------|-------|
| `id` | `Integer` | PK, autoincrement | — | |
| `availability_id` | `Integer` | FK → `teacher_availabilities.id`, NOT NULL | — | `ondelete="CASCADE"` |
| `day_of_week` | `Integer` | NOT NULL | — | 0=Monday … 6=Sunday |
| `start_time` | `Time` | NOT NULL | — | |
| `end_time` | `Time` | NOT NULL | — | |

**Unique Constraint**: `uq_availability_slot` on `(availability_id, day_of_week, start_time, end_time)`.

**Business Rules**:
- BR-AS-1: `start_time` must be before `end_time`.
- BR-AS-2: Slots within the same `availability_id` and `day_of_week` MUST NOT overlap (use overlap formula).
- BR-AS-3: `day_of_week` must be in range 0-6.

---

### 2.13 Designation (MODIFIED — was 2.8)

**Table**: `designations` (unchanged table name)  
**Module**: `scheduling/models/designation.py` (moved from `models/`)  
**Phase**: 1 (move), Phase 2 (modify)

#### Columns KEPT (unchanged)

| Column | Type | Constraints | Default | Notes |
|--------|------|-------------|---------|-------|
| `id` | `Integer` | PK, autoincrement | — | |
| `teacher_ci` | `String(20)` | FK → `teachers.ci`, NOT NULL | — | `ondelete="CASCADE"` |
| `semester_hours` | `Integer` | nullable | — | From curriculum (total semester hours) |
| `monthly_hours` | `Integer` | nullable | — | Auto-computed: `weekly_hours_calculated * 4` |
| `weekly_hours` | `Integer` | nullable | — | From source data (original) |
| `weekly_hours_calculated` | `Integer` | nullable | — | Auto-computed: sum of slot `academic_hours` |
| `created_at` | `DateTime` | NOT NULL | `func.now()` | |

#### Columns ADDED (Phase 2)

| Column | Type | Constraints | Default | Notes |
|--------|------|-------------|---------|-------|
| `academic_period_id` | `Integer` | FK → `academic_periods.id`, NOT NULL | — | `ondelete="RESTRICT"`. Replaces `academic_period` string. |
| `subject_id` | `Integer` | FK → `subjects.id`, NOT NULL | — | `ondelete="RESTRICT"`. Replaces `subject` string. |
| `group_id` | `Integer` | FK → `groups.id`, NOT NULL | — | `ondelete="RESTRICT"`. Replaces `group_code` string. Links to semester implicitly via group. |
| `source` | `String(20)` | NOT NULL | `"manual"` | Enum: `manual`, `legacy_import` |
| `status` | `String(20)` | NOT NULL | `"draft"` | Enum: `draft`, `confirmed`, `cancelled` |

#### Columns DEPRECATED (Phase 2 — kept temporarily, Phase 4 — removed)

| Column | Type | Notes |
|--------|------|-------|
| `academic_period` | `String(20)` | Kept during transition. Auto-populated from `AcademicPeriod.code` on save. Removed in Phase 4. |
| `subject` | `String(200)` | Kept during transition. Auto-populated from `Subject.name` on save. Removed in Phase 4. |
| `semester` | `String(50)` | Kept during transition. Auto-populated from `Semester.name` via `Group.semester`. Removed in Phase 4. |
| `group_code` | `String(20)` | Kept during transition. Auto-populated from `Group.code` on save. Removed in Phase 4. |
| `schedule_json` | `JSON` | Kept during transition. Auto-populated from `DesignationSlot` records by `CompatibilityAdapter`. Removed in Phase 4. |
| `schedule_raw` | `Text` | Kept during transition. No longer populated for `source=manual`. Removed in Phase 4. |

#### Modified Unique Constraint

Replace `uq_designation_teacher_subject_semester_group_period`:
```
UNIQUE (teacher_ci, subject_id, group_id, academic_period_id)
```
Note: `semester` is no longer in the unique constraint because `group_id` already implies a semester (via `Group.semester_id`).

**Relationships**:
- `teacher` → `Teacher` (back_populates `designations`)
- `academic_period` → `AcademicPeriod` (back_populates `designations`)
- `subject_rel` → `Subject` (back_populates `designations`)
- `group_rel` → `Group` (back_populates `designations`)
- `slots` → `DesignationSlot[]` (back_populates `designation`, cascade `all, delete-orphan`)
- `attendance_records` → `AttendanceRecord[]` (back_populates `designation`) — payroll FK remains

**Business Rules**:
- BR-DG-1: `weekly_hours_calculated` = sum of all slot `academic_hours`. Auto-computed on slot add/remove.
- BR-DG-2: `monthly_hours` = `weekly_hours_calculated * 4`. Auto-computed.
- BR-DG-3: Status lifecycle: `draft` → `confirmed` → `cancelled`. Only `draft` → `confirmed` and `draft|confirmed` → `cancelled` are valid.
- BR-DG-4: Confirmed designations cannot be edited (slots added/removed/modified) without admin override.
- BR-DG-5: Cancelled designations cannot be edited or confirmed.
- BR-DG-6: When any slot is added/removed, `schedule_json` is re-generated via `CompatibilityAdapter` (transition period only).
- BR-DG-7: Legacy import designations get `source = 'legacy_import'` and `status = 'confirmed'` automatically.

---

### 2.14 DesignationSlot (was 2.9)

**Table**: `designation_slots`  
**Module**: `scheduling/models/designation_slot.py`  
**Phase**: 2

| Column | Type | Constraints | Default | Notes |
|--------|------|-------------|---------|-------|
| `id` | `Integer` | PK, autoincrement | — | |
| `designation_id` | `Integer` | FK → `designations.id`, NOT NULL | — | `ondelete="CASCADE"` |
| `room_id` | `Integer` | FK → `rooms.id`, nullable | `None` | `ondelete="SET NULL"`. Room may not be assigned yet. |
| `day_of_week` | `Integer` | NOT NULL | — | 0=Monday … 6=Sunday |
| `start_time` | `Time` | NOT NULL | — | |
| `end_time` | `Time` | NOT NULL | — | |
| `duration_minutes` | `Integer` | NOT NULL | — | Auto-computed: `(end_time - start_time)` in minutes |
| `academic_hours` | `Integer` | NOT NULL | — | Auto-computed: `round(duration_minutes / 45)` |
| `created_at` | `DateTime` | NOT NULL | `func.now()` | |

**Unique Constraint**: `uq_designation_slot` on `(designation_id, day_of_week, start_time)`.

**Indexes**:
- `ix_designation_slots_room_day` on `(room_id, day_of_week)` — for conflict queries
- `ix_designation_slots_designation` on `(designation_id)` — for loading all slots of a designation

**Relationships**:
- `designation` → `Designation` (back_populates `slots`)
- `room` → `Room` (back_populates `designation_slots`)

**Business Rules**:
- BR-DS-1: `start_time` must be before `end_time`.
- BR-DS-2: `duration_minutes` = `(end_time - start_time)` in total minutes. Auto-computed on save.
- BR-DS-3: `academic_hours` = `round(duration_minutes / 45)`. Auto-computed on save. This matches the existing formula in `attendance_engine` and `designation_loader`.
- BR-DS-4: Before saving, `ConflictService.validate_slot()` MUST be called. If any HARD conflict is returned, the save is rejected.
- BR-DS-5: `day_of_week` must be in range 0-6.
- BR-DS-6: A slot can exist without a `room_id` (room assignment is optional and can be done later).

---

## 3. Service Layer

### 3.1 PeriodService

**Module**: `scheduling/services/period_service.py`  
**Phase**: 2

```python
class PeriodService:
    def create_period(
        self, db: Session, *, code: str, name: str, year: int,
        semester_number: int, start_date: date, end_date: date
    ) -> AcademicPeriod:
        """Create a new period with status='planning'.
        Validates: BR-AP-5 (start < end), BR-AP-6 (code format), unique code.
        Raises: 409 if code already exists, 422 if validation fails.
        """

    def activate_period(self, db: Session, period_id: int) -> AcademicPeriod:
        """Set is_active=True on target period, is_active=False on current active.
        Also sets status='active' if currently 'planning'.
        Raises: 404 if not found, 409 if period is 'closed'.
        """

    def get_active_period(self, db: Session) -> AcademicPeriod | None:
        """Returns the single active period, or None if no period is active.
        This REPLACES settings.ACTIVE_ACADEMIC_PERIOD across the system.
        """

    def list_periods(
        self, db: Session, *, status: str | None = None
    ) -> list[AcademicPeriod]:
        """List all periods, optionally filtered by status.
        Ordered by year DESC, semester_number DESC.
        """

    def get_period(self, db: Session, period_id: int) -> AcademicPeriod:
        """Get single period by ID. Raises 404 if not found."""

    def update_period(
        self, db: Session, period_id: int, **fields
    ) -> AcademicPeriod:
        """Update mutable fields (name, start_date, end_date).
        Raises: 404 if not found, 409 if period is 'closed' (BR-AP-3).
        """

    def close_period(self, db: Session, period_id: int) -> AcademicPeriod:
        """Set status='closed'. Validates BR-AP-4 (no draft designations).
        Raises: 409 if draft designations exist.
        """
```

---

### 3.2 CareerService

**Module**: `core/services/career_service.py`  
**Phase**: 2

```python
class CareerService:
    def create(self, db: Session, *, code: str, name: str, description: str | None = None) -> Career:
        """Create a new career. Validates unique code.
        Raises: 409 if code exists.
        """

    def update(self, db: Session, career_id: int, **fields) -> Career:
        """Update career fields (name, description). Raises 404."""

    def deactivate(self, db: Session, career_id: int) -> Career:
        """Soft delete. Validates BR-CR-1 (no active designations in any semester).
        Raises: 409 if active designations exist.
        """

    def reactivate(self, db: Session, career_id: int) -> Career

    def list_all(self, db: Session, *, active_only: bool = True) -> list[Career]:
        """List careers with semester count."""

    def get(self, db: Session, career_id: int) -> Career:
        """Career with eagerly loaded semesters and subjects. Raises 404."""

    def import_curriculum(
        self, db: Session, career_id: int, curriculum_json: dict
    ) -> dict:
        """Bulk import subjects from malla curricular JSON format.
        Creates semesters and subjects that don't exist yet. Updates existing ones.
        Returns: {semesters_created, subjects_created, subjects_updated, warnings[]}
        """
```

---

### 3.3 SemesterService

**Module**: `core/services/semester_service.py`  
**Phase**: 2

```python
class SemesterService:
    def create(self, db: Session, *, career_id: int, number: int, name: str) -> Semester:
        """Create semester in career. Validates unique (career_id, number).
        Raises: 409 if exists, 404 if career not found.
        """

    def update(self, db: Session, semester_id: int, **fields) -> Semester:
        """Update name. Raises 404."""

    def delete(self, db: Session, semester_id: int) -> None:
        """Hard delete. Validates BR-SM-2 (no active designations).
        Raises: 409 if active designations exist.
        """

    def list_by_career(self, db: Session, career_id: int) -> list[Semester]:
        """All semesters for a career, ordered by number. Includes subject count."""

    def get(self, db: Session, semester_id: int) -> Semester:
        """Semester with subjects. Raises 404."""
```

---

### 3.4 SubjectService

**Module**: `core/services/subject_service.py`  
**Phase**: 2

```python
class SubjectService:
    def create(
        self, db: Session, *, semester_id: int, code: str | None,
        name: str, theoretical_hours: int, practical_hours: int,
        credits: int, is_elective: bool = False
    ) -> Subject:
        """Create subject in semester. Code nullable for electives.
        Validates: unique code (when not null), semester exists.
        Raises: 409 if code exists, 404 if semester not found, 422 if hours < 0.
        """

    def update(self, db: Session, subject_id: int, **fields) -> Subject:
        """Update subject fields. All fields editable (BR-SJ-5).
        Raises: 404 if not found.
        """

    def delete(self, db: Session, subject_id: int) -> None:
        """Hard delete. Validates BR-SJ-2 (no active designations).
        Raises: 409 if active designations exist.
        """

    def list_by_semester(self, db: Session, semester_id: int) -> list[Subject]:
        """All subjects for a semester, ordered by code. Includes designation count per active period."""

    def get(self, db: Session, subject_id: int) -> Subject:
        """Subject with semester and career info. Raises 404."""

    def search(self, db: Session, *, query: str, career_id: int | None = None) -> list[Subject]:
        """Search subjects by name or code. Optionally filter by career."""
```

---

### 3.5 ShiftService

**Module**: `scheduling/services/shift_service.py`  
**Phase**: 2

```python
class ShiftService:
    def list_all(self, db: Session) -> list[Shift]:
        """All shifts ordered by display_order. Pre-seeded: M, T, N."""

    def get(self, db: Session, shift_id: int) -> Shift:
        """Raises 404."""

    def update(self, db: Session, shift_id: int, **fields) -> Shift:
        """Update name, start/end times, display_order.
        Raises: 404 if not found.
        """

    def seed_defaults(self, db: Session) -> list[Shift]:
        """Create default shifts if they don't exist:
        M (Mañana, 06:30-12:30, order=1)
        T (Tarde, 12:30-18:30, order=2)
        N (Noche, 18:30-22:00, order=3)
        Idempotent — safe to call multiple times.
        """
```

---

### 3.6 GroupService

**Module**: `scheduling/services/group_service.py`  
**Phase**: 2

```python
class GroupService:
    def create_group(
        self, db: Session, *, period_id: int, semester_id: int,
        shift_id: int, number: int, is_special: bool = False,
        student_count: int | None = None
    ) -> Group:
        """Create group for a period+semester+shift.
        Auto-generates code: '{shift.code}-{number}' or 'G.E.' for special.
        Validates: unique (period_id, semester_id, code).
        Raises: 409 if duplicate, 404 if period/semester/shift not found.
        """

    def create_bulk(
        self, db: Session, *, period_id: int, semester_id: int,
        groups: list[dict]  # [{shift_id, number, student_count?, is_special?}]
    ) -> list[Group]:
        """Create multiple groups at once for a semester in a period.
        Useful when admin sets up 'this semester has M-1, M-2, T-1, N-1, N-2'.
        """

    def update(self, db: Session, group_id: int, **fields) -> Group:
        """Update student_count, is_active. Cannot change shift/number if designations exist.
        Raises: 404 if not found.
        """

    def delete(self, db: Session, group_id: int) -> None:
        """Delete group. Validates BR-GR-3 (no designations).
        Raises: 409 if designations exist.
        """

    def list_by_period(
        self, db: Session, period_id: int, *,
        semester_id: int | None = None
    ) -> list[Group]:
        """All groups for a period, optionally filtered by semester.
        Ordered by semester number, shift display_order, group number.
        Includes: semester, shift, designation count.
        """

    def get(self, db: Session, group_id: int) -> Group:
        """Group with semester, shift, period. Raises 404."""
```

---

### 3.7 RoomTypeService (was 3.2)

**Module**: `scheduling/services/room_type_service.py`  
**Phase**: 2

```python
class RoomTypeService:
    def create(self, db: Session, *, code: str, name: str, description: str | None = None) -> RoomType
    def update(self, db: Session, type_id: int, **fields) -> RoomType
    def delete(self, db: Session, type_id: int) -> None  # BR-RT-1: 409 if rooms exist
    def list_all(self, db: Session) -> list[RoomType]
    def get(self, db: Session, type_id: int) -> RoomType  # 404 if not found
```

---

### 3.8 EquipmentService (was 3.3)

**Module**: `scheduling/services/equipment_service.py`  
**Phase**: 2

```python
class EquipmentService:
    def create(self, db: Session, *, code: str, name: str, description: str | None = None) -> Equipment
    def update(self, db: Session, equipment_id: int, **fields) -> Equipment
    def delete(self, db: Session, equipment_id: int) -> None  # BR-EQ-1: 409 if assigned to rooms
    def list_all(self, db: Session) -> list[Equipment]
    def get(self, db: Session, equipment_id: int) -> Equipment  # 404 if not found
```

---

### 3.9 RoomService (was 3.4)

**Module**: `scheduling/services/room_service.py`  
**Phase**: 2

```python
class RoomService:
    def create_room(
        self, db: Session, *, code: str, name: str, building: str,
        floor: str, capacity: int, room_type_id: int,
        equipment: list[dict] | None = None,  # [{equipment_id, quantity?, notes?}]
        description: str | None = None
    ) -> Room:
        """Create room with optional equipment assignment.
        Validates: BR-RM-3 (capacity >= 1), room_type exists.
        Raises: 409 if code already exists, 422 if room_type not found.
        """

    def update_room(self, db: Session, room_id: int, **fields) -> Room:
        """Update room fields. Cannot change code if slots exist.
        Raises: 404 if not found.
        """

    def deactivate_room(self, db: Session, room_id: int) -> Room:
        """Set is_active=False. Validates BR-RM-1.
        Raises: 409 if active slots reference this room in non-closed periods.
        """

    def reactivate_room(self, db: Session, room_id: int) -> Room:
        """Set is_active=True."""

    def list_rooms(
        self, db: Session, *, building: str | None = None,
        floor: str | None = None, room_type_id: int | None = None,
        active_only: bool = True
    ) -> list[Room]:
        """Filtered list. Includes room_type and equipment eagerly loaded."""

    def get_room(self, db: Session, room_id: int) -> Room:
        """Room with type + equipment. Raises 404."""

    def add_equipment(
        self, db: Session, room_id: int, equipment_id: int,
        quantity: int = 1, notes: str | None = None
    ) -> RoomEquipment:
        """Assign equipment to room. Raises 409 if already assigned."""

    def remove_equipment(self, db: Session, room_id: int, equipment_id: int) -> None:
        """Remove equipment assignment. Raises 404 if not assigned."""

    def update_equipment(
        self, db: Session, room_id: int, equipment_id: int,
        quantity: int | None = None, notes: str | None = None
    ) -> RoomEquipment:
        """Update equipment assignment details."""
```

---

### 3.10 AvailabilityService (was 3.5)

**Module**: `scheduling/services/availability_service.py`  
**Phase**: 2

```python
class AvailabilityService:
    def set_availability(
        self, db: Session, *, teacher_ci: str, period_id: int,
        slots: list[dict]  # [{day_of_week, start_time, end_time}]
    ) -> TeacherAvailability:
        """Replace all availability slots for this teacher+period.
        Creates TeacherAvailability if doesn't exist, replaces slots.
        Validates: BR-AS-1 (start < end), BR-AS-2 (no overlaps), BR-AS-3 (day range).
        Raises: 404 if teacher or period not found, 422 if validation fails.
        """

    def get_availability(
        self, db: Session, *, teacher_ci: str, period_id: int
    ) -> TeacherAvailability | None:
        """Returns availability with eagerly loaded slots. None if not set."""

    def clear_availability(
        self, db: Session, *, teacher_ci: str, period_id: int
    ) -> None:
        """Delete all availability for this teacher+period."""

    def list_by_period(
        self, db: Session, period_id: int
    ) -> list[TeacherAvailability]:
        """All teacher availabilities for a period, with slots."""
```

---

### 3.11 DesignationService (was 3.6)

**Module**: `scheduling/services/designation_service.py`  
**Phase**: 2

```python
class DesignationService:
    def create_designation(
        self, db: Session, *,
        teacher_ci: str, period_id: int, subject_id: int,
        group_id: int,
        slots: list[dict],  # [{day_of_week, start_time, end_time, room_id?}]
        semester_hours: int | None = None,
        weekly_hours: int | None = None,
    ) -> Designation:
        """Create designation with slots. Status='draft', source='manual'.
        Validates: teacher, period, subject, group all exist.
        Validates: group belongs to the given period.
        For each slot:
          1. Compute duration_minutes, academic_hours (BR-DS-2, BR-DS-3)
          2. Validate via ConflictService (BR-DS-4)
          3. Create DesignationSlot
        After all slots: compute weekly_hours_calculated and monthly_hours (BR-DG-1, BR-DG-2).
        Generate schedule_json via CompatibilityAdapter (BR-DG-6).
        Populate deprecated string columns (subject, semester, group_code, academic_period) from FK entities.
        Raises: 404 teacher/period/subject/group not found, 409 conflicts detected, 422 validation.
        """

    def update_designation(
        self, db: Session, designation_id: int, **fields
    ) -> Designation:
        """Update non-slot fields (subject_id, group_id, semester_hours).
        Validates BR-DG-4 (confirmed cannot edit), BR-DG-5 (cancelled cannot edit).
        Re-populates deprecated string columns on change.
        """

    def add_slot(
        self, db: Session, designation_id: int,
        day_of_week: int, start_time: time, end_time: time,
        room_id: int | None = None
    ) -> DesignationSlot:
        """Add a slot to an existing designation.
        Validates conflicts, recomputes hours, regenerates schedule_json.
        Raises: 409 if conflicts, 422 if designation is confirmed/cancelled.
        """

    def remove_slot(self, db: Session, slot_id: int) -> None:
        """Remove a slot. Recompute hours, regenerate schedule_json.
        Raises: 422 if parent designation is confirmed/cancelled.
        """

    def update_slot(
        self, db: Session, slot_id: int, *,
        day_of_week: int | None = None, start_time: time | None = None,
        end_time: time | None = None, room_id: int | None = None
    ) -> DesignationSlot:
        """Update slot fields. Re-validates conflicts, recomputes hours.
        Raises: 409 if new values create conflicts.
        """

    def assign_room_to_slot(
        self, db: Session, slot_id: int, room_id: int
    ) -> DesignationSlot:
        """Assign room to slot. Validates room availability and capacity.
        Raises: 409 if room is booked, inactive, or insufficient capacity.
        """

    def unassign_room_from_slot(self, db: Session, slot_id: int) -> DesignationSlot:
        """Remove room assignment from slot. Sets room_id=None."""

    def confirm_designation(self, db: Session, designation_id: int) -> Designation:
        """Status → 'confirmed'. Validates all slots have no conflicts.
        Raises: 409 if any unresolved conflicts, 422 if already cancelled.
        """

    def cancel_designation(self, db: Session, designation_id: int) -> Designation:
        """Status → 'cancelled'. Allowed from draft or confirmed.
        Raises: 422 if already cancelled.
        """

    def list_designations(
        self, db: Session, *,
        period_id: int | None = None,
        teacher_ci: str | None = None,
        status: str | None = None,
        subject: str | None = None,
    ) -> list[Designation]:
        """Filtered list with eagerly loaded slots and teacher."""

    def get_designation(self, db: Session, designation_id: int) -> Designation:
        """Single designation with slots, teacher, period. Raises 404."""

    def get_designations_for_period(
        self, db: Session, period_id: int
    ) -> list[Designation]:
        """Public interface for payroll consumption.
        Returns confirmed + legacy_import designations.
        """
```

---

### 3.12 ConflictService (was 3.7)

**Module**: `scheduling/services/conflict_service.py`  
**Phase**: 2

```python
@dataclass
class Conflict:
    type: str          # TEACHER_OVERLAP | ROOM_DOUBLE_BOOKING | GROUP_OVERLAP |
                       # ROOM_INACTIVE | OUTSIDE_AVAILABILITY | DUPLICATE_SLOT
    severity: str      # HARD (blocks save) | SOFT (warning only)
    message: str       # Human-readable description
    conflicting_slot_id: int | None  # ID of the existing slot that conflicts
    details: dict      # Extra context (teacher_ci, room_code, group_code, times)


class ConflictService:
    def validate_slot(
        self, db: Session, *,
        period_id: int, designation_id: int | None,
        teacher_ci: str, group_code: str,
        day_of_week: int, start_time: time, end_time: time,
        room_id: int | None = None,
        exclude_slot_id: int | None = None,  # For updates: exclude self
    ) -> list[Conflict]:
        """Run ALL conflict checks. Returns list of conflicts (may be empty).
        Called by DesignationService before every slot create/update.
        """

    def check_teacher_overlap(
        self, db: Session, *, teacher_ci: str, period_id: int,
        day_of_week: int, start_time: time, end_time: time,
        exclude_slot_id: int | None = None
    ) -> list[Conflict]:
        """Same teacher, same period, same day, overlapping times.
        Overlap formula: a.start < b.end AND b.start < a.end
        Severity: HARD
        """

    def check_room_overlap(
        self, db: Session, *, room_id: int, period_id: int,
        day_of_week: int, start_time: time, end_time: time,
        exclude_slot_id: int | None = None
    ) -> list[Conflict]:
        """Same room, same period, same day, overlapping times.
        Severity: HARD
        """

    def check_group_overlap(
        self, db: Session, *, group_code: str, period_id: int,
        day_of_week: int, start_time: time, end_time: time,
        exclude_slot_id: int | None = None
    ) -> list[Conflict]:
        """Same group, same period, same day, overlapping times.
        Severity: HARD
        """

    def check_room_active(self, db: Session, room_id: int) -> list[Conflict]:
        """Room must exist and be is_active=True.
        Severity: HARD
        """

    def check_teacher_availability(
        self, db: Session, *, teacher_ci: str, period_id: int,
        day_of_week: int, start_time: time, end_time: time
    ) -> list[Conflict]:
        """Slot must fall within teacher's declared availability.
        If no availability is set for this teacher+period, skip check (no conflict).
        Severity: SOFT (warning — teacher may not have set availability yet)
        """
```

**Overlap Formula** (used for teacher, room, and group checks):
```sql
-- Two slots overlap on the same day_of_week in the same period when:
existing.start_time < :new_end_time
AND :new_start_time < existing.end_time
AND existing.day_of_week = :new_day_of_week

-- Additional join to filter by period:
JOIN designations d ON ds.designation_id = d.id
WHERE d.academic_period_id = :period_id
AND d.status != 'cancelled'
```

**Performance indexes** (critical for conflict queries):
```sql
-- Teacher overlap check
CREATE INDEX ix_slots_teacher_day ON designation_slots(day_of_week)
  -- JOIN through designations WHERE teacher_ci = ? AND academic_period_id = ?

-- Room overlap check
CREATE INDEX ix_slots_room_day ON designation_slots(room_id, day_of_week)

-- Group overlap check (through designations)
-- Uses existing designation indexes + slot day_of_week
```

---

### 3.13 SlotReadService (was 3.8) (Payroll Interface)

**Module**: `scheduling/services/slot_read_service.py`  
**Phase**: 3

This is the **PUBLIC READ API** that payroll consumes. It replaces direct `Designation` model imports in payroll.

```python
@dataclass
class ScheduledSlotDTO:
    """Flat, immutable DTO for payroll consumption.
    Payroll NEVER imports scheduling models directly — only this DTO.
    """
    designation_id: int
    teacher_ci: str
    academic_period_code: str  # e.g. "I/2026" — for backward compat
    subject: str
    group_code: str
    semester: str
    day_of_week: int           # 0=Monday ... 6=Sunday
    day_name: str              # "lunes", "martes", ... (for attendance_engine compat)
    start_time: time
    end_time: time
    duration_minutes: int
    academic_hours: int
    room_code: str | None


class SlotReadService:
    def get_slots_for_period(
        self, db: Session, period_id: int
    ) -> list[ScheduledSlotDTO]:
        """All slots for all confirmed designations in this period.
        Used by attendance_engine.process_month().
        """

    def get_slots_for_teacher(
        self, db: Session, teacher_ci: str, period_id: int
    ) -> list[ScheduledSlotDTO]:
        """All slots for one teacher in one period.
        Used by teacher detail views, schedule PDF, portal.
        """

    def get_slots_for_teacher_on_day(
        self, db: Session, teacher_ci: str, period_id: int,
        day_of_week: int
    ) -> list[ScheduledSlotDTO]:
        """Slots for one teacher on a specific weekday.
        Used by attendance_engine for per-day matching.
        """

    def get_slot_hours_for_designation(
        self, db: Session, designation_id: int,
        day_of_week: int, start_time: time
    ) -> int:
        """Get academic_hours for a specific slot.
        Used by planilla_generator for ABSENT hour recovery.
        Raises: 404 if slot not found.
        """
```

---

### 3.14 CompatibilityAdapter (was 3.9)

**Module**: `scheduling/services/compatibility_adapter.py`  
**Phase**: 2 (created), Phase 4 (removed)

```python
class CompatibilityAdapter:
    """Generates legacy schedule_json from DesignationSlot records.
    Used during transition to keep existing frontend/payroll code working.
    """

    WEEKDAY_NAMES: dict[int, str] = {
        0: "lunes", 1: "martes", 2: "miercoles",
        3: "jueves", 4: "viernes", 5: "sabado", 6: "domingo"
    }

    def slots_to_schedule_json(self, slots: list[DesignationSlot]) -> list[dict]:
        """Convert relational slots to legacy JSON format:
        [
            {
                "dia": "lunes",
                "hora_inicio": "08:00",
                "hora_fin": "09:30",
                "duracion_minutos": 90,
                "horas_academicas": 2
            }
        ]
        """

    def sync_designation_json(self, db: Session, designation_id: int) -> None:
        """Regenerate and persist schedule_json on the Designation record.
        Called automatically after slot add/remove/update.
        """
```

---

## 4. API Endpoints

All endpoints require JWT authentication. Role requirements specified per endpoint.

### 4.1 Academic Periods

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `POST` | `/api/scheduling/periods` | admin | Create period |
| `GET` | `/api/scheduling/periods` | admin | List periods (query: `?status=`) |
| `GET` | `/api/scheduling/periods/{id}` | admin | Get period detail |
| `PUT` | `/api/scheduling/periods/{id}` | admin | Update period |
| `POST` | `/api/scheduling/periods/{id}/activate` | admin | Activate period |
| `POST` | `/api/scheduling/periods/{id}/close` | admin | Close period |
| `GET` | `/api/scheduling/periods/active` | admin, docente | Get current active period |

**Request: Create Period**
```json
{
    "code": "I/2026",
    "name": "Primer Semestre 2026",
    "year": 2026,
    "semester_number": 1,
    "start_date": "2026-02-01",
    "end_date": "2026-07-15"
}
```

**Response: Period**
```json
{
    "id": 1,
    "code": "I/2026",
    "name": "Primer Semestre 2026",
    "year": 2026,
    "semester_number": 1,
    "start_date": "2026-02-01",
    "end_date": "2026-07-15",
    "is_active": false,
    "status": "planning",
    "created_at": "2026-04-19T10:00:00",
    "designation_count": 0
}
```

**Modified endpoint**: `GET /api/config/active-period` now calls `PeriodService.get_active_period()` and returns `AcademicPeriod` instead of a plain string.

---

### 4.2 Careers

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `POST` | `/api/core/careers` | admin | Create career |
| `GET` | `/api/core/careers` | admin | List careers (query: `?active_only=true`) |
| `GET` | `/api/core/careers/{id}` | admin | Get career with semesters + subjects |
| `PUT` | `/api/core/careers/{id}` | admin | Update career |
| `POST` | `/api/core/careers/{id}/deactivate` | admin | Soft delete |
| `POST` | `/api/core/careers/{id}/reactivate` | admin | Reactivate |
| `POST` | `/api/core/careers/{id}/import-curriculum` | admin | Bulk import subjects from malla curricular JSON |

**Request: Import Curriculum**
```json
{
    "semestres": [
        {
            "semestre": 1,
            "materias": [
                {"codigo": "MRF 0100", "nombre": "Anatomía Humana I", "HT": 51, "HP": 51, "CR": 5},
                {"codigo": null, "nombre": "Electiva I", "HT": 40, "HP": 40, "CR": 4}
            ]
        }
    ]
}
```

**Response: Import Result**
```json
{
    "semesters_created": 10,
    "subjects_created": 78,
    "subjects_updated": 0,
    "warnings": ["Electiva I: código null, marcada como electiva"]
}
```

---

### 4.3 Semesters

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `POST` | `/api/core/careers/{career_id}/semesters` | admin | Create semester |
| `GET` | `/api/core/careers/{career_id}/semesters` | admin | List semesters for career |
| `GET` | `/api/core/semesters/{id}` | admin | Get semester with subjects |
| `PUT` | `/api/core/semesters/{id}` | admin | Update semester |
| `DELETE` | `/api/core/semesters/{id}` | admin | Delete (409 if designations exist) |

---

### 4.4 Subjects

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `POST` | `/api/core/semesters/{semester_id}/subjects` | admin | Create subject |
| `GET` | `/api/core/semesters/{semester_id}/subjects` | admin | List subjects for semester |
| `GET` | `/api/core/subjects/{id}` | admin | Get subject detail |
| `PUT` | `/api/core/subjects/{id}` | admin | Update subject |
| `DELETE` | `/api/core/subjects/{id}` | admin | Delete (409 if designations exist) |
| `GET` | `/api/core/subjects/search` | admin | Search subjects (query: `?q=anatomia&career_id=1`) |

**Response: Subject**
```json
{
    "id": 1,
    "code": "MRF 0100",
    "name": "Anatomía Humana I",
    "theoretical_hours": 51,
    "practical_hours": 51,
    "credits": 5,
    "is_elective": false,
    "is_active": true,
    "semester": {"id": 1, "number": 1, "name": "1er Semestre"},
    "career": {"id": 1, "code": "MED", "name": "Medicina"}
}
```

---

### 4.5 Shifts

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `GET` | `/api/scheduling/shifts` | admin | List all shifts (pre-seeded: M, T, N) |
| `PUT` | `/api/scheduling/shifts/{id}` | admin | Update shift (name, times, order) |

Shifts are pre-seeded and cannot be created or deleted via API.

---

### 4.6 Groups

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `POST` | `/api/scheduling/groups` | admin | Create group |
| `POST` | `/api/scheduling/groups/bulk` | admin | Create multiple groups at once |
| `GET` | `/api/scheduling/groups` | admin | List groups (query: `?period_id=&semester_id=`) |
| `GET` | `/api/scheduling/groups/{id}` | admin | Get group detail |
| `PUT` | `/api/scheduling/groups/{id}` | admin | Update group |
| `DELETE` | `/api/scheduling/groups/{id}` | admin | Delete (409 if designations exist) |

**Request: Create Group**
```json
{
    "period_id": 1,
    "semester_id": 1,
    "shift_id": 1,
    "number": 1,
    "student_count": 35
}
```

**Response: Group**
```json
{
    "id": 1,
    "code": "M-1",
    "academic_period": {"id": 1, "code": "I/2026"},
    "semester": {"id": 1, "number": 1, "name": "1er Semestre", "career": {"id": 1, "name": "Medicina"}},
    "shift": {"id": 1, "code": "M", "name": "Mañana"},
    "number": 1,
    "is_special": false,
    "student_count": 35,
    "is_active": true,
    "designation_count": 0
}
```

**Request: Bulk Create Groups**
```json
{
    "period_id": 1,
    "semester_id": 1,
    "groups": [
        {"shift_id": 1, "number": 1, "student_count": 35},
        {"shift_id": 1, "number": 2, "student_count": 30},
        {"shift_id": 2, "number": 1, "student_count": 40},
        {"shift_id": 3, "number": 1, "student_count": 25},
        {"shift_id": 3, "number": 2, "student_count": 28}
    ]
}
```
This creates groups M-1, M-2, T-1, N-1, N-2 for 1er Semestre in period I/2026.

---

### 4.7 Room Types (was 4.2)

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `POST` | `/api/scheduling/room-types` | admin | Create |
| `GET` | `/api/scheduling/room-types` | admin | List all |
| `GET` | `/api/scheduling/room-types/{id}` | admin | Get one |
| `PUT` | `/api/scheduling/room-types/{id}` | admin | Update |
| `DELETE` | `/api/scheduling/room-types/{id}` | admin | Delete (409 if rooms exist) |

---

### 4.8 Equipment (was 4.3)

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `POST` | `/api/scheduling/equipment` | admin | Create |
| `GET` | `/api/scheduling/equipment` | admin | List all |
| `GET` | `/api/scheduling/equipment/{id}` | admin | Get one |
| `PUT` | `/api/scheduling/equipment/{id}` | admin | Update |
| `DELETE` | `/api/scheduling/equipment/{id}` | admin | Delete (409 if assigned) |

---

### 4.9 Rooms (was 4.4)

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `POST` | `/api/scheduling/rooms` | admin | Create room (with optional equipment) |
| `GET` | `/api/scheduling/rooms` | admin | List rooms (query: `?building=&floor=&type_id=&active_only=true`) |
| `GET` | `/api/scheduling/rooms/{id}` | admin | Get room with type + equipment |
| `PUT` | `/api/scheduling/rooms/{id}` | admin | Update room |
| `POST` | `/api/scheduling/rooms/{id}/deactivate` | admin | Soft delete (409 if active slots) |
| `POST` | `/api/scheduling/rooms/{id}/reactivate` | admin | Reactivate |
| `POST` | `/api/scheduling/rooms/{id}/equipment` | admin | Add equipment to room |
| `DELETE` | `/api/scheduling/rooms/{id}/equipment/{eq_id}` | admin | Remove equipment |
| `PUT` | `/api/scheduling/rooms/{id}/equipment/{eq_id}` | admin | Update equipment assignment |

**Request: Create Room**
```json
{
    "code": "A-101",
    "name": "Aula 101",
    "building": "Edificio Central",
    "floor": "1",
    "capacity": 40,
    "room_type_id": 1,
    "description": "Aula amplia con ventilacion",
    "equipment": [
        {"equipment_id": 1, "quantity": 1, "notes": "Proyector Epson"},
        {"equipment_id": 2, "quantity": 2}
    ]
}
```

**Response: Room**
```json
{
    "id": 1,
    "code": "A-101",
    "name": "Aula 101",
    "building": "Edificio Central",
    "floor": "1",
    "capacity": 40,
    "is_active": true,
    "description": "Aula amplia con ventilacion",
    "room_type": {"id": 1, "code": "AULA", "name": "Aula Comun"},
    "equipment": [
        {"equipment_id": 1, "code": "PROY", "name": "Proyector", "quantity": 1, "notes": "Proyector Epson"},
        {"equipment_id": 2, "code": "PIZ", "name": "Pizarra", "quantity": 2, "notes": null}
    ],
    "created_at": "2026-04-19T10:00:00"
}
```

---

### 4.10 Teacher Availability (was 4.5)

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `PUT` | `/api/scheduling/availability/{teacher_ci}/{period_id}` | admin | Set/replace availability |
| `GET` | `/api/scheduling/availability/{teacher_ci}/{period_id}` | admin, docente | Get availability |
| `DELETE` | `/api/scheduling/availability/{teacher_ci}/{period_id}` | admin | Clear availability |
| `GET` | `/api/scheduling/availability/period/{period_id}` | admin | List all teachers' availability |

**Request: Set Availability**
```json
{
    "slots": [
        {"day_of_week": 0, "start_time": "07:00", "end_time": "12:00"},
        {"day_of_week": 0, "start_time": "14:00", "end_time": "18:00"},
        {"day_of_week": 1, "start_time": "07:00", "end_time": "20:00"},
        {"day_of_week": 2, "start_time": "08:00", "end_time": "13:00"}
    ]
}
```

---

### 4.11 Designations (was 4.6)

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `POST` | `/api/scheduling/designations` | admin | Create designation with slots |
| `GET` | `/api/scheduling/designations` | admin | List (query: `?period_id=&teacher_ci=&status=&subject=`) |
| `GET` | `/api/scheduling/designations/{id}` | admin | Get with slots, teacher, period |
| `PUT` | `/api/scheduling/designations/{id}` | admin | Update non-slot fields |
| `POST` | `/api/scheduling/designations/{id}/confirm` | admin | Confirm designation |
| `POST` | `/api/scheduling/designations/{id}/cancel` | admin | Cancel designation |
| `POST` | `/api/scheduling/designations/{id}/slots` | admin | Add slot to designation |
| `PUT` | `/api/scheduling/designations/{id}/slots/{slot_id}` | admin | Update slot |
| `DELETE` | `/api/scheduling/designations/{id}/slots/{slot_id}` | admin | Remove slot |
| `POST` | `/api/scheduling/designations/{id}/slots/{slot_id}/assign-room` | admin | Assign room to slot |
| `DELETE` | `/api/scheduling/designations/{id}/slots/{slot_id}/room` | admin | Unassign room |

**Request: Create Designation**
```json
{
    "teacher_ci": "1234567",
    "period_id": 1,
    "subject_id": 1,
    "group_id": 1,
    "semester_hours": 80,
    "slots": [
        {"day_of_week": 0, "start_time": "08:00", "end_time": "09:30", "room_id": 1},
        {"day_of_week": 2, "start_time": "08:00", "end_time": "09:30", "room_id": 1},
        {"day_of_week": 4, "start_time": "10:00", "end_time": "11:30"}
    ]
}
```

**Response: Designation**
```json
{
    "id": 1,
    "teacher": {"ci": "1234567", "full_name": "PEREZ Juan"},
    "academic_period": {"id": 1, "code": "I/2026", "name": "Primer Semestre 2026"},
    "subject": {"id": 1, "code": "MRF 0100", "name": "Anatomía Humana I"},
    "group": {"id": 1, "code": "M-1", "semester": {"id": 1, "number": 1, "name": "1er Semestre"}, "shift": {"code": "M", "name": "Mañana"}},
    "status": "draft",
    "source": "manual",
    "semester_hours": 80,
    "weekly_hours_calculated": 6,
    "monthly_hours": 24,
    "slots": [
        {
            "id": 1,
            "day_of_week": 0,
            "day_name": "Lunes",
            "start_time": "08:00",
            "end_time": "09:30",
            "duration_minutes": 90,
            "academic_hours": 2,
            "room": {"id": 1, "code": "A-101", "name": "Aula 101"}
        },
        {
            "id": 2,
            "day_of_week": 2,
            "day_name": "Miercoles",
            "start_time": "08:00",
            "end_time": "09:30",
            "duration_minutes": 90,
            "academic_hours": 2,
            "room": {"id": 1, "code": "A-101", "name": "Aula 101"}
        },
        {
            "id": 3,
            "day_of_week": 4,
            "day_name": "Viernes",
            "start_time": "10:00",
            "end_time": "11:30",
            "duration_minutes": 90,
            "academic_hours": 2,
            "room": null
        }
    ],
    "created_at": "2026-04-19T10:00:00"
}
```

---

### 4.12 Conflict Checking (was 4.7)

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `POST` | `/api/scheduling/conflicts/check` | admin | Validate a proposed slot |
| `GET` | `/api/scheduling/conflicts/period/{period_id}` | admin | Get all conflicts in a period |
| `GET` | `/api/scheduling/conflicts/teacher/{teacher_ci}/{period_id}` | admin | Get teacher conflicts in period |

**Request: Check Conflicts**
```json
{
    "period_id": 1,
    "teacher_ci": "1234567",
    "group_code": "M-1",
    "day_of_week": 0,
    "start_time": "08:00",
    "end_time": "09:30",
    "room_id": 1,
    "exclude_slot_id": null
}
```

**Response: Conflicts**
```json
{
    "has_hard_conflicts": true,
    "conflicts": [
        {
            "type": "ROOM_DOUBLE_BOOKING",
            "severity": "HARD",
            "message": "Aula A-101 ya ocupada Lunes 08:00-10:00 por Biologia I (M-2)",
            "conflicting_slot_id": 5,
            "details": {
                "room_code": "A-101",
                "existing_subject": "Biologia I",
                "existing_group": "M-2",
                "existing_time": "08:00-10:00"
            }
        }
    ]
}
```

---

## 5. Frontend Pages

### 5.1 New Pages

#### CareersPage (`/admin/careers`)
- Table listing careers with columns: code, name, semester count, subject count, active status
- Actions per row: edit, deactivate/reactivate, view curriculum
- Create button → modal form with: code, name, description
- Curriculum detail view: expandable accordion or tabs by semester, showing all subjects with code, name, HT, HP, CR
- Import curriculum button → upload JSON file or paste JSON → calls bulk import endpoint
- Inline subject editing (add/edit/remove subjects within a semester)

#### GroupsPage (`/admin/groups`)
- Period selector dropdown (defaults to active period)
- View organized by semester (tabs or accordion): "1er Semestre", "2do Semestre", etc.
- For each semester: table of groups with columns: code, shift, number, student count, designation count, active
- Quick-create: select semester → select shifts and numbers → bulk create (e.g. "add M-1, M-2, T-1, N-1, N-2 to 1er Semestre")
- Actions per group: edit student count, delete (if no designations)
- Visual summary: grid showing all semesters × shifts with group counts

#### AcademicPeriodsPage (`/admin/periods`)
- Table listing all periods with columns: code, name, year, status, is_active badge, designation count
- Actions per row: edit, activate, close
- Create button → modal form with fields: code, name, year, semester_number, start_date, end_date
- Active period highlighted with badge/color
- Filter by status (planning/active/closed)

#### RoomsPage (`/admin/rooms`)
- Table listing rooms with columns: code, name, building, floor, capacity, type, equipment icons, active status
- Actions per row: edit, deactivate/reactivate, manage equipment
- Create button → form with: code, name, building, floor, capacity, room type selector, equipment multi-select with quantity
- Filters: building, floor, type, active/all
- Equipment management: inline table or modal to add/remove equipment

#### DesignationManagementPage (`/admin/designations`)
- Period selector dropdown (defaults to active period)
- Table listing designations with: teacher, subject (from Subject entity), group code (from Group entity), semester, status, weekly hours, slot count
- Actions: edit, confirm, cancel, view detail
- Create button → multi-step form:
  1. Select teacher + period
  2. Select career → semester → subject (cascading dropdowns from normalized entities)
  3. Select group (filtered by period + semester, shows shift + number)
  4. Add slots (day picker, time pickers, optional room selector)
  5. Review (shows weekly hours calculation, any conflicts)
- Detail view: card with designation info + visual weekly schedule grid showing slots with room assignments
- Inline conflict warnings (real-time validation as slots are added)

#### TeacherAvailabilityPage (`/admin/availability`)
- Period selector dropdown
- Teacher selector or list view
- Weekly calendar grid where admin clicks/drags to mark available blocks
- Save replaces all slots for that teacher+period
- Visual indicator of assigned designation slots overlaid on availability

#### ConflictDashboardPage (`/admin/conflicts`)
- Period selector
- Lists all detected conflicts grouped by type (teacher overlap, room double booking, group overlap)
- Each conflict card shows: type badge, severity, involved designation details, suggested resolution
- Link to involved designations for quick editing

### 5.2 Modified Pages

#### UploadPage
- Period field: replace free-text input with dropdown selector populated from `GET /api/scheduling/periods`
- Default selection: active period
- Legacy upload still works but creates `source=legacy_import` designations

#### SchedulePage (docente portal)
- Continue showing weekly schedule view
- Data source: switch from inline `schedule_json` to `/api/scheduling/designations?teacher_ci={ci}&period_id={active}` response with slots
- Add room info to each slot display

#### TeacherDetailPage (admin)
- Designation section: show slots from new structure instead of parsing schedule_json
- Add room code per slot
- Add designation status badge (draft/confirmed/cancelled)

#### DashboardPage
- Add scheduling summary cards: total designations, rooms in use, conflicts detected (for active period)

### 5.3 Navigation

Add new sections in sidebar:
```
Gestion Academica
  ├── Carreras y Mallas
  ├── Periodos Academicos
  └── Grupos

Programacion de Horarios
  ├── Aulas
  ├── Disponibilidad Docente
  ├── Designaciones
  └── Conflictos
```

---

## 6. Module Structure (Phase 1 — File Mapping)

### 6.1 Directory Layout

```
backend/app/
├── shared/
│   ├── __init__.py
│   ├── config.py                    ← moved from app/config.py
│   ├── database.py                  ← moved from app/database.py
│   ├── middleware/
│   │   └── __init__.py
│   └── utils/
│       └── helpers.py               ← moved from app/utils/helpers.py
│
├── core/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── teacher.py               ← moved from app/models/teacher.py
│   │   ├── user.py                  ← moved from app/models/user.py
│   │   ├── career.py                ← NEW
│   │   ├── semester.py              ← NEW
│   │   ├── subject.py               ← NEW
│   │   ├── activity_log.py          ← moved from app/models/activity_log.py
│   │   ├── notification.py          ← moved from app/models/notification.py
│   │   └── detail_request.py        ← moved from app/models/detail_request.py
│   ├── schemas/
│   │   ├── teacher.py
│   │   ├── user.py
│   │   ├── career.py                ← NEW
│   │   └── subject.py               ← NEW
│   ├── services/
│   │   ├── auth_service.py          ← moved from app/services/auth_service.py
│   │   ├── activity_logger.py       ← moved from app/services/activity_logger.py
│   │   ├── career_service.py        ← NEW
│   │   ├── semester_service.py      ← NEW
│   │   └── subject_service.py       ← NEW
│   └── routers/
│       ├── auth.py                  ← moved from app/routers/auth.py
│       ├── users.py                 ← moved from app/routers/users.py
│       ├── teachers.py              ← moved from app/routers/teachers.py
│       ├── careers.py               ← NEW
│       ├── subjects.py              ← NEW (includes semester routes)
│       ├── detail_requests.py       ← moved from app/routers/detail_requests.py
│       ├── activity_log.py          ← moved from app/routers/activity_log.py
│       ├── admin.py                 ← moved from app/routers/admin.py
│       └── portal_profile.py        ← split from app/routers/docente_portal.py
│
├── scheduling/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── academic_period.py       ← NEW
│   │   ├── shift.py                 ← NEW
│   │   ├── group.py                 ← NEW
│   │   ├── room_type.py             ← NEW
│   │   ├── equipment.py             ← NEW
│   │   ├── room.py                  ← NEW
│   │   ├── room_equipment.py        ← NEW
│   │   ├── teacher_availability.py  ← NEW
│   │   ├── availability_slot.py     ← NEW
│   │   ├── designation.py           ← moved from app/models/designation.py
│   │   └── designation_slot.py      ← NEW
│   ├── schemas/
│   │   ├── period.py
│   │   ├── shift.py                 ← NEW
│   │   ├── group.py                 ← NEW
│   │   ├── room.py
│   │   ├── availability.py
│   │   └── designation.py
│   ├── services/
│   │   ├── period_service.py        ← NEW
│   │   ├── shift_service.py         ← NEW
│   │   ├── group_service.py         ← NEW
│   │   ├── room_type_service.py     ← NEW
│   │   ├── equipment_service.py     ← NEW
│   │   ├── room_service.py          ← NEW
│   │   ├── availability_service.py  ← NEW
│   │   ├── designation_service.py   ← NEW
│   │   ├── conflict_service.py      ← NEW
│   │   ├── slot_read_service.py     ← NEW (payroll read interface)
│   │   ├── compatibility_adapter.py ← NEW (transition, removed Phase 4)
│   │   ├── designation_import_legacy.py ← moved from app/services/designation_loader.py
│   │   └── schedule_pdf.py          ← moved from app/services/schedule_pdf.py
│   └── routers/
│       ├── periods.py               ← NEW
│       ├── shifts.py                ← NEW
│       ├── groups.py                ← NEW
│       ├── room_types.py            ← NEW
│       ├── equipment.py             ← NEW
│       ├── rooms.py                 ← NEW
│       ├── availability.py          ← NEW
│       ├── designations.py          ← moved from app/routers/designations.py
│       ├── conflicts.py             ← NEW
│       └── portal_schedule.py       ← split from app/routers/docente_portal.py
│
├── payroll/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── biometric.py             ← moved from app/models/biometric.py
│   │   ├── attendance.py            ← moved from app/models/attendance.py
│   │   ├── planilla.py              ← moved from app/models/planilla.py
│   │   ├── billing_publication.py   ← moved from app/models/billing_publication.py
│   │   └── report.py                ← moved from app/models/report.py
│   ├── schemas/
│   │   ├── biometric.py
│   │   ├── attendance.py
│   │   ├── planilla.py
│   │   └── billing.py
│   ├── services/
│   │   ├── biometric_parser.py      ← moved
│   │   ├── attendance_engine.py     ← moved (Phase 3: consume SlotReadService)
│   │   ├── planilla_generator.py    ← moved (Phase 3: consume SlotReadService)
│   │   ├── report_generator.py      ← moved
│   │   ├── contract_pdf.py          ← moved
│   │   ├── retention_letter_pdf.py  ← moved
│   │   └── audit_report_pdf.py      ← moved
│   └── routers/
│       ├── biometric.py             ← moved
│       ├── attendance.py            ← moved
│       ├── planilla.py              ← moved
│       ├── reports.py               ← moved
│       ├── billing_publication.py   ← moved
│       ├── contracts.py             ← moved
│       └── portal_billing.py        ← split from app/routers/docente_portal.py
│
├── main.py                          ← registers routers from all modules
└── __init__.py
```

### 6.2 Dependency Rules (enforced by convention, verified in code review)

```
shared/     → depends on nothing
core/       → depends on shared/
scheduling/ → depends on core/, shared/
payroll/    → depends on scheduling/, core/, shared/
```

**Violations that MUST NOT exist**:
- `core/` importing from `scheduling/` or `payroll/`
- `scheduling/` importing from `payroll/`
- `payroll/` importing models from `scheduling/` directly (must use `SlotReadService` or `ScheduledSlotDTO`)
- Any module importing from `shared/` other than `config`, `database`, `utils`

### 6.3 Model Registry

`main.py` must import all model `__init__.py` files to register them in `Base.metadata`:
```python
import app.core.models       # noqa: F401
import app.scheduling.models  # noqa: F401
import app.payroll.models     # noqa: F401
```

---

## 7. Migration & Compatibility (Phase 2-3 Transition)

### 7.1 Database Migration

Since the project currently uses `create_all()` + manual column migrations in `main.py`:

**Phase 1**: No schema changes. Only file moves and import path changes.

**Phase 2**: Add new tables and modify `designations`:
1. Create new tables via `create_all()`:
   - Core: `careers`, `semesters`, `subjects`
   - Scheduling: `academic_periods`, `shifts`, `groups`, `room_types`, `equipment`, `rooms`, `room_equipment`, `teacher_availabilities`, `availability_slots`, `designation_slots`
2. Seed default data:
   - Seed shifts: M (Mañana), T (Tarde), N (Noche)
   - Create default career "Medicina" with code "MED"
   - Import malla curricular from JSON file → creates 10 semesters + ~78 subjects
3. Add columns to `designations`: `academic_period_id`, `subject_id`, `group_id` (all nullable initially), `source`, `status` via `_run_column_migrations()`.
4. Data migration script:
   - Create `AcademicPeriod` record for `settings.ACTIVE_ACADEMIC_PERIOD` value.
   - Create `Group` records from existing unique `group_code` values in designations (match to shift + number).
   - Match existing `subject` strings to `Subject` records by name similarity.
   - Match existing `semester` strings to `Semester` records by number extraction.
   - Backfill `designations.academic_period_id`, `subject_id`, `group_id` from matched entities.
   - Make FK columns NOT NULL after backfill.
   - Set `source = 'legacy_import'` and `status = 'confirmed'` for all existing designations.
   - Parse each designation's `schedule_json` → create `DesignationSlot` records.
5. After successful migration, deprecated string columns (`subject`, `semester`, `group_code`, `schedule_json`) kept but only maintained by `CompatibilityAdapter`.

### 7.2 Payroll Transition (Phase 3)

**attendance_engine.py changes**:
- Replace `db.query(Designation).filter(Designation.academic_period == ...)` with `SlotReadService.get_slots_for_period(period_id)`
- Replace `schedule_json` parsing in `match_teacher_day()` with `ScheduledSlotDTO` fields
- The matching algorithm itself does NOT change — only the data source
- `ScheduledSlotDTO.day_name` provides the normalized day string (matching existing `WEEKDAY_MAP`)

**planilla_generator.py changes**:
- Replace `schedule_json` reads for ABSENT hour recovery with `SlotReadService.get_slot_hours_for_designation(designation_id, day_of_week, start_time)`
- The calculation logic does NOT change — only the lookup

### 7.3 Frontend Compatibility

- Phase 2: New scheduling pages work immediately (they only use new endpoints)
- Phase 2: Existing pages continue working because `schedule_json` is maintained by `CompatibilityAdapter`
- Phase 3: Update existing pages one by one to use new scheduling endpoints
- Phase 4: Remove `schedule_json` from responses

---

## 8. Test Scenarios

### 8.1 Academic Period

| # | Scenario | Given | When | Then |
|---|----------|-------|------|------|
| AP-1 | Create valid period | No periods exist | Create "I/2026" | Period created with status=planning, is_active=false |
| AP-2 | Reject duplicate code | "I/2026" exists | Create "I/2026" again | 409 Conflict |
| AP-3 | Reject invalid code format | — | Create "Primero/2026" | 422 Validation error |
| AP-4 | Reject invalid dates | — | Create with start > end | 422 Validation error |
| AP-5 | Activate period | "I/2026" active, "II/2026" planning | Activate "II/2026" | "I/2026" inactive, "II/2026" active+status=active |
| AP-6 | Close period | Period active, all designations confirmed | Close period | status=closed |
| AP-7 | Reject close with drafts | Period has draft designations | Close period | 409 Conflict with draft count |
| AP-8 | Reject edit on closed | Period closed | Update name | 409 Conflict |

### 8.2 Careers, Semesters & Subjects

| # | Scenario | Given | When | Then |
|---|----------|-------|------|------|
| CR-1 | Create career | — | Create "MED" / "Medicina" | Career created, active |
| CR-2 | Reject duplicate code | "MED" exists | Create "MED" again | 409 Conflict |
| CR-3 | Import curriculum | Career "MED" exists, JSON with 10 semesters | Import curriculum | 10 semesters, 78 subjects created |
| CR-4 | Import updates existing | Subject "MRF 0100" exists with HT=51 | Import with HT=60 | Subject updated, count shows 0 created, 1 updated |
| CR-5 | Elective without code | JSON has materia with `codigo: null` | Import | Subject created with `is_elective=true`, `code=null` |
| CR-6 | Delete subject with designations | Subject has active designation | Delete subject | 409 with designation count |
| CR-7 | Delete empty subject | Subject has no designations | Delete | Subject deleted |
| CR-8 | Search subjects | 3 subjects with "Anatomía" in name | Search "anatomia" | Returns 3 results |
| CR-9 | Deactivate career with designations | Career has semester with active designation | Deactivate | 409 |

### 8.3 Shifts & Groups

| # | Scenario | Given | When | Then |
|---|----------|-------|------|------|
| SG-1 | Seed default shifts | No shifts exist | Call seed_defaults | M, T, N created with correct times and order |
| SG-2 | Seed is idempotent | Shifts already exist | Call seed_defaults again | No duplicates, same 3 shifts |
| SG-3 | Create group | Period, semester, shift M exist | Create M-1 | Group created with code="M-1" |
| SG-4 | Bulk create groups | Period + 1er Semestre exist | Bulk create M-1, M-2, T-1, N-1, N-2 | 5 groups created |
| SG-5 | Reject duplicate group | M-1 exists in period+semester | Create M-1 again | 409 Conflict |
| SG-6 | Create special group | Period + semester exist | Create with is_special=true | Group created with code="G.E." |
| SG-7 | Delete group with designations | Group has designations | Delete | 409 |
| SG-8 | Delete empty group | Group has no designations | Delete | Deleted |
| SG-9 | List groups by period+semester | 5 groups in 1st sem, 3 in 2nd | List for 1st sem | Returns 5 groups ordered by shift+number |

### 8.4 Rooms & Equipment (was 8.2)

| # | Scenario | Given | When | Then |
|---|----------|-------|------|------|
| RM-1 | Create room with equipment | RoomType "AULA", Equipment "PROY" exist | Create room with equipment | Room created with equipment list |
| RM-2 | Reject duplicate code | Room "A-101" exists | Create "A-101" again | 409 Conflict |
| RM-3 | Reject capacity < 1 | — | Create room with capacity=0 | 422 Validation error |
| RM-4 | Deactivate empty room | Room with no active slots | Deactivate | Room is_active=false |
| RM-5 | Reject deactivate busy room | Room has slots in active period | Deactivate | 409 with conflicting slots |
| RM-6 | Reject delete type with rooms | RoomType has rooms | Delete type | 409 |
| RM-7 | Reject delete equipment assigned | Equipment assigned to room | Delete equipment | 409 |

### 8.5 Teacher Availability (was 8.3)

| # | Scenario | Given | When | Then |
|---|----------|-------|------|------|
| AV-1 | Set availability | Teacher + period exist | Set 5 slots | Availability created with 5 slots |
| AV-2 | Replace availability | Existing 3 slots | Set 2 new slots | Old slots deleted, 2 new created |
| AV-3 | Reject overlapping slots | — | Set Mon 8-12 and Mon 10-14 | 422 Validation error |
| AV-4 | Reject invalid time | — | Set start=14:00, end=12:00 | 422 Validation error |
| AV-5 | Clear availability | Existing slots | Clear | All slots deleted |

### 8.6 Designations & Slots (was 8.4)

| # | Scenario | Given | When | Then |
|---|----------|-------|------|------|
| DG-1 | Create designation with slots | Teacher, period, room exist | Create with 3 slots | Designation draft, weekly_hours=6, monthly_hours=24 |
| DG-2 | Auto-compute hours | Slot 08:00-09:30 (90min) | Create slot | duration_minutes=90, academic_hours=2 |
| DG-3 | Auto-compute hours rounding | Slot 08:00-09:15 (75min) | Create slot | academic_hours=round(75/45)=2 |
| DG-4 | Confirm designation | Draft designation | Confirm | status=confirmed |
| DG-5 | Reject edit confirmed | Confirmed designation | Add slot | 422 "Cannot modify confirmed designation" |
| DG-6 | Cancel designation | Draft or confirmed | Cancel | status=cancelled |
| DG-7 | Reject edit cancelled | Cancelled designation | Update subject | 422 "Cannot modify cancelled designation" |
| DG-8 | Add slot recomputes hours | Designation has 2 slots (4 hours) | Add slot with 2 hours | weekly_hours_calculated=6, monthly_hours=24 |
| DG-9 | Remove slot recomputes | Designation has 3 slots (6 hours) | Remove 1 slot (2 hours) | weekly_hours_calculated=4, monthly_hours=16 |
| DG-10 | Assign room to slot | Slot with no room, room available | Assign room | slot.room_id set |
| DG-11 | Unassign room | Slot with room | Unassign | slot.room_id = null |
| DG-12 | Schedule_json compatibility | Create designation with 3 slots | Check schedule_json | Matches legacy format exactly |

### 8.7 Conflict Detection (was 8.5)

| # | Scenario | Given | When | Then |
|---|----------|-------|------|------|
| CF-1 | Teacher overlap | Teacher has Mon 8-10 | Add Mon 9-11 for same teacher | TEACHER_OVERLAP (HARD) |
| CF-2 | No teacher overlap (adjacent) | Teacher has Mon 8-10 | Add Mon 10-12 for same teacher | No conflict |
| CF-3 | Room double booking | Room has Mon 8-10 | Add Mon 9-11 for same room | ROOM_DOUBLE_BOOKING (HARD) |
| CF-4 | No room conflict (different day) | Room has Mon 8-10 | Add Tue 8-10 same room | No conflict |
| CF-5 | Group overlap | Group M-1 has Mon 8-10 | Add Mon 9-11 for M-1 | GROUP_OVERLAP (HARD) |
| CF-6 | Room inactive | Room is_active=false | Assign to slot | ROOM_INACTIVE (HARD) |
| CF-7 | Outside availability | Teacher available Mon 8-12 | Add Mon 14-16 | OUTSIDE_AVAILABILITY (SOFT) |
| CF-8 | No availability set | Teacher has no availability | Add any slot | No conflict (skip check) |
| CF-9 | Update slot excludes self | Slot id=5 Mon 8-10 | Update slot 5 to Mon 8-11 | Excludes self from overlap check |
| CF-10 | Cancelled designation ignored | Cancelled designation has Mon 8-10 | Add Mon 8-10 for same teacher | No conflict (cancelled excluded) |

### 8.8 Compatibility & Migration (was 8.6)

| # | Scenario | Given | When | Then |
|---|----------|-------|------|------|
| CM-1 | Legacy JSON matches new slots | Designation with 3 DesignationSlots | Generate schedule_json via adapter | Output matches legacy format: dia, hora_inicio, hora_fin, duracion_minutos, horas_academicas |
| CM-2 | Attendance engine reads new structure | Designation with slots, no schedule_json | attendance_engine processes month | Same attendance results as with schedule_json |
| CM-3 | ABSENT hour recovery parity | ABSENT attendance record exists | planilla_generator recovers hours | Same hours recovered via SlotReadService as via schedule_json |
| CM-4 | Legacy upload still works | Upload designations JSON file | Process upload | Designations created with source=legacy_import, status=confirmed, DesignationSlots auto-created |
| CM-5 | Existing data migrated | 400 designations with schedule_json | Run migration script | 400 designations have matching DesignationSlot records |

### 8.9 Integration (was 8.7)

| # | Scenario | Given | When | Then |
|---|----------|-------|------|------|
| INT-1 | Full flow: period → room → designation → payroll | Create period, activate, create room, create designation with slots, confirm, process attendance | Run planilla_generator | Payroll calculated correctly using DesignationSlot data |
| INT-2 | Designation count per period | 3 designations in I/2026 | GET /api/scheduling/periods/1 | designation_count = 3 |
| INT-3 | Room occupation view | Room A-101 has 5 slots | GET room detail | Shows 5 designation slots with times |

---

## 9. Glossary

| Term | Definition |
|------|-----------|
| Career | Academic program (e.g. Medicina, Odontología). Contains semesters and subjects (malla curricular). |
| Semester | Academic level within a career (1er Semestre through 10mo Semestre for Medicina). Contains the subjects from the curriculum. |
| Subject | A course in the curriculum (e.g. "Anatomía Humana I"). Has code, hours, credits. Linked to a semester. |
| Shift | Time-of-day classification for groups: M (Mañana), T (Tarde), N (Noche). Pre-seeded, not user-created. |
| Group | A specific student group for a semester in a period (e.g. M-1 = morning group 1). Created per period by admin. |
| G.E. (Grupo Especial) | Special group for convalidación students from other universities. Has `is_special=true` and may take subjects from different semesters. |
| Academic Period | A semester (e.g. I/2026). Contains all designations, availability, and scheduling for that term. |
| Designation | Assignment of a teacher to a subject+group for a period. Has one or more time slots. |
| DesignationSlot | A single weekly class block (e.g. Monday 8:00-9:30 in Room A-101). |
| Conflict | An overlap or validation error that prevents or warns about a schedule assignment. |
| HARD conflict | Blocks the operation — cannot save. |
| SOFT conflict | Warning only — can still save. |
| Malla Curricular | The fixed curriculum of a career. Defines which subjects belong to which semester with their hours and credits. |
| schedule_json | Legacy JSON blob storing slot data inside Designation. Deprecated in Phase 2, removed in Phase 4. |
| ScheduledSlotDTO | Flat data transfer object that payroll services consume from scheduling. |
| CompatibilityAdapter | Service that generates legacy schedule_json from DesignationSlot records during transition. |
