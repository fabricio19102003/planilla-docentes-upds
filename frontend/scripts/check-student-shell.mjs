import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

// S1/S2/S4/S6/S9/S10: the student portal shell (brand band, icon top nav, mobile notch bar, account menu, 404).

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')
const layout = read('src/pages/student/StudentPortalLayout.tsx')
const notFound = read('src/pages/student/StudentNotFoundPage.tsx')
const app = read('src/App.tsx')
const css = read('src/index.css')

const DESTINATIONS = [
  ['/estudiante', 'Inicio'],
  ['/estudiante/horario', 'Mi horario'],
  ['/estudiante/rematricula', 'Rematrícula'],
  ['/estudiante/historial', 'Historial académico'],
  ['/estudiante/intensivos', 'Cursos de verano e invierno'],
]

test('the layout keeps the session guards, the brand toggle and the page-enter outlet', () => {
  assert.match(layout, /localStorage\.getItem\(STUDENT_TOKEN_KEY\)[\s\S]*?<Navigate to="\/estudiante\/login" replace \/>/)
  assert.match(layout, /me\.data\?\.must_change_password[\s\S]*?<Navigate to="\/estudiante\/cambiar-clave" replace \/>/)
  assert.match(layout, /<ThemeToggle\b[^>]*variant="brand"/)
  assert.match(layout, /<main\b[^>]*key=\{pathname\}[^>]*page-enter/)
  assert.match(layout, /me\.data\.full_name/, 'the student name stays in the band')
})

test('five destinations feed both the top nav and the mobile bar, with their icons and short labels', () => {
  for (const [to, label] of DESTINATIONS) {
    assert.ok(layout.includes(`to: '${to}'`), `${to} is a destination`)
    assert.ok(layout.includes(`'${label}'`), `${label} label`)
  }
  assert.equal(layout.match(/\bto: '\/estudiante[^']*'/g)?.length, 5, 'exactly five destinations in the config')
  for (const icon of ['House', 'CalendarDays', 'ClipboardPen', 'GraduationCap', 'Sun']) {
    assert.match(layout, new RegExp(`\\b${icon}\\b`), `${icon} icon`)
  }
  for (const short of ['Horario', 'Historial', 'Cursos']) assert.ok(layout.includes(`'${short}'`), `${short} short label`)
})

test('the desktop top nav marks the active link and slides an underline between items', () => {
  assert.match(layout, /<nav\b[^>]*aria-label="Principal"/)
  assert.match(layout, /<NavLink\b[\s\S]*?end=\{end\}/, 'NavLink sets aria-current="page" on the active destination')
  assert.doesNotMatch(layout, /aria-current=\{[^}]*false/, 'no manual aria-current that could drift from the route')
  assert.match(layout, /layoutId=/)
  assert.match(layout, /useReducedMotion/)
  assert.match(layout, /duration: 0/, 'reduced motion lands on the same underline without sliding')
  assert.match(layout, /hidden md:/, 'the top nav is desktop only')
  assert.match(layout, /focus-visible:/, 'visible focus on the links')
  assert.match(layout, /active:scale-95/, 'press feedback')
})

test('the mobile bar is the R1 NotchTabBar, reserves space and never hides content', () => {
  assert.match(layout, /import \{[^}]*NotchTabBar[^}]*\} from '@\/components\/student'/)
  assert.match(layout, /<NotchTabBar\b[^>]*label="Navegación"/)
  assert.match(layout, /<NotchTabBar\b[^>]*md:hidden/)
  assert.match(layout, /<main\b[^>]*pb-\[calc\([^)]*env\(safe-area-inset-bottom\)\)\][^>]*md:pb-/, 'bottom padding covers the bar and the safe area')
})

test('the account menu holds Cambiar contraseña and Salir, reachable in two taps', () => {
  assert.match(layout, /<Menu>[\s\S]*<MenuTrigger[\s\S]*aria-label=\{[^}]*Cuenta/)
  assert.match(layout, /<MenuPopup[\s\S]*Cambiar contraseña[\s\S]*Salir[\s\S]*<\/MenuPopup>/)
  assert.match(layout, /navigate\('\/estudiante\/cambiar-clave'\)/)
  assert.match(layout, /logout\(\)[\s\S]*navigate\('\/estudiante\/login', \{ replace: true \}\)/)
  assert.doesNotMatch(layout, /to: '\/estudiante\/cambiar-clave'/, 'the password link left the nav')
  assert.match(layout, /min-h-11/, 'menu items reach 44px')
})

// The splat is absolute like its siblings: a bare path="*" would be parsed as a staff page by check-navigation.
test('the 404 route lives under the /estudiante layout and renders the Spanish clinic 404 contained', () => {
  assert.match(app, /import \{ StudentNotFoundPage \} from '\.\/pages\/student\/StudentNotFoundPage'/)
  assert.match(app, /<Route path="\/estudiante" element=\{<StudentPortalLayout \/>\}>[\s\S]*<Route path="\/estudiante\/\*" element=\{<StudentNotFoundPage \/>\} \/>[\s\S]*?<\/Route>/)
  assert.match(notFound, /<ClinicNotFound\b[^>]*\bcontained\b/, 'fixed would cover the band and the bottom bar')
  assert.match(notFound, /relative/, 'the contained 404 needs a positioned parent')
  assert.doesNotMatch(notFound, /title=|message=|ctaLabel=/, 'copy comes from the Spanish defaults of ClinicNotFound')
})

test('layout and 404 follow the page rules: no hex, gradients or palette classes', () => {
  for (const [name, source] of [['layout', layout], ['404', notFound]]) {
    assert.doesNotMatch(source, /#[0-9a-fA-F]{3,8}\b/, `${name}: hex colour`)
    assert.doesNotMatch(source, /gradient/i, `${name}: gradient`)
    assert.doesNotMatch(source, /\b(?:bg|text|border|ring|from|to|via|fill|stroke|shadow)-(?:red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|slate|gray|zinc|neutral|stone)-\d/, `${name}: palette class`)
  }
})

test('the underline colour is a student token utility, not a literal', () => {
  assert.match(css, /--color-student-accent-line:\s*var\(--student-accent-line\)/)
  assert.match(layout, /bg-student-accent-line/)
})
