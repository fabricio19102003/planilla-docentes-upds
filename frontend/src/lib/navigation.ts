export type NavIconName =
  | 'dashboard'
  | 'calendarCheck'
  | 'upload'
  | 'attendance'
  | 'audit'
  | 'observations'
  | 'planilla'
  | 'reports'
  | 'academic'
  | 'teachers'
  | 'contracts'
  | 'designations'
  | 'school'
  | 'schedule'
  | 'requests'
  | 'settings'
  | 'users'
  | 'activity'
  | 'backup'
  | 'billing'
  | 'history'
  | 'letter'
  | 'notifications'
  | 'messages'
  | 'profile'

export interface NavItemDef {
  to: string
  label: string
  icon: NavIconName
  exact?: boolean
  badge?: number
}

export interface NavGroupDef {
  label: string
  icon: NavIconName
  children: NavItemDef[]
}

export type AdminNavEntry = NavItemDef | NavGroupDef

export const FALLBACK_TITLE = 'UPDS Planilla'
export const RETENTION_LETTER_PATH = '/portal/retention-letter'

export const adminNav: AdminNavEntry[] = [
  { to: '/', label: 'Dashboard', icon: 'dashboard', exact: true },
  {
    label: 'Cierre mensual',
    icon: 'calendarCheck',
    children: [
      { to: '/upload', label: 'Subir biométrico', icon: 'upload' },
      { to: '/attendance', label: 'Asistencia teóricas', icon: 'attendance' },
      { to: '/practice-attendance', label: 'Asistencia prácticas', icon: 'attendance' },
      { to: '/observations', label: 'Observaciones', icon: 'observations' },
      { to: '/attendance-audit', label: 'Auditoría de asistencia', icon: 'audit' },
      { to: '/planilla', label: 'Planilla', icon: 'planilla' },
      { to: '/reports', label: 'Reportes', icon: 'reports' },
    ],
  },
  {
    label: 'Docentes y académico',
    icon: 'academic',
    children: [
      { to: '/teachers', label: 'Docentes', icon: 'teachers' },
      { to: '/designations', label: 'Designaciones', icon: 'designations' },
      { to: '/contracts', label: 'Contratos', icon: 'contracts' },
      { to: '/academic-management', label: 'Gestión académica', icon: 'school' },
      { to: '/schedule-planner', label: 'Planificador de horarios', icon: 'schedule' },
      { to: '/requests', label: 'Solicitudes', icon: 'requests' },
      { to: '/chat', label: 'Mensajes', icon: 'messages' },
    ],
  },
  {
    label: 'Administración',
    icon: 'settings',
    children: [
      { to: '/users', label: 'Usuarios', icon: 'users' },
      { to: '/activity', label: 'Registro de actividad', icon: 'activity' },
      { to: '/backup', label: 'Respaldos', icon: 'backup' },
      { to: '/settings', label: 'Configuración', icon: 'settings' },
    ],
  },
]

export const docenteNav: NavItemDef[] = [
  { to: '/portal', label: 'Mi Facturación', icon: 'billing', exact: true },
  { to: '/portal/history', label: 'Histórico', icon: 'history' },
  { to: '/portal/schedule', label: 'Mi Horario', icon: 'schedule' },
  { to: RETENTION_LETTER_PATH, label: 'Carta Retención', icon: 'letter' },
  { to: '/portal/requests', label: 'Mis Solicitudes', icon: 'requests' },
  { to: '/portal/chat', label: 'Mensajes', icon: 'messages' },
  { to: '/portal/notifications', label: 'Notificaciones', icon: 'notifications' },
  { to: '/portal/profile', label: 'Mi Perfil', icon: 'profile' },
]

export function isNavGroup(entry: AdminNavEntry): entry is NavGroupDef {
  return 'children' in entry
}

export function isPathActive(pathname: string, item: NavItemDef): boolean {
  return item.exact ? pathname === item.to : pathname === item.to || pathname.startsWith(`${item.to}/`)
}

export function getActiveGroupLabel(pathname: string, entries: AdminNavEntry[]): string | undefined {
  return entries.find(
    (entry): entry is NavGroupDef =>
      isNavGroup(entry) && entry.children.some((child) => isPathActive(pathname, child)),
  )?.label
}

/** Missing data (profile loading, older backend) keeps the item visible. */
export function isRetentionVisible(hasRetention: boolean | undefined): boolean {
  return hasRetention !== false
}

export function getDocenteNavItems(hasRetention: boolean | undefined): NavItemDef[] {
  return docenteNav.filter((item) => item.to !== RETENTION_LETTER_PATH || isRetentionVisible(hasRetention))
}

const routeTitles: Record<string, string> = {
  ...Object.fromEntries(
    [...adminNav.flatMap((entry) => (isNavGroup(entry) ? entry.children : [entry])), ...docenteNav].map((item) => [
      item.to,
      item.label,
    ]),
  ),
  '/practice-planilla': 'Planilla',
  '/portal/retention-letter': 'Carta de Retención',
}

export function getTitleFromPath(pathname: string): string {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname
  if (routeTitles[path]) return routeTitles[path]
  if (path.startsWith('/teachers/')) return 'Detalle de Docente'
  return FALLBACK_TITLE
}
