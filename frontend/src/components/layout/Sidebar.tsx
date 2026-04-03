import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Upload,
  ClipboardCheck,
  AlertTriangle,
  FileSpreadsheet,
  Users,
  Shield,
  MessageSquare,
  Receipt,
  History,
  User,
  LogOut,
} from 'lucide-react'
import { Logo } from './Logo'
import { useAuth } from '@/context/AuthContext'
import type { LucideIcon } from 'lucide-react'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  exact?: boolean
  badge?: number
}

const adminNavItems: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { to: '/upload', label: 'Subir Archivos', icon: Upload },
  { to: '/attendance', label: 'Asistencia', icon: ClipboardCheck },
  { to: '/observations', label: 'Observaciones', icon: AlertTriangle },
  { to: '/planilla', label: 'Planilla', icon: FileSpreadsheet },
  { to: '/teachers', label: 'Docentes', icon: Users },
  { to: '/users', label: 'Gestión Usuarios', icon: Shield },
  { to: '/requests', label: 'Solicitudes', icon: MessageSquare },
]

const docenteNavItems: NavItem[] = [
  { to: '/portal', label: 'Mi Facturación', icon: Receipt, exact: true },
  { to: '/portal/history', label: 'Histórico', icon: History },
  { to: '/portal/requests', label: 'Mis Solicitudes', icon: MessageSquare },
  { to: '/portal/profile', label: 'Mi Perfil', icon: User },
]

function NavItemLink({ item }: { item: NavItem }) {
  return (
    <NavLink
      to={item.to}
      end={item.exact}
      className={({ isActive }) =>
        [
          'flex items-center gap-3 px-4 py-3 text-sm transition-all duration-200 relative',
          isActive
            ? 'text-white border-l-4 border-[#4DA8DA]'
            : 'text-white/70 border-l-4 border-transparent hover:text-white',
        ].join(' ')
      }
      style={({ isActive }) =>
        isActive ? { backgroundColor: 'rgba(0, 102, 204, 0.85)' } : undefined
      }
      onMouseEnter={(e) => {
        const target = e.currentTarget
        if (target.style.backgroundColor !== 'rgba(0, 102, 204, 0.85)') {
          target.style.backgroundColor = 'rgba(0, 64, 128, 0.5)'
        }
      }}
      onMouseLeave={(e) => {
        const target = e.currentTarget
        if (target.style.backgroundColor === 'rgba(0, 64, 128, 0.5)') {
          target.style.backgroundColor = ''
        }
      }}
    >
      <item.icon size={18} />
      <span className="flex-1">{item.label}</span>
      {item.badge !== undefined && item.badge > 0 && (
        <span className="bg-yellow-400 text-yellow-900 text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
          {item.badge > 9 ? '9+' : item.badge}
        </span>
      )}
    </NavLink>
  )
}

export function Sidebar() {
  const { user, isAdmin, logout } = useAuth()
  const navItems = isAdmin ? adminNavItems : docenteNavItems

  return (
    <aside
      className="fixed left-0 top-0 h-screen w-64 flex flex-col z-50 gradient-navy"
      style={{ boxShadow: '4px 0 24px rgba(0,0,0,0.15)' }}
    >
      {/* Logo Section */}
      <div className="px-6 py-5 border-b border-white/10" style={{ boxShadow: '0 1px 0 rgba(255,255,255,0.05)' }}>
        <Logo size="md" />
        <p className="text-white/60 text-xs mt-1 font-medium tracking-wide">
          Planilla Docentes
        </p>
      </div>

      {/* User info */}
      <div className="px-4 py-3 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-bold flex-shrink-0"
            style={{ backgroundColor: '#0066CC' }}
          >
            {user?.full_name?.charAt(0).toUpperCase() ?? 'U'}
          </div>
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
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 overflow-y-auto">
        {navItems.map((item) => (
          <NavItemLink key={item.to} item={item} />
        ))}
      </nav>

      {/* Logout */}
      <div className="border-t border-white/10">
        <button
          onClick={logout}
          className="flex items-center gap-3 w-full px-4 py-4 text-sm text-white/60 hover:text-red-300 transition-colors hover:bg-red-500/10"
        >
          <LogOut size={18} />
          <span>Cerrar Sesión</span>
        </button>
      </div>
    </aside>
  )
}
