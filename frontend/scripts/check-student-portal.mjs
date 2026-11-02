import assert from 'node:assert/strict'
import test from 'node:test'

import { buildSubmission, estimateAmounts, groupLabel, shiftLabel, submissionProblem } from '../src/lib/studentPortalState.ts'

const scholarship = { category: 'sin_beca', label: 'Sin beca', average: 55, never_failed: false, cuota: 1600, cuotas: 5, total: 8000 }
const eligibility = {
  target_semester: 3,
  recursado: [
    { code: 'LIN 0130', name: 'Inglés Técnico I', semester: 1, is_elective: false },
    { code: 'MRF 0110', name: 'Embriología', semester: 1, is_elective: false },
    { code: 'MRF 0120', name: 'Histología', semester: 1, is_elective: false },
    { code: 'MRF 0200', name: 'Anatomía II', semester: 2, is_elective: false },
  ],
  pending: [{ code: 'CBC 0200', name: 'Caso Básico II', semester: 2, is_elective: false }],
  scholarship,
  recursado_fee: { per_subject: 1200, subjects: 4, charged_subjects: 3, total: 3600 },
}

test('the submission keeps only subjects with a chosen group', () => {
  assert.deepEqual(buildSubmission(7, { 'LIN 0130': 3, 'MRF 0110': '', 'CBC 0200': 9 }), {
    main_group_id: 7,
    items: [{ subject_code: 'LIN 0130', group_id: 3 }, { subject_code: 'CBC 0200', group_id: 9 }],
  })
})

test('amounts follow the chosen recursado subjects and charge three at most', () => {
  assert.deepEqual(estimateAmounts(eligibility, {}), {
    scholarshipLabel: 'Sin beca', cuota: 1600, cuotas: 5, cuotasTotal: 8000,
    recursadoChosen: 0, recursadoCharged: 0, recursadoTotal: 0,
  })
  const all = { 'LIN 0130': 1, 'MRF 0110': 1, 'MRF 0120': 1, 'MRF 0200': 2, 'CBC 0200': 2 }
  assert.deepEqual(estimateAmounts(eligibility, all), {
    scholarshipLabel: 'Sin beca', cuota: 1600, cuotas: 5, cuotasTotal: 8000,
    recursadoChosen: 4, recursadoCharged: 3, recursadoTotal: 3600,
  })
  // A pending (Retirado-only) subject never adds the recursado fee.
  assert.equal(estimateAmounts(eligibility, { 'CBC 0200': 2 }).recursadoTotal, 0)
})

test('groups show shift and free places', () => {
  assert.equal(shiftLabel('M'), 'Mañana')
  assert.equal(shiftLabel('T'), 'Tarde')
  assert.equal(shiftLabel('N'), 'Noche')
  assert.equal(shiftLabel('EXTRA'), 'EXTRA')
  const group = { id: 1, code: 'M-01', shift: 'M', semester: 3, capacity: 40, taken: 37, free: 3, is_full: false }
  assert.equal(groupLabel(group), 'M-01 · Mañana · 3 cupos libres')
  assert.equal(groupLabel({ ...group, free: 1 }), 'M-01 · Mañana · 1 cupo libre')
  assert.equal(groupLabel({ ...group, free: 0, is_full: true }), 'M-01 · Mañana · sin cupos')
  assert.equal(groupLabel({ ...group, capacity: null, free: null }), 'M-01 · Mañana')
})

test('the form explains what is missing before sending', () => {
  const view = { window: { is_open: true }, eligibility, main_groups: [{ id: 7 }], request: null }
  assert.equal(submissionProblem(view, null), 'Elegí el grupo de tu semestre.')
  assert.equal(submissionProblem(view, 7), null)
  assert.equal(submissionProblem({ ...view, window: { is_open: false } }, 7), 'La rematrícula no está abierta.')
  assert.equal(submissionProblem({ ...view, request: { status: 'realizada' } }, 7), 'Tu rematrícula ya fue realizada.')
  assert.equal(submissionProblem({ ...view, main_groups: [] }, null), 'Todavía no hay grupos abiertos para tu semestre; consultá en Registro.')
  assert.equal(submissionProblem({ ...view, eligibility: { ...eligibility, target_semester: null } }, null),
    'No encontramos tu historial académico; acercate a Registro.')
})
