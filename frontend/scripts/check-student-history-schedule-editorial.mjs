import assert from 'node:assert/strict'
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import { averageDecimals, historyCounts, periodTone } from '../src/components/student/history/history-view.ts'
import {
  buildDayTimeline,
  clockLabel,
  MIN_BLOCK_PX,
  nowPosition,
  PX_PER_HOUR,
  TONE_COUNT,
  toneIndex,
} from '../src/lib/studentDayTimeline.ts'

// T7 (S1-S3): Historial as a period timeline with grade figures and meters, Horario "Hoy" as a day timeline
// with a time axis, a "now" line and subject-colored blocks. The layout math is pure and lives in lib.

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')
const filesIn = (dir) =>
  existsSync(resolve(root, dir))
    ? readdirSync(resolve(root, dir), { recursive: true, withFileTypes: true })
        .filter((item) => item.isFile() && /\.(tsx|ts|css)$/.test(item.name))
        .map((item) => resolve(item.parentPath ?? item.path, item.name))
    : []

const cls = (subject_code, start_time, end_time, over = {}) => ({ subject_code, subject_name: subject_code, start_time, end_time, ...over })
const at = (hours, minutes = 0) => hours * 60 + minutes

// ---- Day timeline math -------------------------------------------------------------------------

test('a day without classes has no timeline at all', () => {
  assert.equal(buildDayTimeline([], at(10)), null)
  // Entries with unreadable times cannot be placed, so they do not make a timeline either.
  assert.equal(buildDayTimeline([cls('A', '', '09:00'), cls('B', 'xx:yy', '09:00')], at(10)), null)
})

test('the axis runs from the hour of the earliest class to the hour after the latest one, with hourly ticks', () => {
  const timeline = buildDayTimeline([cls('A', '07:30', '09:00'), cls('B', '11:00', '12:30'), cls('C', '12:45', '13:45')], null)
  assert.equal(timeline.startMinutes, at(7))
  assert.equal(timeline.endMinutes, at(14))
  assert.deepEqual(timeline.ticks.map((tick) => tick.label), ['07:00', '08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00'])
  assert.deepEqual(timeline.ticks.map((tick) => tick.top), [0, 1, 2, 3, 4, 5, 6, 7].map((hour) => hour * PX_PER_HOUR))
  assert.equal(timeline.height, 7 * PX_PER_HOUR)
})

test('a class ending on the hour does not add an extra hour to the axis', () => {
  const timeline = buildDayTimeline([cls('A', '08:00', '10:00')], null)
  assert.equal(timeline.startMinutes, at(8))
  assert.equal(timeline.endMinutes, at(10))
})

test('each block is placed by its start time and sized by its duration', () => {
  const timeline = buildDayTimeline([cls('A', '07:30', '09:00'), cls('B', '11:00', '12:30')], null)
  const [first, second] = timeline.blocks
  assert.equal(first.top, 0.5 * PX_PER_HOUR)
  assert.equal(first.height, 1.5 * PX_PER_HOUR)
  assert.equal(second.top, 4 * PX_PER_HOUR)
  assert.equal(second.height, 1.5 * PX_PER_HOUR)
  assert.deepEqual([first.lane, first.lanes, second.lane, second.lanes], [0, 1, 0, 1])
  assert.equal(first.entry.subject_code, 'A')
})

test('blocks come in time order whatever the input order', () => {
  const timeline = buildDayTimeline([cls('B', '11:00', '12:00'), cls('A', '08:00', '09:00')], null)
  assert.deepEqual(timeline.blocks.map((block) => block.entry.subject_code), ['A', 'B'])
})

test('a very short class keeps a readable minimum height', () => {
  const [block] = buildDayTimeline([cls('A', '08:00', '08:20')], null).blocks
  assert.equal(block.height, MIN_BLOCK_PX)
  // A class that ends before it starts (bad data) still renders at the minimum instead of a negative height.
  const [broken] = buildDayTimeline([cls('A', '09:00', '08:00')], null).blocks
  assert.equal(broken.height, MIN_BLOCK_PX)
})

test('overlapping classes share the width in lanes and a later class reuses a free lane', () => {
  const timeline = buildDayTimeline([
    cls('A', '08:00', '10:00'),
    cls('B', '09:00', '11:00'),
    cls('C', '10:00', '12:00'),
    cls('D', '13:00', '14:00'),
  ], null)
  const lane = Object.fromEntries(timeline.blocks.map((block) => [block.entry.subject_code, [block.lane, block.lanes]]))
  // A and B overlap, C starts when A ends so it takes A's lane, and D is alone in its own cluster.
  assert.deepEqual(lane, { A: [0, 2], B: [1, 2], C: [0, 2], D: [0, 1] })
})

test('a class that starts when another ends does not overlap it', () => {
  const timeline = buildDayTimeline([cls('A', '08:00', '09:00'), cls('B', '09:00', '10:00')], null)
  assert.deepEqual(timeline.blocks.map((block) => [block.lane, block.lanes]), [[0, 1], [0, 1]])
})

test('the now line sits inside the range proportionally to the time', () => {
  const entries = [cls('A', '08:00', '09:00'), cls('B', '11:00', '12:00')]
  const timeline = buildDayTimeline(entries, at(10, 30))
  assert.deepEqual(timeline.now, { state: 'within', minutes: at(10, 30), top: 2.5 * PX_PER_HOUR, label: '10:30' })
})

test('before the first hour or after the last one there is no now line, only the state', () => {
  const entries = [cls('A', '08:30', '09:30'), cls('B', '11:00', '12:30')]
  assert.deepEqual(buildDayTimeline(entries, at(6, 45)).now, { state: 'before', minutes: at(6, 45), top: null, label: '06:45' })
  assert.deepEqual(buildDayTimeline(entries, at(14, 5)).now, { state: 'after', minutes: at(14, 5), top: null, label: '14:05' })
  // The first and the last axis minute are inside; one minute outside is not.
  assert.equal(buildDayTimeline(entries, at(8)).now.state, 'within')
  assert.equal(buildDayTimeline(entries, at(13)).now.state, 'within')
  assert.equal(buildDayTimeline(entries, at(13) + 1).now.state, 'after')
  assert.equal(buildDayTimeline(entries, at(8) - 1).now.state, 'before')
  assert.equal(buildDayTimeline(entries, null).now, null)
})

test('each block says whether it is done, in progress or later at the given time', () => {
  const entries = [cls('A', '08:00', '09:00'), cls('B', '09:15', '10:45'), cls('C', '11:00', '12:00')]
  const states = (minutes) => buildDayTimeline(entries, minutes).blocks.map((block) => block.status)
  assert.deepEqual(states(at(10)), ['done', 'now', 'later'])
  // A class is over at its end time and in progress at its start time.
  assert.deepEqual(states(at(9)), ['done', 'later', 'later'])
  assert.deepEqual(states(at(9, 15)), ['done', 'now', 'later'])
  assert.deepEqual(states(at(6)), ['later', 'later', 'later'])
  assert.deepEqual(states(at(23)), ['done', 'done', 'done'])
  assert.deepEqual(states(null), ['later', 'later', 'later'])
})

test('nowPosition and clockLabel format the same way the timeline does', () => {
  assert.equal(clockLabel(at(7)), '07:00')
  assert.equal(clockLabel(at(13, 5)), '13:05')
  assert.deepEqual(nowPosition(at(9, 30), at(8), at(12)), { state: 'within', minutes: at(9, 30), top: 1.5 * PX_PER_HOUR, label: '09:30' })
  assert.equal(nowPosition(at(7), at(8), at(12)).state, 'before')
  assert.equal(nowPosition(at(12, 1), at(8), at(12)).state, 'after')
})

// ---- Subject colors ----------------------------------------------------------------------------

test('the color of a subject is stable, within range and the same every call', () => {
  assert.ok(Number.isInteger(TONE_COUNT) && TONE_COUNT >= 5)
  for (const code of ['FUN 0300', 'MRF 0200', 'LIN 0230', '', 'ñandú']) {
    const tone = toneIndex(code)
    assert.ok(Number.isInteger(tone) && tone >= 0 && tone < TONE_COUNT, `${code} -> ${tone}`)
    assert.equal(toneIndex(code), tone)
  }
  // Pinned so a change of the hash (which would recolor every subject for every student) is deliberate.
  assert.deepEqual(['FUN 0300', 'MRF 0200', 'LIN 0230', 'FUN 0310'].map((code) => toneIndex(code)), [0, 1, 2, 5])
  assert.equal(toneIndex('FUN 0300', 3), toneIndex('FUN 0300', 3))
})

test('different subjects spread over several colors and the same subject keeps one color across blocks', () => {
  const codes = ['FUN 0300', 'FUN 0310', 'MRF 0200', 'MRF 0210', 'LIN 0230', 'PSI 0200', 'SCP 0300', 'CIR 0300', 'INF 0310', 'CBC 0300']
  assert.ok(new Set(codes.map((code) => toneIndex(code))).size >= 4, 'the hash must not collapse to one or two colors')
  const timeline = buildDayTimeline([cls('FUN 0300', '08:00', '09:00'), cls('FUN 0300', '10:00', '11:00'), cls('MRF 0200', '12:00', '13:00')], null)
  assert.equal(timeline.blocks[0].tone, timeline.blocks[1].tone)
  assert.equal(timeline.blocks[0].tone, toneIndex('FUN 0300'))
})

// ---- Historial view rules ----------------------------------------------------------------------

const term = (code, is_intensive = false) => ({ code, name: code, year: 2025, kind: 'I', is_intensive })
const record = (id, subject_code, status, grade = null) => ({
  legacy_registration_id: id, subject_code, subject_name: subject_code, group_code: null, shift: null,
  teacher_name: null, status, grade, in_curriculum: true,
})

test('the summary legend counts subjects to retake (failed and never approved) and subjects in progress', () => {
  const history = [
    { term: term('2026-I'), records: [record(1, 'A', 'reprobado', 40), record(2, 'B', 'pendiente'), record(3, 'C', 'pendiente'), record(4, 'D', 'reprobado', 30)] },
    { term: term('2025-II'), records: [record(5, 'D', 'aprobado', 60), record(6, 'E', 'retirado'), record(7, 'F', 'aprobado', 80)] },
  ]
  // A is still failed; D was failed and then approved so it is not to retake; E is withdrawn and counts as neither.
  assert.deepEqual(historyCounts(history), { approved: 2, total: 6, toRetake: 1, inProgress: 2 })
  assert.deepEqual(historyCounts([]), { approved: 0, total: 0, toRetake: 0, inProgress: 0 })
})

test('the period average shows only the decimals it has, and a period has one tone that flags problems first', () => {
  assert.equal(averageDecimals(75), 0)
  assert.equal(averageDecimals(62.5), 1)
  assert.equal(averageDecimals(51.67), 2)
  assert.equal(averageDecimals(null), 0)
  assert.equal(periodTone([record(1, 'A', 'aprobado', 70), record(2, 'B', 'reprobado', 30), record(3, 'C', 'pendiente')]), 'bad')
  assert.equal(periodTone([record(1, 'A', 'aprobado', 70), record(3, 'C', 'pendiente')]), 'warn')
  assert.equal(periodTone([record(1, 'A', 'aprobado', 70), record(2, 'B', 'retirado')]), 'ok')
  assert.equal(periodTone([]), 'default')
})

// ---- Static: the generic lists are gone and the editorial pieces are used ----------------------

const HISTORY_FILES = ['src/components/students/StudentHistoryTimeline.tsx', ...filesIn('src/components/student/history')]
const SCHEDULE_FILES = ['src/pages/student/StudentSchedulePage.tsx', ...filesIn('src/components/student/schedule')]
const source = (files) => files.map((file) => (existsSync(file) ? readFileSync(file, 'utf8') : read(file))).join('\n')

test('Historial and Horario have no divide-y lists left', () => {
  assert.doesNotMatch(source(HISTORY_FILES), /divide-y/)
  assert.doesNotMatch(source(SCHEDULE_FILES), /divide-y/)
  assert.doesNotMatch(read('src/pages/student/StudentHistoryPage.tsx'), /divide-y/)
})

test('Historial uses the Timeline primitives, figures, rings and meters for the summary and the grades', () => {
  const code = source(HISTORY_FILES)
  assert.match(code, /<Timeline\b/)
  assert.match(code, /<TimelineItem\b/)
  assert.match(code, /<DisplayFigure\b/)
  assert.match(code, /<ProgressRing\b/)
  assert.match(code, /<Meter\b/)
  assert.match(code, /<Sheet\b/)
  assert.ok(code.includes('Promedio general') && code.includes('Materias aprobadas'))
})

test('Historial explains "Fuera de malla" and the subject code with an InfoTip', () => {
  const code = source(HISTORY_FILES)
  assert.ok(code.includes('Fuera de malla'))
  assert.match(code, /<InfoTip\b[^>]*>[\s\S]{0,600}Fuera de malla|Fuera de malla[\s\S]{0,600}<InfoTip\b/)
  assert.ok((code.match(/<InfoTip\b/g) ?? []).length >= 3, 'average, progress/approved, fuera de malla and code are explained')
})

test('failed subjects are highlighted and every outcome has its own icon and tone', () => {
  const code = source(HISTORY_FILES)
  assert.match(code, /data-outcome=/)
  for (const icon of ['CircleCheck', 'CircleX', 'Hourglass', 'LogOut']) assert.match(code, new RegExp(`\\b${icon}\\b`), `${icon} icon`)
  const css = read('src/styles/student/history.css')
  assert.match(css, /\[data-outcome='failed'\]/)
})

test('Horario Hoy draws the day timeline with the axis, the now line, colored blocks and tooltips on room and teacher', () => {
  const code = source(SCHEDULE_FILES)
  assert.match(code, /buildDayTimeline\(/)
  assert.match(code, /boliviaClock\(/)
  assert.match(code, /<InfoTip\b/)
  assert.match(code, /America\/La_Paz|boliviaClock/)
  for (const icon of ['Clock', 'MapPin', 'User']) assert.match(code, new RegExp(`\\b${icon}\\b`), `${icon} icon`)
  const css = read('src/styles/student/schedule.css')
  for (let tone = 0; tone < TONE_COUNT; tone += 1) assert.ok(css.includes(`data-tone='${tone}'`), `tone ${tone} is defined`)
  assert.match(css, /\.sp-day-now/)
})

test('Horario keeps the Hoy / Semana / Próximo switch and the info alert', () => {
  const code = read('src/pages/student/StudentSchedulePage.tsx')
  assert.match(code, /<GlassSwitch\b/)
  for (const text of ['Hoy', 'Semana', 'Próximo']) assert.ok(code.includes(`'${text}'`), `${text} is an option`)
  assert.match(code, /<Alert variant="info"/)
  assert.ok(code.includes('Este horario todavía no empezó a regir; puede cambiar hasta esa fecha.'))
})

test('the new styles live in their own files, are imported by the pages and use tokens, not literal colors', () => {
  const history = read('src/styles/student/history.css')
  const schedule = read('src/styles/student/schedule.css')
  assert.match(source(HISTORY_FILES) + read('src/pages/student/StudentHistoryPage.tsx'), /styles\/student\/history\.css/)
  assert.match(source(SCHEDULE_FILES), /styles\/student\/schedule\.css/)
  for (const [name, css] of [['history.css', history], ['schedule.css', schedule]]) {
    assert.deepEqual(css.match(/#[0-9a-fA-F]{3,8}\b/g) ?? [], [], `${name} must not contain hex colors`)
    assert.deepEqual(css.match(/\brgba?\(/g) ?? [], [], `${name} must not use rgb()/rgba()`)
    assert.match(css, /prefers-reduced-motion: reduce/, `${name} ends on the same state with reduced motion`)
    assert.match(css, /:focus-visible/, `${name} keeps a visible focus`)
  }
})
