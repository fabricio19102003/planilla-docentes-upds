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
          'flex items-center transition-all duration-200 relative',
          collapsed ? 'justify-center px-2 py-3' : 'gap-3 px-4 py-3 text-sm',
          isActive
            ? `text-white ${collapsed ? '' : 'border-l-4 border-[#4DA8DA]'}`
            : `text-white/70 ${collapsed ? '' : 'border-l-4 border-transparent'} hover:text-white`,
        ].join(' ')
      }
      style={({ isActive }) =>
        isActive ? { backgroundColor: 'rgba(0, 102, 204, 0.85)' } : undefined
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
  onToggle,
}: {
  group: NavGroup
  collapsed: boolean
  expanded: boolean
  active: boolean
  pathname: string
  onToggle: () => void
}) {
  if (collapsed) {
    return (
      <div className="relative group">
        <button
          type="button"
          className={`flex items-center justify-center w-full px-2 py-3 transition-all duration-200 ${active ? 'text-white' : 'text-white/70 hover:text-white'}`}
          style={active ? { backgroundColor: 'rgba(0, 102, 204, 0.85)' } : undefined}
          title={group.label}
        >
          <group.icon size={20} />
        </button>
        <div className="absolute left-full top-0 z-[60] ml-2 hidden min-w-56 rounded-lg border border-white/10 bg-[#071A2E] p-2 shadow-2xl group-hover:block">
          <p className="px-3 py-2 text-sm font-semibold text-white">{group.label}</p>
          <div className="space-y-1">
            {group.children.map((child) => {
              const childActive = isItemActive(pathname, child)

              return (
                <NavLink
                  key={child.to}
                  to={child.to}
                  end={child.exact}
                  className={`relative flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors duration-200 ${
                    childActive ? 'text-white' : 'text-white/70 hover:bg-white/5 hover:text-white'
                  }`}
                  style={childActive ? { backgroundColor: 'rgba(0, 102, 204, 0.85)' } : undefined}
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
    <div>
      <button
        type="button"
        onClick={onToggle}
        className={`flex w-full items-center gap-3 border-l-4 px-4 py-3 text-sm transition-all duration-200 ${
          active
            ? 'border-[#4DA8DA] bg-white/10 text-white/90'
            : 'border-transparent text-white/80 hover:bg-white/5 hover:text-white'
        }`}
      >
        <group.icon size={18} />
        <span>{group.label}</span>
        {expanded ? <ChevronDown size={16} className="ml-auto" /> : <ChevronRight size={16} className="ml-auto" />}
      </button>
      <div
        className={`grid transition-[grid-template-rows] duration-200 ease-in-out ${expanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'}`}
      >
        <div className="overflow-hidden">
          <div className="ml-6 border-l-2 border-white/10 py-1">
            {group.children.map((child) => (
              <NavLink
                key={child.to}
                to={child.to}
                end={child.exact}
                className={({ isActive }) =>
                  [
                    'relative flex items-center gap-2 py-2.5 pl-4 pr-4 text-sm transition-all duration-200',
                    isActive
                      ? 'border-l-4 border-[#4DA8DA] text-white'
                      : 'border-l-4 border-transparent text-white/60 hover:text-white',
                  ].join(' ')
                }
                style={({ isActive }) =>
                  isActive ? { backgroundColor: 'rgba(0, 102, 204, 0.85)' } : undefined
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
      className={`fixed left-0 top-0 h-screen flex flex-col z-50 gradient-navy overflow-visible ${collapsed ? 'w-[68px]' : 'w-64'}`}
      style={{ boxShadow: '4px 0 24px rgba(0,0,0,0.15)', transition: 'width 200ms ease-in-out' }}
    >
      {/* Logo Section */}
      <div className="px-3 py-5 border-b border-white/10 flex items-center justify-center" style={{ boxShadow: '0 1px 0 rgba(255,255,255,0.05)' }}>
        {collapsed ? (
          <span className="font-black text-2xl" style={{ color: '#4DA8DA' }}>S</span>
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
            className="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-bold flex-shrink-0"
            style={{ backgroundColor: '#0066CC' }}
          >
            {user?.full_name?.charAt(0).toUpperCase() ?? 'U'}
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <p className="text-white text-sm font-medium truncate leading-tight">
                {user?.full_name ?? ''}
              </p>
              <span
                className="text-xs font-semibold px-1.5 py-0.5 rounded"
                style={
                  isAdmin
                    ? { backgroundColor: '#1d4ed8', color: '#bfdbfe' }
                    : { backgroundColor: '#15803d', color: '#bbf7d0' }
                }
              >
                {isAdmin ? 'Admin' : 'Docente'}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className={`flex-1 py-4 ${collapsed ? 'overflow-visible' : 'overflow-y-auto'}`}>
        {navItems.map((item) => (
          isNavGroup(item) ? (
            <NavGroupComponent
              key={item.label}
              group={item}
              collapsed={collapsed}
              expanded={expandedGroups.has(item.label)}
              active={item.children.some((child) => isItemActive(pathname, child))}
              pathname={pathname}
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
          className={`flex items-center w-full px-4 py-3 text-sm text-white/50 hover:text-white hover:bg-white/5 transition-colors ${collapsed ? 'justify-center' : 'gap-3'}`}
          title={collapsed ? 'Expandir menú' : 'Colapsar menú'}
        >
          {collapsed ? <ChevronRight size={18} /> : <><ChevronLeft size={18} /><span>Colapsar</span></>}
        </button>
      </div>

      {/* Logout */}
      <div className="border-t border-white/10">
        <button
          onClick={logout}
          className={`flex items-center w-full px-4 py-4 text-sm text-white/60 hover:text-red-300 transition-colors hover:bg-red-500/10 ${collapsed ? 'justify-center' : 'gap-3'}`}
          title={collapsed ? 'Cerrar Sesión' : undefined}
        >
          <LogOut size={18} />
          {!collapsed && <span>Cerrar Sesión</span>}
        </button>
      </div>
    </aside>
  )
}
