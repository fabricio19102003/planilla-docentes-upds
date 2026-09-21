import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  resolutionDesignationKey,
  resolutionSlotKey,
  selectAdminRequestEvidence,
} from '../src/lib/adminRequestResolution.ts'

const page = readFileSync(new URL('../src/pages/AdminRequestsPage.tsx', import.meta.url), 'utf8')
const panel = readFileSync(new URL('../src/components/requests/ResolutionSnapshotPanel.tsx', import.meta.url), 'utf8')

const historicalSnapshot = {
  kind: 'schedule_detail',
  academic_period: 'I/2026',
  effective_date: '2026-04-01',
  designations: [{
    subject: 'Historical Anatomy',
    semester: '1',
    group_code: 'A',
    weekly_hours: 2,
    monthly_hours: 8,
    source_kind: 'published',
    source_id: 7,
    source_key: 'published:7',
    schedule: [{ dia: 'Lunes', hora_inicio: '08:00', hora_fin: '09:30', horas_academicas: 2 }],
  }],
}

test('resolved requests select immutable snapshots and discard newer live context', () => {
  const live = { publication: 'published:99', subject: 'New Current Anatomy' }
  const evidence = selectAdminRequestEvidence(
    { status: 'approved', resolution_snapshot: historicalSnapshot },
    live,
  )

  assert.equal(evidence.kind, 'historical')
  assert.equal(evidence.snapshot.designations[0].source_key, 'published:7')
  assert.equal('live' in evidence, false)
})

test('old resolved requests are explicit legacy fallback and pending requests may use live context', () => {
  assert.deepEqual(
    selectAdminRequestEvidence({ status: 'rejected', resolution_snapshot: null }, { current: true }),
    { kind: 'legacy-fallback' },
  )
  assert.deepEqual(
    selectAdminRequestEvidence({ status: 'pending', resolution_snapshot: null }, { current: true }),
    { kind: 'live-pending', live: { current: true } },
  )
})

test('historical schedule keys prefer typed source identity and remain null safe', () => {
  const designation = historicalSnapshot.designations[0]
  const designationKey = resolutionDesignationKey(designation)
  assert.equal(designationKey, 'published:7')
  assert.equal(
    resolutionSlotKey(designationKey, designation.schedule[0]),
    'published:7|Lunes|08:00|09:30|2|0',
  )
  assert.equal(
    resolutionDesignationKey({
      subject: 'Legacy', semester: '2', group_code: 'B', weekly_hours: null,
      monthly_hours: null, source_key: null, schedule: [],
    }),
    'legacy-unknown|Legacy|B|2|unknown|0',
  )
})

test('admin rendering exposes authoritative and fallback labels without loading live resolved data', () => {
  assert.match(page, /request\?\.status === 'pending'/)
  assert.match(page, /Evidencia histórica autoritativa/)
  assert.match(page, /Resolución histórica guardada/)
  assert.match(page, /Solicitud histórica sin evidencia guardada/)
  assert.match(page, /El contexto actual no se usa como reemplazo/)
  assert.match(page, /aria-label="Solicitud histórica sin resolución guardada"/)
  assert.match(panel, /aria-labelledby=\{headingId\}/)
  assert.match(panel, /aria-label="Detalle biométrico histórico"/)
})
