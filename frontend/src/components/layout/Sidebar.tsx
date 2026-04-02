import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Upload,
  ClipboardCheck,
  AlertTriangle,
  FileSpreadsheet,
  Users,
} from 'lucide-react'
import { Logo } from './Logo'

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { to: '/upload', label: 'Subir Archivos', icon: Upload, exact: false },
  { to: '/attendance', label: 'Asistencia', icon: ClipboardCheck, exact: false },
  { to: '/observations', label: 'Observaciones', icon: AlertTriangle, exact: false },
  { to: '/planilla', label: 'Planilla', icon: FileSpreadsheet, exact: false },
  { to: '/teachers', label: 'Docentes', icon: Users, exact: false },
]

export function Sidebar() {
  return (
    <aside
      className="fixed left-0 top-0 h-screen w-64 flex flex-col z-50"
      style={{ backgroundColor: '#003366' }}
    >
      {/* Logo Section */}
      <div className="px-6 py-5 border-b border-white/10">
        <Logo size="md" />
        <p className="text-white/60 text-xs mt-1 font-medium tracking-wide">
          Planilla Docentes
        </p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 overflow-y-auto">
        {navItems.map(({ to, label, icon: Icon, exact }) => (
          <NavLink
            key={to}
            to={to}
            end={exact}
            className={({ isActive }) =>
              [
                'flex items-center gap-3 px-4 py-3 text-sm transition-colors',
                isActive
                  ? 'text-white border-l-4 border-[#4DA8DA]'
                  : 'text-white/70 border-l-4 border-transparent hover:text-white',
              ].join(' ')
            }
            style={({ isActive }) =>
              isActive ? { backgroundColor: '#0066CC' } : undefined
            }
            onMouseEnter={(e) => {
              const target = e.currentTarget
              if (!target.classList.contains('text-white') || target.style.backgroundColor !== 'rgb(0, 102, 204)') {
                target.style.backgroundColor = '#004080'
              }
            }}
            onMouseLeave={(e) => {
              const target = e.currentTarget
              if (target.style.backgroundColor === 'rgb(0, 64, 128)') {
                target.style.backgroundColor = ''
              }
            }}
          >
            <Icon size={18} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-4 py-4 border-t border-white/10">
        <p className="text-white/40 text-xs text-center">
          Sistema de Planillas v1.0
        </p>
      </div>
    </aside>
  )
}
