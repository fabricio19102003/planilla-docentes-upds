# Proposal: Scheduling Module

## Intent

The intent of this change is to evolve the SIPAD system by introducing a native scheduling module, shifting away from importing Excel/JSON files as the primary source of truth. By managing class schedules, classrooms, and teacher assignments directly within the system using a new modular structure, we eliminate structural coupling, improve data integrity, and provide a foundation for detecting scheduling conflicts (room double-booking, teacher overlap, etc.). This ensures the system can act as the authoritative source for academic scheduling rather than just a payroll processor of external files.

## Scope

### In Scope
- Restructure the monolithic backend into `shared/`, `core/`, `scheduling/`, and `payroll/` modules with unidirectional dependencies.
- Normalize `AcademicPeriod` as an admin-managed database entity instead of a settings string.
- Introduce `Room`, `RoomType`, and `Equipment` models to manage physical spaces and their metadata.
- Replace the legacy `schedule_json` blob with a relational `DesignationSlot` model to manage class schedules and academic hours.
- Implement conflict detection for V1 (room double-booking, teacher overlap, group overlap, and capacity/equipment validation).
- Adapt existing payroll modules (`attendance_engine`, `planilla_generator`) to consume schedule data via service-layer DTOs instead of direct model imports.

### Out of Scope
- Auto-generation solver (OR-Tools) for schedules (deferred to V2).
- Room booking for non-class events like exams or external events (deferred).
- Subject/Group/Career normalization (deferred until needed).
- Fully dropping the legacy manual schedule loading immediately (the legacy import pipeline will be phased out in a later phase, but V1 focuses on creating the native structure).

## Capabilities

### New Capabilities
- `scheduling-management`: Creating and managing designations, academic periods, rooms, equipment, and teacher availability.
- `conflict-detection`: Validating schedule assignments against overlapping teacher, room, and group schedules.

### Modified Capabilities
- `attendance-generation`: The attendance engine must read from the new `DesignationSlot` models (or compatibility DTOs) instead of parsing `schedule_json`.
- `payroll-calculation`: The planilla generator must compute absent-hour recovery against the relational slots.
- `docente-portal`: The teacher schedule visualization needs to consume the new scheduling module endpoints instead of the mixed payroll/core endpoints.

## Approach

We will use a **compatibility-first phased approach** to transition to the new architecture without breaking existing payroll and attendance logic:
1. **Phase 1 (Structural Refactor)**: Move existing files into the new `shared/`, `core/`, `scheduling/`, and `payroll/` module directories. Fix imports and introduce module-level service boundaries. No new features yet.
2. **Phase 2 (Scheduling Models)**: Implement the new authoritative scheduling models (`AcademicPeriod`, `Room`, `RoomType`, `Equipment`, `TeacherAvailability`, `DesignationSlot`) and conflict detection services.
3. **Phase 3 (Payroll Integration)**: Update `attendance_engine` and `planilla_generator` to consume scheduling DTOs provided by the scheduling service instead of relying on `Designation.schedule_json`. Create compatibility adapters for frontend pages.
4. **Phase 4 (Deprecation)**: Deprecate the legacy JSON/Excel import pipeline once the new native scheduling flows are verified.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/models/designation.py` | Modified | Relocated to `scheduling/`, replaces `schedule_json` with `DesignationSlot` relation, adds `academic_period_id`. |
| `backend/app/services/attendance_engine.py` | Modified | Relocated to `payroll/`, updated to consume `ScheduledSlotDTO` instead of direct model. |
| `backend/app/services/planilla_generator.py` | Modified | Relocated to `payroll/`, updated to calculate absent hours against relational slots. |
| `backend/app/routers/docente_portal.py` | Modified | Split into `scheduling/routers/portal_schedule.py`, `payroll/routers/portal_billing.py`, and `core/routers/portal_profile.py`. |
| `frontend/src/pages/SchedulePage.tsx` | Modified | Updated to consume the new schedule API DTOs. |
| `frontend/src/pages/UploadPage.tsx` | Modified | Updated to allow explicit selection of a configured `AcademicPeriod` entity. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Silent drift in ABSENT deduction calculations due to slot matching logic changes. | High | Implement parallel run/tests comparing legacy `schedule_json` absent deductions against the new `DesignationSlot` data before full cutover. |
| Broken frontend screens due to changes in nested teacher designation DTOs. | Medium | Build compatibility API adapters that project `DesignationSlot` data back into the legacy `schedule_json` shape during the transition phases. |
| Start-up failures due to flat migration logic in `main.py` depending on old structure. | Medium | Carefully sequence model moves and ensure Alembic or start-up scripts are updated to recognize the new modular Base registries. |

## Rollback Plan

If the new scheduling module or payroll integrations fail in production during Phase 3, we will revert the deployment to the Phase 1 state (structural refactor only) and restore the `schedule_json` data from the backup snapshot taken prior to Phase 2. The temporary compatibility endpoints will remain active to ensure the frontend continues operating with legacy data while fixes are developed.

## Dependencies

- None external. Relies on existing FastAPI/SQLAlchemy/React stack.

## Success Criteria

- [ ] All code is organized into `shared`, `core`, `scheduling`, and `payroll` directories with no cross-module model imports.
- [ ] Admin can create an `AcademicPeriod` and activate it, replacing the settings string.
- [ ] Admin can create `Room`, `Equipment`, and assign class schedules that persist to `DesignationSlot`.
- [ ] System actively rejects scheduling conflicts (teacher double-booking, room overlap).
- [ ] Payroll (`planilla_generator`) successfully calculates identical payable hours using the new slot data structure compared to a legacy control set.