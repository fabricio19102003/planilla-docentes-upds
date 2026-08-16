## Exploration: medicine-schedule-assistant

### Current State

SIPAD already has a strong designation/import pipeline built around `Designation`, `schedule_json`, and the admin upload flow. Today, `backend/app/services/designation_loader.py` normalizes Excel/JSON inputs into stored schedules, and `backend/app/routers/designations.py` still depends on that legacy intake path. The docente schedule UI (`frontend/src/pages/SchedulePage.tsx`, `frontend/src/api/hooks/useAuth.ts`) also assumes the current designation-shaped DTOs.

The existing `scheduling-module` change points in a different direction: it proposes a native scheduling platform that moves away from Excel as the source of truth. This new change is intentionally separate and should not overwrite that work. Here, the product direction is narrower: Medicine-only, Excel-first import from the current `horarios-med.xlsx` structure, with versioned uploads, validation, manual correction, and explicit activation.

The standalone parser at `/home/pedro/projects/planilla-docuentes/horarios_med_query.py` is useful groundwork, but it remains outside SIPAD and should be treated as validated reference behavior, not the implementation target.

### Affected Areas
- `backend/app/routers/designations.py` — current upload entry point; likely needs a Medicine-specific import/versioning branch or adapter.
- `backend/app/services/designation_loader.py` — current normalization logic; useful baseline for Excel parsing and compatibility shapes.
- `backend/app/models/designation.py` — existing schedule source-of-truth model; conflicts with versioned assistant semantics if reused blindly.
- `backend/app/routers/docente_portal.py` — schedule retrieval and legacy DTO shape that the assistant may need to reuse or extend.
- `frontend/src/pages/UploadPage.tsx` — admin upload flow and academic period handling.
- `frontend/src/pages/SchedulePage.tsx` — current weekly schedule rendering; likely reusable for synchronized calendar/table views.
- `frontend/src/api/hooks/useAuth.ts` — schedule/PDF download hooks.
- `openspec/changes/scheduling-module/*` — explicit architectural conflict boundary; must stay intact.

### Approaches
1. **Medicine assistant as a compatibility layer over the existing SIPAD import flow** — keep the current Excel shape, add versioning/preview/validation/manual correction/activation, and expose simulation/recommendation features as a separate Medicine domain slice.
   - Pros: lowest disruption; preserves current workbook semantics; aligns with the approved scope; can reuse parser/DTOs and existing schedule rendering.
   - Cons: transitional duplication; needs careful adapter boundaries; legacy designation concepts remain visible.
   - Effort: High

2. **Fold Medicine into the native `scheduling-module` rewrite** — treat Medicine as just another scheduling slice inside the broader modular refactor.
   - Pros: cleaner long-term architecture if the rewrite already existed.
   - Cons: directly conflicts with the agreed product direction; risks overwriting the separate `scheduling-module`; loses the Excel-first constraint and the specific simulation/versioning rules.
   - Effort: Very High

### Recommendation

Use the compatibility-layer approach, but keep `medicine-schedule-assistant` as a separate OpenSpec change with explicit coexistence rules. The proposal should define Medicine-only bounded contexts for import/versioning, simulation, and export while leaving `scheduling-module` untouched. That gives a safe path for Excel-based operational workflows without forcing the broader scheduling rewrite to absorb conflicting assumptions.

### Risks
- The biggest architectural risk is the conflict with `scheduling-module`: one change wants to leave Excel behind, the other requires versioned Excel import and combination recommendations.
- Simulation rules are domain-dense and easy to under-specify, especially the hard/soft preference split, conflict tolerance, and ranking order.
- Validation flows must be strict enough that errors block activation while warnings require explicit acceptance; otherwise the audit trail becomes unreliable.
- Saving only the selected simulation means the persistence model must preserve exact filters, metrics, and warnings or exports will not be reproducible.

### Ready for Proposal
Yes — the next proposal should define the Medicine-only boundaries, coexistence with the existing `scheduling-module`, the versioned Excel lifecycle, and the persisted simulation/export contract.
