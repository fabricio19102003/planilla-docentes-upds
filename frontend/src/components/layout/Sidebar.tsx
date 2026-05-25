import { useEffect, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  GraduationCap,
  Upload,
  ClipboardCheck,
  AlertTriangle,
  FileSpreadsheet,
  Users,
  Shield,
  ShieldCheck,
  MessageSquare,
  Receipt,
  History,
  User,
  LogOut,
  FileText,
  Bell,
  Calendar,
  Activity,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  FileSignature,
  Database,
  Settings,
} from 'lucide-react'
import { Logo } from './Logo'
import { useAuth } from '@/context/AuthContext'
import { useSidebar } from '@/context/SidebarContext'
import type { LucideIcon } from 'lucide-react'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  exact?: boolean
  badge?: number
}

interface NavGroup {
  label: string
  icon: LucideIcon
  children: NavItem[]
}

type AdminNavEntry = NavItem | NavGroup

function isNavGroup(entry: AdminNavEntry): entry is NavGroup {
  return 'children' in entry
}

const adminNavItems: AdminNavEntry[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  {
    label: 'Gestión Académica',
    icon: GraduationCap,
    children: [
      { to: '/upload', label: 'Subir Archivos', icon: Upload },
      { to: '/teachers', label: 'Docentes', icon: Users },
      { to: '/contracts', label: 'Contratos', icon: FileSignature },
    ],
  },
  {
    label: 'Asistencia',
    icon: ClipboardCheck,
    children: [
      { to: '/attendance', label: 'Asistencia', icon: ClipboardCheck },
      { to: '/practice-attendance', label: 'Asistencia Prácticas', icon: ClipboardCheck },
      { to: '/attendance-audit', label: 'Auditoría Asistencia', icon: ShieldCheck },
      { to: '/observations', label: 'Observaciones', icon: AlertTriangle },
    ],
  },
  {
    label: 'Planillas',
    icon: FileSpreadsheet,
    children: [
      { to: '/planilla', label: 'Planilla', icon: FileSpreadsheet },
      { to: '/practice-planilla', label: 'Planilla Prácticas', icon: FileSpreadsheet },
      { to: '/reports', label: 'Reportes', icon: FileText },
    ],
  },
  {
    label: 'Administración',
    icon: Settings,
    children: [
      { to: '/users', label: 'Gestión Usuarios', icon: Shield },
      { to: '/requests', label: 'Solicitudes', icon: MessageSquare },
      { to: '/activity', label: 'Registro de Actividad', icon: Activity },
      { to: '/backup', label: 'Respaldos', icon: Database },
      { to: '/settings', label: 'Configuración', icon: Settings },
    ],
  },
]

const docenteNavItems: NavItem[] = [
  { to: '/portal', label: 'Mi Facturación', icon: Receipt, exact: true },
  { to: '/portal/history', label: 'Histórico', icon: History },
  { to: '/portal/schedule', label: 'Mi Horario', icon: Calendar },
  { to: '/portal/retention-letter', label: 'Carta Retención', icon: FileText },
  { to: '/portal/requests', label: 'Mis Solicitudes', icon: MessageSquare },
  { to: '/portal/notifications', label: 'Notificaciones', icon: Bell },
  { to: '/portal/profile', label: 'Mi Perfil', icon: User },
]

function NavItemLink({ item, collapsed }: { item: NavItem; collapsed?: boolean }) {
  return (
    <NavLink
      to={item.to}
      end={item.exact}
      className={({ isActive }) =>
        [
          'relative mx-2 flex items-center rounded-lg transition-all duration-200 ease-in-out',
          collapsed ? 'justify-center px-2 py-3' : 'gap-3 px-4 py-3 text-sm',
          isActive
            ? `bg-white/15 text-white/90 ${collapsed ? '' : 'border-l-[3px] border-sky-400'}`
            : `text-white/50 ${collapsed ? '' : 'border-l-[3px] border-transparent'} hover:bg-white/[0.08] hover:text-white/90`,
        ].join(' ')
      }
      title={collapsed ? item.label : undefined}
    >
      <item.icon size={collapsed ? 20 : 18} />
      {!collapsed && <span>{item.label}</span>}
      {!collapsed && item.badge != null && item.badge > 0 && (
        <span className="ml-auto bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
          {item.badge > 9 ? '9+' : item.badge}
        </span>
      )}
      {collapsed && item.badge != null && item.badge > 0 && (
        <span className="absolute top-1 right-1 w-3.5 h-3.5 bg-red-500 text-white text-[9px] font-bold rounded-full flex items-center justify-center">
          {item.badge > 9 ? '9+' : item.badge}
        </span>
      )}
    </NavLink>
  )
}

function isItemActive(pathname: string, item: NavItem) {
  return item.exact ? pathname === item.to : pathname === item.to || pathname.startsWith(`${item.to}/`)
}

function NavGroupComponent({
  group,
  collapsed,
  expanded,
  active,
  pathname,
  showSeparator,
  onToggle,
}: {
  group: NavGroup
  collapsed: boolean
  expanded: boolean
  active: boolean
  pathname: string
  showSeparator: boolean
  onToggle: () => void
}) {
  if (collapsed) {
    return (
      <div className={`group relative mx-2 ${showSeparator ? 'mt-2 border-t border-white/[0.08] pt-2' : ''}`}>
        <button
          type="button"
          className={`flex w-full items-center justify-center rounded-lg px-2 py-3 transition-all duration-200 ease-in-out ${
            active ? 'bg-white/15 text-white/90' : 'text-white/50 hover:bg-white/[0.08] hover:text-white/90'
          }`}
          title={group.label}
        >
          <group.icon size={20} className="text-sky-400/70" />
        </button>
        <div className="absolute left-full top-0 z-[60] ml-3 hidden min-w-56 rounded-xl border border-white/10 bg-slate-900/95 p-2 shadow-2xl backdrop-blur-xl group-hover:block">
          <p className="px-3 py-2 text-[11px] font-bold uppercase tracking-widest text-white/60">{group.label}</p>
          <div className="space-y-1">
            {group.children.map((child) => {
              const childActive = isItemActive(pathname, child)

              return (
                <NavLink
                  key={child.to}
                  to={child.to}
                  end={child.exact}
                  className={`relative flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-all duration-200 ease-in-out ${
                    childActive ? 'bg-sky-500/20 text-white' : 'text-white/50 hover:bg-white/[0.08] hover:text-white/90'
                  }`}
                >
                  <child.icon size={16} />
                  <span>{child.label}</span>
                  {child.badge != null && child.badge > 0 && (
                    <span className="ml-auto bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                      {child.badge > 9 ? '9+' : child.badge}
                    </span>
                  )}
                </NavLink>
              )
            })}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={showSeparator ? 'mt-2 border-t border-white/[0.08] pt-2' : ''}>
      <button
        type="button"
        onClick={onToggle}
        className={`mx-2 flex w-[calc(100%-1rem)] items-center gap-3 rounded-lg border-l-[3px] px-4 py-3 text-sm transition-all duration-200 ease-in-out ${
          active
            ? 'border-sky-400 bg-white/15 text-white/90'
            : 'border-transparent text-white/60 hover:bg-white/[0.08] hover:text-white/90'
        }`}
      >
        <group.icon size={18} className="text-sky-400/70" />
        <span className="text-[11px] font-bold uppercase tracking-widest">{group.label}</span>
        {expanded ? <ChevronDown size={16} className="ml-auto" /> : <ChevronRight size={16} className="ml-auto" />}
      </button>
      <div
        className={`grid transition-[grid-template-rows] duration-200 ease-in-out ${expanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'}`}
      >
        <div className="overflow-hidden">
          <div className="ml-6 border-l border-white/10 py-1">
            {group.children.map((child) => (
              <NavLink
                key={child.to}
                to={child.to}
                end={child.exact}
                className={({ isActive }) =>
                  [
                    'relative my-0.5 ml-2 mr-2 flex items-center gap-2 rounded-lg py-2.5 pl-11 pr-4 text-sm transition-all duration-200 ease-in-out',
                    isActive
                      ? 'border-l-2 border-sky-400 bg-sky-500/20 text-white'
                      : 'border-l-2 border-transparent text-white/50 hover:bg-white/[0.08] hover:text-white/90',
                  ].join(' ')
                }
              >
                <child.icon size={16} />
                <span>{child.label}</span>
                {child.badge != null && child.badge > 0 && (
                  <span className="ml-auto bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                    {child.badge > 9 ? '9+' : child.badge}
                  </span>
                )}
              </NavLink>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export function Sidebar() {
  const { user, isAdmin, logout } = useAuth()
  const { collapsed, toggle } = useSidebar()
  const { pathname } = useLocation()
  const navItems = isAdmin ? adminNavItems : docenteNavItems
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(() => new Set())

  useEffect(() => {
    if (!isAdmin) return

    const activeGroup = adminNavItems.find(
      (item) => isNavGroup(item) && item.children.some((child) => isItemActive(pathname, child))
    )

    if (!activeGroup || !isNavGroup(activeGroup)) return

    setExpandedGroups((current) => {
      if (current.has(activeGroup.label)) return current

      const next = new Set(current)
      next.add(activeGroup.label)
      return next
    })
  }, [isAdmin, pathname])

  const toggleGroup = (label: string) => {
    setExpandedGroups((current) => {
      const next = new Set(current)

      if (next.has(label)) {
        next.delete(label)
      } else {
        next.add(label)
      }

      return next
    })
  }

  return (
    <aside
      className={`fixed left-0 top-0 z-50 flex h-screen flex-col overflow-visible ${collapsed ? 'w-[68px]' : 'w-64'}`}
      style={{
        background: 'linear-gradient(180deg, #1C398E 0%, #142866 50%, #0F1D4A 100%)',
        boxShadow: '0 8px 30px rgb(0,0,0,0.08)',
        transition: 'width 200ms ease-in-out',
      }}
    >
      {/* Logo Section */}
      <div className="flex items-center justify-center border-b border-white/10 px-3 py-5" style={{ boxShadow: '0 1px 0 rgba(255,255,255,0.05)' }}>
        {collapsed ? (
          <span className="text-2xl font-black text-sky-400 drop-shadow-[0_0_8px_rgba(0,166,244,0.4)]">S</span>
        ) : (
          <div className="flex flex-col">
            <Logo size="md" />
            <p className="text-white/60 text-xs mt-1 font-medium tracking-wide">SIPAD</p>
          </div>
        )}
      </div>

      {/* User info */}
      <div className="px-3 py-3 border-b border-white/10">
        <div className={`flex items-center ${collapsed ? 'justify-center' : 'gap-3'}`}>
          <div
            className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-sky-400 to-blue-600 text-sm font-bold text-white shadow-[0_8px_30px_rgb(0,0,0,0.08)]"
          >
            {user?.full_name?.charAt(0).toUpperCase() ?? 'U'}
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <p className="truncate text-sm font-medium leading-tight text-white/90">
                {user?.full_name ?? ''}
              </p>
              <span
                className={`rounded-lg px-1.5 py-0.5 text-xs font-semibold ${
                  isAdmin ? 'bg-sky-500/20 text-sky-300' : 'bg-emerald-500/20 text-emerald-300'
                }`}
              >
                {isAdmin ? 'Admin' : 'Docente'}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav
        className={`flex-1 py-4 ${
          collapsed
            ? 'overflow-visible'
            : 'overflow-y-auto [scrollbar-color:rgba(255,255,255,0.1)_transparent] [scrollbar-width:thin] [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-white/10 [&::-webkit-scrollbar-track]:bg-transparent'
        }`}
      >
        {navItems.map((item, index) => (
          isNavGroup(item) ? (
            <NavGroupComponent
              key={item.label}
              group={item}
              collapsed={collapsed}
              expanded={expandedGroups.has(item.label)}
              active={item.children.some((child) => isItemActive(pathname, child))}
              pathname={pathname}
              showSeparator={navItems.slice(0, index).some(isNavGroup)}
              onToggle={() => toggleGroup(item.label)}
            />
          ) : (
            <NavItemLink key={item.to} item={item} collapsed={collapsed} />
          )
        ))}
      </nav>

      {/* Toggle button */}
      <div className="border-t border-white/10">
        <button
          onClick={toggle}
          className={`mx-2 my-1 flex w-[calc(100%-1rem)] items-center rounded-lg px-4 py-3 text-sm text-white/50 transition-colors duration-200 ease-in-out hover:bg-white/[0.08] hover:text-white/90 ${collapsed ? 'justify-center' : 'gap-3'}`}
          title={collapsed ? 'Expandir menú' : 'Colapsar menú'}
        >
          {collapsed ? <ChevronRight size={18} /> : <><ChevronLeft size={18} /><span>Colapsar</span></>}
        </button>
      </div>

      {/* Logout */}
      <div className="border-t border-white/10">
        <button
          onClick={logout}
          className={`mx-2 my-1 flex w-[calc(100%-1rem)] items-center rounded-lg px-4 py-4 text-sm text-white/60 transition-colors duration-200 ease-in-out hover:bg-red-500/15 hover:text-red-300 ${collapsed ? 'justify-center' : 'gap-3'}`}
          title={collapsed ? 'Cerrar Sesión' : undefined}
        >
          <LogOut size={18} />
          {!collapsed && <span>Cerrar Sesión</span>}
        </button>
      </div>
    </aside>
  )
}
