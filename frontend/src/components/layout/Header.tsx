import { useState, useRef, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { LogOut, ChevronDown, Bell, Search, Users, BookOpen, Layers, Menu } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { useUnreadCount } from '@/api/hooks/useNotifications'
import { api } from '@/api/client'
import { SheetTrigger } from '@/components/ui/sheet'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

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
  '/portal/notifications': 'Notificaciones',
}

function getTitleFromPath(pathname: string): string {
  if (routeTitles[pathname]) return routeTitles[pathname]
  if (pathname.startsWith('/teachers/')) return 'Detalle de Docente'
  const match = Object.keys(routeTitles)
    .filter((key) => key !== '/')
    .find((key) => pathname.startsWith(key))
  return match ? routeTitles[match] : 'UPDS Planilla'
}

interface SearchResults {
  teachers: { ci: string; full_name: string; email: string | null }[]
  subjects: { subject: string; semester: string }[]
  groups: { group_code: string }[]
}

export function Header() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { user, isAdmin, isDocente, logout } = useAuth()
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [failedAvatarUrl, setFailedAvatarUrl] = useState<string | null>(null)
  const title = getTitleFromPath(pathname)
  const { data: unreadCount = 0 } = useUnreadCount(isDocente)
  const avatarUrl = user?.avatar_url ?? null
  const showAvatarImage = Boolean(avatarUrl) && failedAvatarUrl !== avatarUrl

  // Global search state
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResults | null>(null)
  const [showSearch, setShowSearch] = useState(false)
  const searchRef = useRef<HTMLDivElement>(null)

  // Debounced search
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- Clear stale search results immediately when the query is too short.
    if (searchQuery.length < 2) { setSearchResults(null); return }
    const timer = setTimeout(async () => {
      try {
        const res = await api.get<SearchResults>(`/search?q=${encodeURIComponent(searchQuery)}`)
        setSearchResults(res.data)
        setShowSearch(true)
      } catch {
        setSearchResults(null)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  // Click outside to close search
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowSearch(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
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
    <header className="sticky top-0 z-40 flex min-h-16 flex-wrap items-center gap-2 bg-white px-3 py-2 shadow-md sm:px-4 md:flex-nowrap md:px-6">
      <div className="flex min-w-0 items-center gap-2">
        <SheetTrigger asChild>
          <button
            type="button"
            className="inline-flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg text-gray-600 transition-colors hover:bg-gray-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0066CC] md:hidden"
            aria-label="Abrir menú de navegación"
          >
            <Menu size={22} />
          </button>
        </SheetTrigger>
        <h1 className="truncate text-base font-semibold sm:text-lg md:text-xl" style={{ color: '#003366' }}>
          {title}
        </h1>
      </div>

      {/* Global search — admin only */}
      {isAdmin && (
        <div ref={searchRef} className="order-last relative w-full flex-1 md:order-none md:mx-4 md:max-w-md">
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              onFocus={() => searchResults && setShowSearch(true)}
              placeholder="Buscar docente, materia o grupo..."
              className="w-full pl-10 pr-4 py-2 bg-gray-100 border-0 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] focus:bg-white transition-colors"
            />
          </div>

          {showSearch && searchResults && (
            <div className="absolute top-full mt-1 w-full bg-white border border-gray-200 rounded-xl shadow-xl z-50 overflow-hidden">
              {/* Teachers */}
              {searchResults.teachers?.length > 0 && (
                <div>
                  <p className="px-3 py-1.5 text-xs font-semibold text-gray-400 uppercase bg-gray-50">Docentes</p>
                  {searchResults.teachers.map((t) => (
                    <button
                      key={t.ci}
                      onClick={() => { navigate(`/teachers/${t.ci}`); setShowSearch(false); setSearchQuery('') }}
                      className="w-full text-left px-3 py-2 hover:bg-blue-50 flex items-center gap-2 text-sm"
                    >
                      <Users size={14} className="text-gray-400 flex-shrink-0" />
                      <span className="font-medium text-gray-800 truncate">{t.full_name}</span>
                      <span className="text-xs text-gray-400 ml-auto flex-shrink-0">CI: {t.ci}</span>
                    </button>
                  ))}
                </div>
              )}

              {/* Subjects */}
              {searchResults.subjects?.length > 0 && (
                <div>
                  <p className="px-3 py-1.5 text-xs font-semibold text-gray-400 uppercase bg-gray-50">Materias</p>
                  {searchResults.subjects.map((s) => (
                    <div key={s.subject} className="px-3 py-2 text-sm flex items-center gap-2">
                      <BookOpen size={14} className="text-gray-400 flex-shrink-0" />
                      <span className="text-gray-700 truncate">{s.subject}</span>
                      <span className="text-xs text-gray-400 ml-auto flex-shrink-0">{s.semester}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Groups */}
              {searchResults.groups?.length > 0 && (
                <div>
                  <p className="px-3 py-1.5 text-xs font-semibold text-gray-400 uppercase bg-gray-50">Grupos</p>
                  {searchResults.groups.map((g) => (
                    <div key={g.group_code} className="px-3 py-2 text-sm flex items-center gap-2">
                      <Layers size={14} className="text-gray-400 flex-shrink-0" />
                      <span className="text-gray-700">{g.group_code}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Empty state */}
              {!searchResults.teachers?.length && !searchResults.subjects?.length && !searchResults.groups?.length && (
                <p className="px-3 py-4 text-sm text-gray-400 text-center">Sin resultados para &ldquo;{searchQuery}&rdquo;</p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Notification bell — docentes only */}
      <div className="flex items-center gap-2">
        {isDocente && (
          <button
            type="button"
            onClick={() => navigate('/portal/notifications')}
            className="relative rounded-lg p-2 transition-colors hover:bg-gray-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0066CC]"
            aria-label={unreadCount > 0 ? `Notificaciones, ${unreadCount} sin leer` : 'Notificaciones'}
          >
            <Bell size={20} className="text-gray-600" />
            {unreadCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 w-5 h-5 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>
        )}

        {/* User section */}
        <DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="flex items-center gap-2 rounded-lg px-2 py-1.5 transition-colors hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0066CC] sm:gap-2.5 sm:px-3"
              aria-expanded={dropdownOpen}
              aria-haspopup="menu"
              aria-label="Abrir menú de usuario"
            >
          <div className="relative w-8 h-8 rounded-full bg-[#003366] flex items-center justify-center text-white text-xs font-bold flex-shrink-0 overflow-hidden ring-2 ring-[#003366]/10">
            {showAvatarImage ? (
              <img
                src={avatarUrl ?? undefined}
                alt={`Foto de perfil de ${user?.full_name ?? 'usuario'}`}
                className="h-full w-full object-cover"
                onError={() => setFailedAvatarUrl(avatarUrl)}
              />
            ) : (
              <span>{initials}</span>
            )}
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
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-52">
            <DropdownMenuLabel className="px-3 py-2.5 font-normal">
              <p className="text-sm font-medium text-gray-800 truncate">{user?.full_name}</p>
              <p className="text-xs text-gray-400 truncate mt-0.5">CI: {user?.ci}</p>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={logout} className="gap-2.5 px-3 py-2.5 text-red-600 focus:bg-red-50 focus:text-red-700">
              <LogOut size={15} />
              Cerrar Sesión
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Gradient accent line */}
      <div
        className="absolute bottom-0 left-0 right-0 h-0.5"
        style={{ background: 'linear-gradient(90deg, #003366 0%, #0066CC 50%, #4DA8DA 80%, transparent 100%)' }}
      />
    </header>
  )
}
