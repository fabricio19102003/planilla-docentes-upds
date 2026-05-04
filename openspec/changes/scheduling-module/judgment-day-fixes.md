# Judgment Day Round 1 Fixes — Scheduling Module

Date: 2026-05-05  
Branch: `scheduling-module`

## Applied Fixes

- **#1** `frontend/src/pages/SchedulingPage.tsx` — removed unused `AcademicPeriod`, `TIME_SLOTS`, `dayLabel`, and `toggleCell` symbols so `noUnusedLocals` does not fail on the page.
- **#2** `backend/app/scheduling/services/conflict_service.py`, `backend/app/scheduling/services/slot_service.py` — group conflict/context resolution now prefers `Designation.group_id`; legacy fallback includes semester context instead of only `group_code + period`.
- **#3** `backend/app/scheduling/services/conflict_service.py` — teacher, room, and group overlap queries ignore `Designation.status == "cancelled"`.
- **#4** `frontend/src/pages/SchedulingPage.tsx` — slot form defaults and validation now treat day `0` (Monday) as a valid value.
- **#5** `backend/app/scheduling/routers/slots.py` — dry-run slot validation rejects `start_time >= end_time` with HTTP 422.
- **#6** `backend/app/scheduling/services/slot_service.py` — `_resolve_context` now uses relational period/group FKs first, then falls back to string fields with semester context.
- **#7** `frontend/src/pages/SchedulingPage.tsx` — availability dialog rehydrates selected grid cells whenever it is opened and `existing` availability changes, preventing late-loaded availability from being overwritten by an empty grid.
- **#8** `backend/app/scheduling/routers/slots.py`, `backend/app/scheduling/services/slot_service.py`, `frontend/src/api/hooks/useScheduling.ts`, `frontend/src/pages/SchedulingPage.tsx` — added room-based slot listing and wired room view to fetch all room slots for the selected period.
- **#9** `backend/app/scheduling/services/room_service.py` — room deactivation now rejects rooms referenced by non-cancelled slots in non-closed periods.
- **#10** `backend/app/scheduling/services/period_service.py` — period closure now rejects periods with draft designations.
- **#11** `frontend/src/pages/SchedulingPage.tsx` — create-slot submit checks backend `{ blocked: true }` responses and keeps the dialog open with conflicts instead of behaving as success.
- **#12** `backend/app/scheduling/routers/slots.py` — dry-run validation now returns HTTP 404 for missing designation and HTTP 422 for unresolved period instead of HTTP 200 with an `error` field.

## Deferred / Non-blocking

- **#13** Active-period uniqueness concurrency remains theoretical/non-blocking. Current service uses `with_for_update()` when activating a period; no heavy migration or DB partial unique index was added in this surgical pass.

## Notes for Re-judgment

- Changes intentionally avoid broad refactors and are limited to the Round 1 findings above.
- No full build was run per instruction.

---

# Judgment Day Round 2 Fixes — Scheduling Module

Date: 2026-05-05  
Branch: `scheduling-module`

## Applied Fixes

- **R2-#1** `frontend/src/api/hooks/useScheduling.ts` — `useTeacherAvailability` now includes the caller-provided `enabled` flag in the TanStack Query `enabled` expression, preserving guard behavior and satisfying `noUnusedParameters`.
- **R2-#2** `frontend/src/api/hooks/useScheduling.ts` — `usePeriodAvailabilities` now includes the caller-provided `enabled` flag in the TanStack Query `enabled` expression, preserving guard behavior and satisfying `noUnusedParameters`.
- **R2-#3** `frontend/src/pages/SchedulingPage.tsx` — `CreateSlotDialog` accepts `defaultRoomId`; room view passes the selected room so new slots opened from the room view preselect that room instead of defaulting to unassigned.
- **R2-#4** `backend/app/scheduling/routers/slots.py` — `POST /slots` no longer has a fixed route-level `201`; blocked hard-conflict creates now return HTTP `409 Conflict`, while successful creates set HTTP `201 Created` conditionally.

## Deferred / Non-blocking

- **R2-INFO** The FK-or-legacy matching drift warnings in `conflict_service.py`, `room_service.py`, and `period_service.py` remain theoretical/non-blocking for this surgical pass. No heavy migration or broad query refactor was performed because Round 2 requested only real actionable CRITICAL/WARNING fixes.

## Notes for Re-judgment

- Exact mapping: R2 issues #1–#4 were fixed in the files identified above.
- The theoretical FK/legacy drift item was documented only, per instruction.
- No full build was run per instruction.

---

# Judgment Day Round 3 Fixes — Scheduling Module

Date: 2026-05-05  
Branch: `scheduling-module`

## Applied Fixes

- **R3-#1** `frontend/src/pages/SchedulingPage.tsx` — create-slot submit now handles Axios-rejected `409 Conflict`/`blocked` responses by reading `response.data.conflicts` and `response.data.blocked`, keeping the dialog open, preserving/displaying conflict details, and using the backend/detail-aware blocked message instead of the generic create failure.

## Notes for Re-judgment

- Exact mapping: R3 issue #1 was fixed in the file identified above.
- No full build was run per instruction.
