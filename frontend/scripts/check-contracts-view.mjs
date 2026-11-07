import assert from 'node:assert/strict'
import test from 'node:test'

import {
  changeKindLabel,
  changeKindTone,
  contractVersionLabel,
  currentLines,
  filterHistory,
  groupByTeacher,
  historyKpis,
  historyPeriods,
  kindCounts,
} from '../src/lib/contractHistoryView.ts'

function line(overrides = {}) {
  return {
    line_number: 1,
    activity_kind: 'theory',
    hourly_rate: 20,
    hours: 10,
    subject_label: 'Álgebra',
    group_label: 'A',
    source_kind: 'published',
    source_id: 1,
    change_kind: 'full',
    ...overrides,
  }
}

function doc(overrides = {}) {
  return {
    public_id: 'doc-1',
    teacher_ci: '100',
    teacher_name: 'Zulema Rojas',
    academic_period: 'I/2026',
    document_kind: 'original',
    amendment_sequence: 0,
    version: 1,
    lines: [line()],
    ...overrides,
  }
}

const HISTORY = [
  doc({ public_id: 'a2', teacher_ci: '200', teacher_name: 'Álvaro Peña', document_kind: 'amendment', amendment_sequence: 1, version: 2, lines: [line({ source_id: 2, hours: 4, hourly_rate: 30, change_kind: 'added' })] }),
  doc({ public_id: 'z1', teacher_ci: '100', teacher_name: 'Zulema Rojas', lines: [line({ source_id: 1, hours: 10, hourly_rate: 20 })] }),
  doc({ public_id: 'a1', teacher_ci: '200', teacher_name: 'Álvaro Peña', lines: [line({ source_id: 1, hours: 8, hourly_rate: 25 })] }),
]

test('groupByTeacher orders teachers by name and versions ascending', () => {
  const groups = groupByTeacher(HISTORY)
  assert.deepEqual(groups.map((g) => g.teacher_name), ['Álvaro Peña', 'Zulema Rojas'])
  assert.deepEqual(groups[0].documents.map((d) => d.public_id), ['a1', 'a2'])
  assert.equal(groups[0].teacher_ci, '200')
  assert.deepEqual(groupByTeacher([]), [])
})

test('historyKpis counts documents, kinds and distinct teachers', () => {
  const kpis = historyKpis(HISTORY)
  assert.equal(kpis.documents, 3)
  assert.equal(kpis.originals, 2)
  assert.equal(kpis.amendments, 1)
  assert.equal(kpis.teachers, 2)
})

test('historyKpis totals the current load: original lines plus later added lines', () => {
  const kpis = historyKpis(HISTORY)
  // Álvaro: 8h x 25 + 4h x 30 = 320; Zulema: 10h x 20 = 200
  assert.equal(kpis.hours, 22)
  assert.equal(kpis.amount, 520)
})

test('currentLines applies changed and removed amendment lines over the original', () => {
  const [group] = groupByTeacher([
    doc({ public_id: 'o', lines: [line({ source_id: 1, hours: 8 }), line({ source_id: 2, hours: 6, line_number: 2 })] }),
    doc({
      public_id: 'e1', document_kind: 'amendment', amendment_sequence: 1, version: 2,
      lines: [line({ source_id: 1, hours: 12, change_kind: 'changed' }), line({ source_id: 2, hours: 0, change_kind: 'removed' })],
    }),
  ])
  const lines = currentLines(group)
  assert.equal(lines.length, 1)
  assert.equal(lines[0].hours, 12)
})

test('currentLines only follows the teacher latest period', () => {
  const [group] = groupByTeacher([
    doc({ public_id: 'old', academic_period: 'II/2025', lines: [line({ source_id: 9, hours: 50 })] }),
    doc({ public_id: 'new', academic_period: 'I/2026', lines: [line({ source_id: 1, hours: 5 })] }),
  ])
  assert.deepEqual(currentLines(group).map((l) => l.hours), [5])
})

test('historyKpis on an empty history is all zero', () => {
  assert.deepEqual(historyKpis([]), { documents: 0, originals: 0, amendments: 0, teachers: 0, hours: 0, amount: 0 })
})

test('filterHistory searches teacher name or CI ignoring accents and case', () => {
  assert.deepEqual(filterHistory(HISTORY, { search: 'alvaro' }).map((d) => d.public_id).sort(), ['a1', 'a2'])
  assert.deepEqual(filterHistory(HISTORY, { search: '  PEÑA ' }).length, 2)
  assert.deepEqual(filterHistory(HISTORY, { search: '100' }).map((d) => d.public_id), ['z1'])
  assert.equal(filterHistory(HISTORY, { search: 'nadie' }).length, 0)
  assert.equal(filterHistory(HISTORY, {}).length, 3)
})

test('filterHistory narrows by period and kind', () => {
  const mixed = [...HISTORY, doc({ public_id: 'old', academic_period: 'II/2025' })]
  assert.deepEqual(filterHistory(mixed, { period: 'II/2025' }).map((d) => d.public_id), ['old'])
  assert.equal(filterHistory(mixed, { period: 'all' }).length, 4)
  assert.deepEqual(filterHistory(mixed, { kind: 'amendment' }).map((d) => d.public_id), ['a2'])
  assert.equal(filterHistory(mixed, { kind: 'original' }).length, 3)
  assert.equal(filterHistory(mixed, { kind: 'all' }).length, 4)
})

test('kindCounts and historyPeriods summarise a history', () => {
  assert.deepEqual(kindCounts(HISTORY), { all: 3, original: 2, amendment: 1 })
  assert.deepEqual(kindCounts([]), { all: 0, original: 0, amendment: 0 })
  const mixed = [...HISTORY, doc({ public_id: 'old', academic_period: 'II/2025' }), doc({ public_id: 'newer', academic_period: 'II/2026' })]
  assert.deepEqual(historyPeriods(mixed), ['II/2026', 'I/2026', 'II/2025'])
  assert.deepEqual(historyPeriods([]), [])
})

test('change kinds map to tones and Spanish labels', () => {
  assert.equal(changeKindTone('added'), 'success')
  assert.equal(changeKindTone('removed'), 'destructive')
  assert.equal(changeKindTone('changed'), 'warning')
  assert.equal(changeKindTone('full'), 'neutral')
  assert.equal(changeKindTone('otro'), 'neutral')
  assert.equal(changeKindLabel('added'), 'Agregada')
  assert.equal(changeKindLabel('removed'), 'Quitada')
  assert.equal(changeKindLabel('changed'), 'Modificada')
  assert.equal(changeKindLabel('full'), 'Completa')
  assert.equal(changeKindLabel('otro'), 'Completa')
})

test('contract versions are labelled Original and Versión N, never as amendments', () => {
  assert.equal(contractVersionLabel({ document_kind: 'original', amendment_sequence: 0 }), 'Original')
  assert.equal(contractVersionLabel({ document_kind: 'amendment', amendment_sequence: 1 }), 'Versión 2')
  assert.equal(contractVersionLabel({ document_kind: 'amendment', amendment_sequence: 2 }), 'Versión 3')
})
