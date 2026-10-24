import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import {
  adminNav,
  docenteNav,
  FALLBACK_TITLE,
  getActiveGroupLabel,
  getDocenteNavItems,
  getTitleFromPath,
  isRetentionVisible,
} from '../src/lib/navigation.ts'

const root = resolve(import.meta.dirname, '..')
const app = readFileSync(resolve(root, 'src/App.tsx'), 'utf8')

function routedPaths() {
  const paths = []
  const portalStart = app.indexOf('path="/portal"')
  assert.ok(portalStart > 0, 'portal route block not found in App.tsx')
  for (const match of app.matchAll(/<Route\s+(?:index|path="([^"]+)")/g)) {
    const raw = match[1]
    const inPortal = match.index > portalStart
    if (raw === undefined) {
      paths.push(inPortal ? '/portal' : '/')
    } else if (raw.startsWith('/')) {
      continue // layout wrappers and public pages (/login, /change-password) have no layout header
    } else {
      paths.push(inPortal ? `/portal/${raw}` : `/${raw}`)
    }
  }
  return paths.map((path) => path.replace(':ci', '123'))
}

test('admin sidebar keeps the monthly-closing order', () => {
  const shape = adminNav.map((entry) =>
    'children' in entry
      ? { group: entry.label, items: entry.children.map((child) => [child.label, child.to]) }
      : { top: [entry.label, entry.to] },
  )

  assert.deepEqual(shape, [
    { top: ['Dashboard', '/'] },
    {
      group: 'Cierre mensual',
      items: [
        ['Subir biométrico', '/upload'],
        ['Asistencia teóricas', '/attendance'],
        ['Asistencia prácticas', '/practice-attendance'],
        ['Observaciones', '/observations'],
        ['Auditoría de asistencia', '/attendance-audit'],
        ['Planilla', '/planilla'],
        ['Reportes', '/reports'],
      ],
    },
    {
      group: 'Docentes y académico',
      items: [
        ['Docentes', '/teachers'],
        ['Contratos', '/contracts'],
        ['Gestión académica', '/academic-management'],
        ['Planificador de horarios', '/schedule-planner'],
        ['Solicitudes', '/requests'],
        ['Mensajes', '/chat'],
      ],
    },
    {
      group: 'Administración',
      items: [
        ['Usuarios', '/users'],
        ['Registro de actividad', '/activity'],
        ['Respaldos', '/backup'],
        ['Configuración', '/settings'],
      ],
    },
  ])
})

test('every routed page resolves to its own non-fallback title', () => {
  const paths = routedPaths()
  assert.ok(paths.length >= 25, `expected to parse App.tsx routes, got ${paths.length}`)

  const titles = new Map()
  for (const path of paths) {
    const title = getTitleFromPath(path)
    assert.notEqual(title, FALLBACK_TITLE, `${path} falls back to the generic title`)
    titles.set(path, title)
  }

  // Redirect-only route shares the Planilla title; every other page title is unique.
  const unique = new Map()
  for (const [path, title] of titles) {
    if (path === '/practice-planilla') continue
    // The admin inbox and the docente conversation are both labelled "Mensajes".
    if (path === '/portal/chat') continue
    assert.ok(!unique.has(title), `${path} reuses the title of ${unique.get(title)}: ${title}`)
    unique.set(title, path)
  }
})

test('sidebar labels and header titles agree for admin items', () => {
  for (const entry of adminNav) {
    const items = 'children' in entry ? entry.children : [entry]
    for (const item of items) {
      assert.equal(getTitleFromPath(item.to), item.label, item.to)
    }
  }
})

test('portal titles do not fall back to the /portal title', () => {
  assert.equal(getTitleFromPath('/portal'), 'Mi Facturación')
  assert.equal(getTitleFromPath('/portal/schedule'), 'Mi Horario')
  assert.equal(getTitleFromPath('/portal/retention-letter'), 'Carta de Retención')
  assert.equal(getTitleFromPath('/portal/history'), 'Histórico')
  assert.equal(getTitleFromPath('/portal/requests'), 'Mis Solicitudes')
  assert.equal(getTitleFromPath('/portal/profile'), 'Mi Perfil')
  assert.equal(getTitleFromPath('/portal/notifications'), 'Notificaciones')
  assert.equal(getTitleFromPath('/portal/chat'), 'Mensajes')
})

test('nested and unknown paths', () => {
  assert.equal(getTitleFromPath('/teachers/123'), 'Detalle de Docente')
  assert.equal(getTitleFromPath('/teachers'), 'Docentes')
  assert.equal(getTitleFromPath('/planilla/'), 'Planilla')
  assert.equal(getTitleFromPath('/no-such-page'), FALLBACK_TITLE)
})

test('active group follows the current route, including nested paths', () => {
  assert.equal(getActiveGroupLabel('/planilla', adminNav), 'Cierre mensual')
  assert.equal(getActiveGroupLabel('/teachers/9', adminNav), 'Docentes y académico')
  assert.equal(getActiveGroupLabel('/settings', adminNav), 'Administración')
  assert.equal(getActiveGroupLabel('/', adminNav), undefined)
})

test('retention item is shown unless the profile says false', () => {
  assert.equal(isRetentionVisible(true), true)
  assert.equal(isRetentionVisible(undefined), true)
  assert.equal(isRetentionVisible(false), false)

  const hasLetter = (items) => items.some((item) => item.to === '/portal/retention-letter')
  assert.equal(hasLetter(getDocenteNavItems(true)), true)
  assert.equal(hasLetter(getDocenteNavItems(undefined)), true)
  assert.equal(hasLetter(getDocenteNavItems(false)), false)
  assert.equal(getDocenteNavItems(false).length, docenteNav.length - 1)
})
