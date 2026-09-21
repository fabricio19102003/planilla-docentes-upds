import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const page = readFileSync(new URL('../src/pages/ReportsPage.tsx', import.meta.url), 'utf8')

test('attendance preview renders regular and practice records with stable provenance keys', () => {
  assert.match(page, /rec\.record_kind === 'practice' \? 'Práctica' : 'Regular'/)
  assert.match(page, /rec\.record_kind}:\$\{rec\.source_key}:\$\{rec\.date}:\$\{rec\.scheduled_start}/)
  assert.match(page, /JUSTIFIED: 'Justificado'/)
})

test('reconciliation preview exposes separated source semantics and stable source keys', () => {
  assert.match(page, /'Fuente'/)
  assert.match(page, /row\.source \?\? '—'/)
  assert.match(page, /row\.source_keys \?\? \[\]/)
})
