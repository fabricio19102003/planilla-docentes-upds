import { CalendarDays, ChevronDown, ClipboardCheck, ClipboardPen, GraduationCap, House, IdCard, KeyRound, LogOut, Sun, type LucideIcon } from 'lucide-react'
import { motion, useReducedMotion } from 'motion/react'
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { useStudentLogout, useStudentMe } from '@/api/hooks/useStudentPortal'
import { STUDENT_TOKEN_KEY } from '@/api/studentClient'
import { Logo } from '@/components/layout/Logo'
import { ThemeToggle } from '@/components/layout/ThemeToggle'
import { InfoTip, NotchTabBar } from '@/components/student'
import { Button } from '@/components/ui/button'
import { Menu, MenuGroup, MenuGroupLabel, MenuItem, MenuPopup, MenuSeparator, MenuTrigger } from '@/components/ui/menu'
import { cn } from '@/lib/utils'
import '@/styles/student/shell.css'

interface Destination {
  to: string
  /** Label of the desktop top nav (full from lg up). */
  label: string
  /** Label of the mobile bar and of the desktop nav below lg. */
  short: string
  icon: LucideIcon
  end: boolean
}

const DESTINATIONS: Destination[] = [
  { to: '/estudiante', label: 'Inicio', short: 'Inicio', icon: House, end: true },
  { to: '/estudiante/horario', label: 'Mi horario', short: 'Horario', icon: CalendarDays, end: false },
  { to: '/estudiante/rematricula', label: 'Rematrícula', short: 'Rematrícula', icon: ClipboardPen, end: false },
  { to: '/estudiante/historial', label: 'Historial académico', short: 'Historial', icon: GraduationCap, end: false },
  { to: '/estudiante/intensivos', label: 'Cursos de verano e invierno', short: 'Cursos', icon: Sun, end: false },
]

const BAR_ITEMS = DESTINATIONS.map(({ to, short, icon, end }) => ({ to, label: short, icon, end }))

const initials = (name: string) =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]!.toUpperCase()).join('')

export function StudentPortalLayout() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const me = useStudentMe()
  const logout = useStudentLogout()
  const reduceMotion = useReducedMotion()

  if (!localStorage.getItem(STUDENT_TOKEN_KEY)) return <Navigate to="/estudiante/login" replace />
  if (me.data?.must_change_password) return <Navigate to="/estudiante/cambiar-clave" replace />

  // Same end state with reduced motion: the underline lands on the active item without sliding.
  const slide = reduceMotion ? { duration: 0 } : { type: 'spring' as const, stiffness: 420, damping: 36 }

  return (
    <div className="student-scope font-student min-h-screen bg-canvas">
      <header className="sps-header bg-brand shadow-lg shadow-brand-surface/20">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3 md:py-4">
          <div className="flex min-w-0 items-center gap-4">
            <Logo size="sm" />
            <span className="hidden items-center gap-2 border-l border-brand-foreground/20 pl-4 text-sm font-extrabold tracking-wide text-brand-foreground sm:flex">
              <GraduationCap aria-hidden="true" />Portal del estudiante
            </span>
          </div>
          <div className="flex items-center gap-2">
            <InfoTip content="Cambiar tema" side="bottom">
              <span className="inline-flex">
                <ThemeToggle variant="brand" />
              </span>
            </InfoTip>
            <Menu>
              <MenuTrigger
                render={
                  <Button
                    type="button"
                    variant="outline"
                    aria-label={me.data ? `Cuenta de ${me.data.full_name}` : 'Cuenta'}
                    className="sps-account h-11 gap-2 border-brand-foreground/30 bg-brand-foreground/10 px-1.5 text-brand-foreground hover:bg-brand-foreground/20 hover:text-brand-foreground active:scale-95 motion-reduce:active:scale-100 sm:h-10 md:pr-3"
                  />
                }
              >
                <span aria-hidden="true" className="sps-avatar">
                  {me.data ? initials(me.data.full_name) : <GraduationCap />}
                </span>
                {me.data && <span className="hidden max-w-48 truncate text-sm font-extrabold md:inline">{me.data.full_name}</span>}
                <ChevronDown aria-hidden="true" className="sps-chevron hidden md:block" />
              </MenuTrigger>
              <MenuPopup align="end" sideOffset={10} className="sp-glass-sheet sps-menu">
                <MenuGroup>
                  {me.data && (
                    <MenuGroupLabel className="sps-menu-head">
                      <span aria-hidden="true" className="sps-avatar sps-avatar--lg">{initials(me.data.full_name)}</span>
                      <span className="sps-menu-who">
                        <b className="truncate">{me.data.full_name}</b>
                        {me.data.document_number && <span><IdCard aria-hidden="true" />Doc. {me.data.document_number}</span>}
                        {me.data.curriculum_plan && <span><ClipboardCheck aria-hidden="true" />Plan {me.data.curriculum_plan}</span>}
                      </span>
                    </MenuGroupLabel>
                  )}
                  <MenuItem className="sps-menu-item min-h-11 sm:min-h-11" onClick={() => navigate('/estudiante/cambiar-clave')}>
                    <KeyRound aria-hidden="true" />Cambiar contraseña
                  </MenuItem>
                  <MenuSeparator />
                  <MenuItem
                    className="sps-menu-item sps-menu-item--danger min-h-11 sm:min-h-11"
                    onClick={() => { logout(); navigate('/estudiante/login', { replace: true }) }}
                  >
                    <LogOut aria-hidden="true" />Salir
                  </MenuItem>
                </MenuGroup>
              </MenuPopup>
            </Menu>
          </div>
        </div>
        <nav aria-label="Principal" className="mx-auto hidden max-w-5xl gap-1 px-4 md:flex">
          {DESTINATIONS.map(({ to, label, short, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => cn(
                'sps-nav-link group relative inline-flex min-h-12 items-center gap-2 whitespace-nowrap rounded-t-lg px-3.5 text-[0.9375rem] tracking-tight transition-colors',
                'focus-visible:outline-2 focus-visible:outline-solid focus-visible:-outline-offset-2 focus-visible:outline-student-accent-on-band active:scale-95 motion-reduce:active:scale-100',
                isActive ? 'font-black text-brand-foreground' : 'font-bold text-brand-foreground/80 hover:bg-brand-foreground/10 hover:text-brand-foreground',
              )}
            >
              {({ isActive }) => (
                <>
                  <Icon
                    aria-hidden="true"
                    className="size-5 transition-transform duration-300 ease-out group-hover:-translate-y-0.5 group-focus-visible:-translate-y-0.5 motion-reduce:transition-none motion-reduce:group-hover:translate-y-0 motion-reduce:group-focus-visible:translate-y-0"
                  />
                  <span className="lg:hidden">{short}</span>
                  <span className="hidden lg:inline">{label}</span>
                  {isActive && (
                    <motion.span
                      layoutId="student-nav-underline"
                      aria-hidden="true"
                      transition={slide}
                      className="absolute inset-x-2 bottom-0 h-1 rounded-t-full bg-student-accent-line"
                    />
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </header>
      <main
        key={pathname}
        className="page-enter mx-auto max-w-5xl space-y-5 px-4 pt-6 pb-[calc(7.5rem+env(safe-area-inset-bottom))] md:pb-10"
      >
        <Outlet />
      </main>
      <NotchTabBar items={BAR_ITEMS} label="Navegación" className="md:hidden" />
    </div>
  )
}
