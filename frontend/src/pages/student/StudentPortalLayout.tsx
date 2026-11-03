import { GraduationCap, LogOut } from 'lucide-react'
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { useStudentLogout, useStudentMe } from '@/api/hooks/useStudentPortal'
import { STUDENT_TOKEN_KEY } from '@/api/studentClient'
import { Logo } from '@/components/layout/Logo'
import { ThemeToggle } from '@/components/layout/ThemeToggle'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const LINKS = [
  { to: '/estudiante', label: 'Inicio', end: true },
  { to: '/estudiante/historial', label: 'Historial académico', end: false },
  { to: '/estudiante/rematricula', label: 'Rematrícula', end: false },
  { to: '/estudiante/horario', label: 'Mi horario', end: false },
  { to: '/estudiante/intensivos', label: 'Cursos de verano e invierno', end: false },
  { to: '/estudiante/cambiar-clave', label: 'Cambiar contraseña', end: false },
]

export function StudentPortalLayout() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const me = useStudentMe()
  const logout = useStudentLogout()

  if (!localStorage.getItem(STUDENT_TOKEN_KEY)) return <Navigate to="/estudiante/login" replace />
  if (me.data?.must_change_password) return <Navigate to="/estudiante/cambiar-clave" replace />

  return (
    <div className="min-h-screen bg-canvas">
      <header className="bg-brand shadow-lg shadow-brand-surface/20">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-4">
          <div className="flex items-center gap-4">
            <Logo size="sm" />
            <span className="flex items-center gap-2 border-l border-brand-foreground/20 pl-4 text-sm font-semibold text-brand-foreground">
              <GraduationCap aria-hidden="true" />Portal del estudiante
            </span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            {me.data && <span className="text-brand-foreground">{me.data.full_name}</span>}
            <ThemeToggle variant="brand" />
            <Button size="sm" variant="outline"
              className="border-brand-foreground/30 bg-brand-foreground/10 text-brand-foreground hover:bg-brand-foreground/20 hover:text-brand-foreground"
              onClick={() => { logout(); navigate('/estudiante/login', { replace: true }) }}>
              <LogOut aria-hidden="true" />Salir
            </Button>
          </div>
        </div>
        <nav aria-label="Portal del estudiante" className="mx-auto flex max-w-5xl gap-1 overflow-x-auto px-4 pb-3">
          {LINKS.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end}
              className={({ isActive }) => cn('whitespace-nowrap rounded-full px-3.5 py-1.5 text-sm transition-colors',
                isActive
                  ? 'bg-brand-foreground font-medium text-brand-surface shadow-sm'
                  : 'text-brand-foreground hover:bg-brand-foreground/10 hover:text-brand-foreground')}>
              {link.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main key={pathname} className="page-enter mx-auto max-w-5xl space-y-5 px-4 py-6"><Outlet /></main>
    </div>
  )
}
