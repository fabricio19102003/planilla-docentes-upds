import { GraduationCap, LogOut } from 'lucide-react'
import { NavLink, Navigate, Outlet, useNavigate } from 'react-router-dom'

import { useStudentLogout, useStudentMe } from '@/api/hooks/useStudentPortal'
import { STUDENT_TOKEN_KEY } from '@/api/studentClient'
import { Logo } from '@/components/layout/Logo'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const LINKS = [
  { to: '/estudiante', label: 'Inicio', end: true },
  { to: '/estudiante/historial', label: 'Historial académico', end: false },
  { to: '/estudiante/rematricula', label: 'Rematrícula', end: false },
  { to: '/estudiante/cambiar-clave', label: 'Cambiar contraseña', end: false },
]

export function StudentPortalLayout() {
  const navigate = useNavigate()
  const me = useStudentMe()
  const logout = useStudentLogout()

  if (!localStorage.getItem(STUDENT_TOKEN_KEY)) return <Navigate to="/estudiante/login" replace />
  if (me.data?.must_change_password) return <Navigate to="/estudiante/cambiar-clave" replace />

  return (
    <div className="min-h-screen bg-muted/30">
      <header className="border-b bg-background">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-3">
            <Logo />
            <span className="flex items-center gap-2 text-sm font-semibold"><GraduationCap aria-hidden="true" />Portal del estudiante</span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            {me.data && <span className="text-muted-foreground">{me.data.full_name}</span>}
            <Button size="sm" variant="outline" onClick={() => { logout(); navigate('/estudiante/login', { replace: true }) }}>
              <LogOut aria-hidden="true" />Salir
            </Button>
          </div>
        </div>
        <nav aria-label="Portal del estudiante" className="mx-auto flex max-w-5xl gap-1 overflow-x-auto px-4">
          {LINKS.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end}
              className={({ isActive }) => cn('whitespace-nowrap border-b-2 px-3 py-2 text-sm',
                isActive ? 'border-primary font-medium text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground')}>
              {link.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-5xl space-y-5 px-4 py-6"><Outlet /></main>
    </div>
  )
}
