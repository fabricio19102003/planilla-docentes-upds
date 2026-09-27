import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import { designationAliasSelectionState } from '../src/lib/designationBootstrapState.ts'

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')
const page = read('src/pages/SchedulePlannerPage.tsx')
const dialog = read('src/components/academic-management/DesignationBootstrapDialog.tsx')
const fields = read('src/components/academic-management/DesignationBootstrapFields.tsx')
const preview = read('src/components/academic-management/DesignationBootstrapPreview.tsx')
const resolver = read('src/components/academic-management/DesignationAliasResolver.tsx')
const api = read('src/api/academicManagement.ts')
const types = read('src/api/types.ts')
const bootstrapSource = `${dialog}\n${fields}\n${preview}\n${resolver}\n${api}`

test('integrates the one-time bootstrap with the existing schedule planner', () => {
  assert.match(page, /DesignationBootstrapDialog/)
  assert.match(dialog, /Importación inicial de designaciones/)
  assert.match(dialog, /Continuar en el borrador/)
  assert.doesNotMatch(page, /designation-bootstrap\/apply/)
})

test('uses fixed II/2026 scope and digest-bound preview then apply APIs', () => {
  assert.match(api, /DESIGNATION_BOOTSTRAP_PERIOD = 'II\/2026'/)
  assert.match(api, /DESIGNATION_BOOTSTRAP_EFFECTIVE_DATE = '2026-08-21'/)
  assert.match(api, /designation-bootstrap\/preview/)
  assert.match(api, /designation-bootstrap\/apply/)
  assert.match(api, /confirmation_digest/)
  assert.match(dialog, /21 de agosto de 2026/)
  assert.doesNotMatch(dialog, /type="date"/)
})

test('defines complete typed preview and apply contracts', () => {
  for (const contract of [
    'DesignationBootstrapPreview',
    'DesignationBootstrapApplyResult',
    'DesignationBootstrapPracticeSummary',
    'DesignationBootstrapResolutionSummary',
  ]) assert.match(types, new RegExp(`interface ${contract}`))
})

test('keeps files in browser memory and exposes accessible states and confirmation', () => {
  assert.match(dialog, /useState<DesignationBootstrapSelectedFiles>/)
  assert.doesNotMatch(bootstrapSource, /localStorage|sessionStorage|console\./)
  assert.match(bootstrapSource, /aria-describedby=/)
  assert.match(fields, /aria-invalid=/)
  assert.match(bootstrapSource, /role="alert"/)
  assert.match(dialog, /role="status"/)
  assert.match(dialog, /aria-busy=/)
  assert.match(dialog, /Confirmo la fecha efectiva y los conteos anteriores/)
  assert.match(dialog, /disabled=\{!confirmed \|\| busy\}/)
})

test('resolves aliases entirely in-app with native labeled controls', () => {
  assert.match(api, /designation-bootstrap\/resolution-context/)
  assert.match(api, /designation-bootstrap\/alias-artifact/)
  assert.match(preview, /Resolver coincidencias/)
  assert.match(resolver, /Resolver coincidencias exactas/)
  assert.match(resolver, /<Label htmlFor=/)
  assert.match(resolver, /<select/)
  assert.match(resolver, /Seleccione una coincidencia/)
  assert.match(resolver, /Seleccione una materia/)
  assert.match(dialog, /new File\(\[artifact\], 'designation-alias-v2\.json'/)
  assert.match(dialog, /await generatePreview\(aliasFile\)/)
})

test('discards stale async results and locks source controls while busy', () => {
  assert.match(dialog, /const requestGeneration = useRef\(0\)/)
  assert.match(dialog, /generation !== requestGeneration\.current/)
  assert.match(dialog, /if \(!nextOpen && busy\) return/)
  assert.match(dialog, /<DialogContent aria-busy=\{busy\}/)
  assert.match(dialog, /disabled=\{busy\}/)
  assert.match(fields, /disabled=\{disabled\}/)
  assert.match(dialog, /role="status" aria-live="polite"/)
})

test('keeps full CI and technical artifact instructions out of the primary flow', () => {
  assert.match(resolver, /masked_ci/)
  assert.match(resolver, /El CI completo permanece protegido en el servidor/)
  assert.doesNotMatch(resolver, /salary_ci|ci_raw/)
  assert.doesNotMatch(`${dialog}\n${preview}\n${resolver}`, /suba.*JSON|obtenga.*JSON|solicite.*archivo/i)
  assert.match(fields, /<details/)
  assert.match(fields, /Opciones avanzadas/)
  assert.match(preview, /Siguiente acción:/)
  assert.doesNotMatch(`${dialog}\n${resolver}`, /JSON\.stringify/)
})

test('builds complete explicit selections only after every native control has a value', () => {
  const context = {
    resolution_token: 'opaque', expires_in_seconds: 900,
    teacher_resolutions: [{
      official_teacher_display: 'Docente oficial', official_teacher_key: 'DOCENTE OFICIAL',
      candidates: [{ candidate_token: 'token-1', salary_teacher_display: 'Docente salarial', salary_teacher_key: 'DOCENTE SALARIAL', masked_ci: '••••1234' }],
    }],
    subject_resolutions: [{
      salary_subject_display: 'Materia salarial', salary_subject_key: 'MATERIA SALARIAL', semester: 2,
      candidates: [{ official_subject_display: 'Materia oficial', official_subject_key: 'MATERIA OFICIAL' }],
    }],
  }
  assert.equal(designationAliasSelectionState(context, {}, {}).complete, false)
  assert.deepEqual(
    designationAliasSelectionState(
      context,
      { 'DOCENTE OFICIAL': 'token-1' },
      { '2:MATERIA SALARIAL': 'MATERIA OFICIAL' },
    ),
    {
      complete: true,
      selections: {
        teacher_selections: [{ official_teacher_key: 'DOCENTE OFICIAL', candidate_token: 'token-1' }],
        subject_selections: [{ salary_subject_key: 'MATERIA SALARIAL', semester: 2, official_subject_key: 'MATERIA OFICIAL' }],
      },
    },
  )
})
