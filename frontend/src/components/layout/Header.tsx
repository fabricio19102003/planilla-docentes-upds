import { useState, useRef, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { LogOut, ChevronDown } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'

const routeTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/upload': 'Subir Archivos',
  '/attendance': 'Asistencia',
  '/observations': 'Observaciones',
  '/planilla': 'Planilla',
  '/teachers': 'Docentes',
  '/users': 'Gestión de Usuarios',
  '/requests': 'Solicitudes de Docentes',
  '/portal': 'Mi Facturación',
  '/portal/history': 'Histórico de Facturación',
  '/portal/requests': 'Mis Solicitudes',
  '/portal/profile': 'Mi Perfil',
}

function getTitleFromPath(pathname: string): string {
  if (routeTitles[pathname]) return routeTitles[pathname]
  if (pathname.startsWith('/teachers/')) return 'Detalle de Docente'
  const match = Object.keys(routeTitles)
    .filter((key) => key !== '/')
    .find((key) => pathname.startsWith(key))
  return match ? routeTitles[match] : 'UPDS Planilla'
}

export function Header() {
  const { pathname } = useLocation()
  const { user, isAdmin, logout } = useAuth()
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const title = getTitleFromPath(pathname)

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const initials = user?.full_name
    ? user.full_name
        .split(' ')
        .slice(0, 2)
        .map((n) => n[0])
        .join('')
        .toUpperCase()
    : 'U'

  return (
    <header className="bg-white shadow-sm border-b h-16 flex items-center justify-between px-6 sticky top-0 z-40">
      <h1 className="text-xl font-semibold" style={{ color: '#003366' }}>
        {title}
      </h1>

      {/* User section */}
      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => setDropdownOpen((v) => !v)}
          className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg hover:bg-gray-50 transition-colors"
        >
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
            style={{ backgroundColor: '#003366' }}
          >
            {initials}
          </div>
          <div className="text-left hidden sm:block">
            <p className="text-sm font-medium text-gray-700 leading-tight max-w-[150px] truncate">
              {user?.full_name ?? ''}
            </p>
            <span
              className="text-xs font-semibold px-1.5 py-0.5 rounded"
              style={
                isAdmin
                  ? { backgroundColor: '#dbeafe', color: '#1d4ed8' }
                  : { backgroundColor: '#dcfce7', color: '#15803d' }
              }
            >
              {isAdmin ? 'Admin' : 'Docente'}
            </span>
          </div>
          <ChevronDown
            size={14}
            className={`text-gray-400 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`}
          />
        </button>

        {/* Dropdown */}
        {dropdownOpen && (
          <div className="absolute right-0 top-full mt-1.5 w-52 bg-white rounded-lg shadow-lg border border-gray-100 py-1 z-50">
            <div className="px-4 py-2.5 border-b border-gray-100">
              <p className="text-sm font-medium text-gray-800 truncate">{user?.full_name}</p>
              <p className="text-xs text-gray-400 truncate mt-0.5">CI: {user?.ci}</p>
            </div>
            <button
              onClick={() => {
                setDropdownOpen(false)
                logout()
              }}
              className="flex items-center gap-2.5 w-full px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors"
            >
              <LogOut size={15} />
              Cerrar Sesión
            </button>
          </div>
        )}
      </div>
    </header>
  )
}
