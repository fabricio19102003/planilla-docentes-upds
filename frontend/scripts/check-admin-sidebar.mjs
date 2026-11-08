import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import { adminNav, adminQuickAccess, getActiveGroupLabel } from '../src/lib/navigation.ts'
import {
  FOOTER_GROUP_LABELS,
  getSearchSections,
  isSearchShortcut,
  showGroupPendingDot,
  splitAdminGroups,
  syncOpenGroup,
  toggleOpenGroup,
} from '../src/lib/adminSidebar.ts'

const root = resolve(import.meta.dirname, '..')
const sidebar = readFileSync(resolve(root, 'src/components/layout/Sidebar.tsx'), 'utf8')

const allPages = adminNav.flatMap((entry) => ('children' in entry ? entry.children : [entry]))
const group = (label) => adminNav.find((entry) => 'children' in entry && entry.label === label)
const key = (overrides) => ({ key: 'k', ctrlKey: true, metaKey: false, altKey: false, shiftKey: false, target: null, ...overrides })

test('opening a group closes the previous one and clicking it again closes everything', () => {
  assert.equal(toggleOpenGroup(null, 'Docentes'), 'Docentes')
  assert.equal(toggleOpenGroup('Cierre mensual', 'Docentes'), 'Docentes')
  assert.equal(toggleOpenGroup('Docentes', 'Docentes'), null)
})

test('the group of the current route opens on load and on route change', () => {
  assert.equal(syncOpenGroup(null, '/planilla', adminNav), 'Cierre mensual')
  assert.equal(syncOpenGroup('Cierre mensual', '/teachers/9', adminNav), 'Docentes')
  assert.equal(syncOpenGroup('Docentes', '/settings', adminNav), 'Sistema')
  assert.equal(syncOpenGroup('Docentes', '/chat', adminNav), 'Docentes')
})

test('routes outside any group keep the current accordion state', () => {
  assert.equal(syncOpenGroup('Estudiantes', '/', adminNav), 'Estudiantes')
  assert.equal(syncOpenGroup(null, '/', adminNav), null)
  assert.equal(syncOpenGroup('Docentes', '/no-such-page', adminNav), 'Docentes')
})

test('group lookup follows the current path, nested paths included', () => {
  assert.equal(getActiveGroupLabel('/reports', adminNav), 'Cierre mensual')
  assert.equal(getActiveGroupLabel('/classroom-reservations', adminNav), 'Académico')
  assert.equal(getActiveGroupLabel('/', adminNav), undefined)
})

test('Sistema lives in the footer and the other groups stay in the scroll area', () => {
  assert.deepEqual(FOOTER_GROUP_LABELS, ['Sistema'])
  const { topLevel, main, footer } = splitAdminGroups(adminNav)
  assert.deepEqual(topLevel.map((item) => item.to), ['/'])
  assert.deepEqual(main.map((entry) => entry.label), ['Cierre mensual', 'Docentes', 'Académico', 'Estudiantes'])
  assert.deepEqual(footer.map((entry) => entry.label), ['Sistema'])
})

test('search lists every admin page exactly once, grouped by section', () => {
  const sections = getSearchSections(adminNav)
  assert.deepEqual(sections.map((section) => section.value), [
    'Inicio',
    'Cierre mensual',
    'Docentes',
    'Académico',
    'Estudiantes',
    'Sistema',
  ])

  const listed = sections.flatMap((section) => section.items)
  assert.deepEqual(listed.map((item) => item.to).sort(), allPages.map((item) => item.to).sort())
  assert.equal(new Set(listed.map((item) => item.to)).size, listed.length)

  for (const section of sections) {
    for (const item of section.items) assert.equal(item.section, section.value)
  }
  assert.deepEqual(
    sections.find((section) => section.value === 'Académico').items.map((item) => item.label),
    group('Académico').children.map((item) => item.label),
  )
  assert.deepEqual(sections[0].items.map((item) => item.label), ['Dashboard'])
})

test('search items expose the label the filter matches on', () => {
  const item = getSearchSections(adminNav).flatMap((section) => section.items).find((entry) => entry.to === '/planilla')
  assert.equal(item.label, 'Planilla')
  assert.equal(item.value, '/planilla')
})

test('quick access has four entries and the unread dot only shows on a closed Docentes group', () => {
  assert.equal(adminQuickAccess.length, 4)
  const docentes = group('Docentes')
  assert.equal(showGroupPendingDot(docentes, 3, false), true)
  assert.equal(showGroupPendingDot(docentes, 3, true), false)
  assert.equal(showGroupPendingDot(docentes, 0, false), false)
  assert.equal(showGroupPendingDot(group('Académico'), 3, false), false)
})

test('Ctrl+K and Cmd+K open the search except while typing', () => {
  assert.equal(isSearchShortcut(key({})), true)
  assert.equal(isSearchShortcut(key({ key: 'K' })), true)
  assert.equal(isSearchShortcut(key({ ctrlKey: false, metaKey: true })), true)
  assert.equal(isSearchShortcut(key({ target: { tagName: 'DIV', isContentEditable: false } })), true)

  assert.equal(isSearchShortcut(key({ ctrlKey: false })), false)
  assert.equal(isSearchShortcut(key({ key: 'j' })), false)
  assert.equal(isSearchShortcut(key({ altKey: true })), false)
  assert.equal(isSearchShortcut(key({ target: { tagName: 'INPUT', isContentEditable: false } })), false)
  assert.equal(isSearchShortcut(key({ target: { tagName: 'TEXTAREA', isContentEditable: false } })), false)
  assert.equal(isSearchShortcut(key({ target: { tagName: 'SELECT', isContentEditable: false } })), false)
  assert.equal(isSearchShortcut(key({ target: { tagName: 'DIV', isContentEditable: true } })), false)
})

test('Sidebar keeps the collapsible rail and wires the search dialog', () => {
  assert.match(sidebar, /collapsible="icon"/)
  assert.match(sidebar, /<SidebarRail\b/)
  assert.match(sidebar, /@\/components\/ui\/command/)
  assert.match(sidebar, /<CommandDialog\b/)
  assert.match(sidebar, /Buscar sección/)
  assert.match(sidebar, /Ctrl K/)
  assert.match(sidebar, /isSearchShortcut/)
  assert.match(sidebar, /Accesos rápidos/)
  assert.match(sidebar, /adminQuickAccess/)
})

test('group headers are accessible disclosure buttons with a reduced-motion safe transition', () => {
  assert.match(sidebar, /aria-expanded=\{/)
  assert.match(sidebar, /aria-controls=\{/)
  assert.match(sidebar, /syncOpenGroup/)
  assert.match(sidebar, /toggleOpenGroup/)
  assert.match(sidebar, /motion-reduce:transition-none/)
  assert.match(sidebar, /sr-only/)
})

test('collapsed groups become one icon button that opens a Menu of links', () => {
  assert.match(sidebar, /<Menu>/)
  assert.match(sidebar, /<MenuPopup\b[^>]*side="right"/)
  assert.match(sidebar, /MenuLinkItem/)
  assert.match(sidebar, /iconMode/)
  assert.match(sidebar, /useChatUnreadCount/)
  assert.match(sidebar, /separatorBefore/)
})
