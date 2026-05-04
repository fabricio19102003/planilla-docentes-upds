# Scheduling Module — Review Guide

The `scheduling-module` branch adds native academic scheduling to SIPAD: maintainers can manage periods, curriculum, rooms, teacher availability, and class slots directly in the app, with backend conflict checks replacing the old “schedule JSON as source of truth” flow.

## Review Outcome

| Item | Status |
|------|--------|
| Judgment Day | **APPROVED** — Round 4 was **CLEAN** from both judges |
| Real blocking issues | Fixed through Rounds 1–3 and documented in `judgment-day-fixes.md` |
| Remaining caveats | Theoretical/non-blocking only; see “Known Caveats” |
| Build | Not run, per instruction |

## Review First

Use this order to understand the branch quickly:

1. `openspec/changes/scheduling-module/judgment-day-fixes.md` — exact fixes from adversarial review.
2. `backend/app/scheduling/services/conflict_service.py` and `slot_service.py` — slot validation, conflict handling, FK/legacy context resolution.
3. `backend/app/scheduling/routers/slots.py`, `scheduling.py`, `rooms.py`, `curriculum.py`, `designations.py` — API surface.
4. `frontend/src/api/hooks/useScheduling.ts` — frontend contract and query/mutation wiring.
5. `frontend/src/pages/SchedulingPage.tsx`, `RoomsPage.tsx`, `PeriodsPage.tsx`, `CurriculumPage.tsx` — maintainer-facing flows.
6. `frontend/src/App.tsx` and `frontend/src/components/layout/Sidebar.tsx` — route/sidebar integration.

## Out of Scope

- Auto-generating schedules with a solver.
- Non-class room booking such as exams or external events.
- Fully removing the legacy `schedule_json`/string-period transition path.
- Heavy migration work for theoretical FK/legacy drift or DB-level active-period uniqueness.

## What Was Added

| Capability | What to look for |
|------------|------------------|
| Academic periods | Create/list/update/activate/close periods under `/api/scheduling/periods`. |
| Rooms and equipment | Room types, equipment, rooms, room equipment, and soft deactivation rules. |
| Curriculum | Careers, semesters, subjects, and curriculum import flow. |
| Groups and shifts | Period-scoped groups tied to semesters and default seeded shifts. |
| Teacher availability | Availability slots per teacher and period. |
| Class slots | Relational `DesignationSlot` CRUD, room assignment, dry-run validation, and compatibility JSON sync. |
| Conflict handling | Teacher overlap, room double-booking, group overlap, inactive rooms, and outside-availability warnings. |

## Backend Concepts

### Periods

- A period has `planning`, `active`, or `closed` status.
- Activating a period deactivates any other active period in the same transaction path.
- Closing a period is blocked if draft designations remain.

### Rooms

- Rooms are soft-deactivated, not hard-deleted.
- A room cannot be deactivated while non-cancelled slots in non-closed periods still reference it.
- Room assignment checks room overlap and inactive-room conflicts.

### Curriculum and Groups

- Curriculum is modeled through careers, semesters, and subjects.
- Groups are period-scoped and tied to semester + shift.
- Slot conflict context prefers relational FKs, then falls back to legacy strings during transition.

### Availability and Slots

- Teacher availability is stored as period-specific availability slots.
- Class slots compute duration and academic hours from start/end time.
- Successful slot writes sync the transition `schedule_json` through the compatibility adapter.

### Conflict Handling

| Conflict | Severity | Behavior |
|----------|----------|----------|
| Teacher overlap | HARD | Blocks create/update. |
| Room double-booking | HARD | Blocks create/update/assign-room. |
| Group overlap | HARD | Blocks create/update. |
| Missing/inactive room | HARD | Blocks room assignment or slot creation with room. |
| Outside teacher availability | SOFT | Returned to the UI, but does not block save. |

## Frontend Flows

| Page | Reviewer focus |
|------|----------------|
| `SchedulingPage.tsx` | Period selection, teacher/room/weekly views, slot create/update/delete, availability dialog, blocked conflict display. |
| `RoomsPage.tsx` | Room type/equipment/room CRUD, room detail, soft delete/deactivation constraints. |
| `PeriodsPage.tsx` | Period lifecycle, groups by semester, shifts panel. |
| `CurriculumPage.tsx` | Careers, semesters, subjects, and curriculum JSON import result handling. |
| `useScheduling.ts` | TanStack Query keys, enabled guards, scheduling mutations, conflict payload typing. |

## Judgment Day Business Rules Now Enforced

- Day `0` is treated as a valid Monday value in slot forms.
- Dry-run validation rejects `start_time >= end_time` with HTTP `422`.
- Missing designations return HTTP `404`; unresolved periods return HTTP `422`.
- Cancelled designations are ignored by overlap checks.
- Group matching prefers `Designation.group_id`; legacy fallback includes semester context.
- Room view fetches room slots by selected room + period.
- Room-view slot creation preselects the selected room.
- Hard-conflict slot creation returns HTTP `409`, not success with a hidden blocked payload.
- The frontend catch path reads Axios-rejected `409` payloads and keeps the dialog open with conflict details.
- Period closure rejects periods with draft designations.
- Room deactivation rejects rooms used by non-cancelled slots in non-closed periods.

## Known Caveats

These were classified as theoretical/non-blocking by Judgment Day and were not fixed in this branch:

- **FK/legacy period matching drift**: transitional queries support both relational FKs and legacy period/group strings. A broad cleanup/migration was intentionally deferred.
- **Active-period concurrency**: service-level activation uses `with_for_update()`, but no heavier DB partial unique index or migration was added in this surgical pass.

## Verification Status

| Check | Result |
|-------|--------|
| Backend `py_compile` on touched files | Passed |
| Frontend lint | Could not run locally because dependencies/local ESLint setup were missing. |
| Frontend typecheck | Could not run locally because dependencies were missing. |
| Build | Not run, per instruction. |

## Reviewer Checklist

- [ ] Confirm the API routers are registered in `backend/app/main.py`.
- [ ] Review conflict severity behavior: HARD blocks, SOFT returns warnings.
- [ ] Confirm `POST /scheduling/slots` returns `409` for hard conflicts and `201` for successful creates.
- [ ] Confirm slot validation handles bad times, missing designations, and unresolved periods with proper HTTP statuses.
- [ ] Confirm room and period lifecycle rules match the business expectations above.
- [ ] Confirm frontend slot dialogs preserve/display backend conflict details.
- [ ] Confirm room view filters slots by selected room and period.
- [ ] Treat the FK/legacy drift and active-period concurrency notes as known theoretical caveats, not unresolved blocking findings.
