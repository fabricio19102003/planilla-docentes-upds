import { useEffect, useState } from 'react'
import { useUsers, useCreateUser, useUpdateUser, useResetUserPassword } from '@/api/hooks/useAuth'
import { useTeachers } from '@/api/hooks/useTeachers'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Field, FieldLabel } from '@/components/ui/field'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { StatCard } from '@/components/shared/StatCard'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { TableCard } from '@/components/shared/TableCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { ConfirmAlertDialog } from '@/components/shared/ConfirmAlertDialog'
import {
  Dialog,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogPanel,
  DialogPopup,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectItem,
  SelectPopup,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  UserPlus,
  RotateCcw,
  UserX,
  UserCheck,
  Users,
  Shield,
  GraduationCap,
  IdCard,
  KeyRound,
  User as UserIcon,
  AlertCircle,
  Search,
  Check,
  X,
} from 'lucide-react'
import type { AuthUser, UserCreate } from '@/api/types'
import { apiErrorMessage, PASSWORD_RULES, passwordIssues } from '@/lib/userCredentials'

const MONTH_NAMES: Record<number, string> = {
  1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun',
  7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic',
}

const ROLE_ITEMS = [
  { value: 'admin', label: 'Administrador' },
  { value: 'docente', label: 'Docente' },
]

const ROLE_FILTER_ITEMS = [
  { value: 'all', label: 'Todos los roles' },
  { value: 'admin', label: 'Administradores' },
  { value: 'docente', label: 'Docentes' },
]

const ACTIVE_FILTER_ITEMS = [
  { value: 'all', label: 'Todos los estados' },
  { value: 'active', label: 'Activos' },
  { value: 'inactive', label: 'Inactivos' },
]

function formatDateTime(dt: string | null) {
  if (!dt) return '—'
  const d = new Date(dt)
  return `${String(d.getDate()).padStart(2, '0')} ${MONTH_NAMES[d.getMonth() + 1]} ${d.getFullYear()}`
}

function PasswordChecklist({ value }: { value: string }) {
  return (
    <ul className="grid grid-cols-2 gap-x-3 gap-y-1 pt-1">
      {PASSWORD_RULES.map((rule) => {
        const ok = rule.test(value)
        return (
          <li
            key={rule.label}
            className={`flex items-center gap-1.5 text-xs ${ok ? 'text-success-foreground' : 'text-muted-foreground'}`}
          >
            {ok ? <Check size={12} /> : <X size={12} />}
            {rule.label}
          </li>
        )
      })}
    </ul>
  )
}

// ─── Create User Dialog ───────────────────────────────────────────────────────
function SectionTitle({ icon: Icon, children }: { icon: typeof IdCard; children: string }) {
  return (
    <div className="mb-3 flex items-center gap-2">
      <Icon size={14} className="text-muted-foreground" aria-hidden="true" />
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{children}</p>
    </div>
  )
}

function CreateUserDialog({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const createUser = useCreateUser()
  const { data: teachers } = useTeachers({ perPage: 200 })

  const [form, setForm] = useState<UserCreate>({
    ci: '',
    full_name: '',
    email: '',
    password: '',
    role: 'docente',
    teacher_ci: '',
  })
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!form.ci || !form.full_name || !form.password) {
      setError('CI, nombre y contraseña son obligatorios.')
      return
    }
    const issues = passwordIssues(form.password)
    if (issues.length) {
      setError(`La contraseña no cumple: ${issues.join(', ').toLowerCase()}.`)
      return
    }
    if (form.role === 'docente' && !form.teacher_ci) {
      setError('Seleccioná el docente vinculado.')
      return
    }
    try {
      await createUser.mutateAsync({
        ...form,
        email: form.email || undefined,
        teacher_ci: form.role === 'docente' ? form.teacher_ci || undefined : undefined,
      })
      setForm({ ci: '', full_name: '', email: '', password: '', role: 'docente', teacher_ci: '' })
      onClose()
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo crear el usuario.'))
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogPopup className="max-w-lg">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-primary/10">
              <UserPlus size={20} className="text-primary" aria-hidden="true" />
            </div>
            <div className="flex flex-col gap-1">
              <DialogTitle>Nuevo Usuario</DialogTitle>
              <DialogDescription>Completá los datos para crear un nuevo usuario</DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col">
          <DialogPanel className="space-y-5">
            {/* Section 1: Identification */}
            <div>
              <SectionTitle icon={IdCard}>Identificación</SectionTitle>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <Field>
                  <FieldLabel htmlFor="create-user-ci">CI *</FieldLabel>
                  <Input
                    id="create-user-ci"
                    value={form.ci}
                    onChange={(e) => setForm((f) => ({ ...f, ci: e.target.value }))}
                    placeholder="12345678"
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="create-user-role">Rol *</FieldLabel>
                  <Select
                    value={form.role}
                    items={ROLE_ITEMS}
                    onValueChange={(v) => setForm((f) => ({ ...f, role: v ?? f.role }))}
                  >
                    <SelectTrigger id="create-user-role">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectPopup>
                      <SelectItem value="admin">
                        <div className="flex items-center gap-2">
                          <Shield size={14} className="text-primary" aria-hidden="true" />
                          Administrador
                        </div>
                      </SelectItem>
                      <SelectItem value="docente">
                        <div className="flex items-center gap-2">
                          <GraduationCap size={14} className="text-success" aria-hidden="true" />
                          Docente
                        </div>
                      </SelectItem>
                    </SelectPopup>
                  </Select>
                </Field>
              </div>
            </div>

            {/* Section 2: Personal info */}
            <div>
              <SectionTitle icon={UserIcon}>Datos Personales</SectionTitle>
              <div className="space-y-3">
                <Field>
                  <FieldLabel htmlFor="create-user-name">Nombre Completo *</FieldLabel>
                  <Input
                    id="create-user-name"
                    value={form.full_name}
                    onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
                    placeholder="Juan Pérez García"
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="create-user-email">Email</FieldLabel>
                  <Input
                    id="create-user-email"
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                    placeholder="juan@upds.edu.bo"
                  />
                </Field>
              </div>
            </div>

            {/* Section 3: Access */}
            <div>
              <SectionTitle icon={KeyRound}>Acceso</SectionTitle>
              <div className="space-y-3">
                <Field>
                  <FieldLabel htmlFor="create-user-password">Contraseña *</FieldLabel>
                  <Input
                    id="create-user-password"
                    type="password"
                    value={form.password}
                    onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                    placeholder="••••••••"
                  />
                  <PasswordChecklist value={form.password} />
                </Field>
                {form.role === 'docente' && (
                  <Field>
                    <FieldLabel htmlFor="create-user-teacher">Docente vinculado</FieldLabel>
                    <Select
                      value={form.teacher_ci || null}
                      items={teachers?.items?.map((t) => ({ value: t.ci, label: `${t.full_name} — ${t.ci}` })) ?? []}
                      onValueChange={(v) => setForm((f) => ({ ...f, teacher_ci: v ?? '' }))}
                    >
                      <SelectTrigger id="create-user-teacher">
                        <SelectValue placeholder="Seleccionar docente..." />
                      </SelectTrigger>
                      <SelectPopup className="max-h-48">
                        {teachers?.items?.map((t) => (
                          <SelectItem key={t.ci} value={t.ci}>
                            {t.full_name} — {t.ci}
                          </SelectItem>
                        ))}
                      </SelectPopup>
                    </Select>
                  </Field>
                )}
              </div>
            </div>

            {error && (
              <Alert variant="error">
                <AlertCircle aria-hidden="true" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
          </DialogPanel>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" loading={createUser.isPending}>
              {createUser.isPending ? (
                'Creando...'
              ) : (
                <>
                  <UserPlus aria-hidden="true" />
                  Crear Usuario
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogPopup>
    </Dialog>
  )
}

// ─── Reset Password Dialog ────────────────────────────────────────────────────
function ResetPasswordDialog({
  user,
  onClose,
}: {
  user: AuthUser | null
  onClose: () => void
}) {
  const resetPwd = useResetUserPassword()
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    const issues = passwordIssues(newPassword)
    if (issues.length) {
      setError(`La contraseña no cumple: ${issues.join(', ').toLowerCase()}.`)
      return
    }
    try {
      await resetPwd.mutateAsync({ id: user!.id, new_password: newPassword })
      setSuccess(true)
      setTimeout(() => {
        setSuccess(false)
        setNewPassword('')
        onClose()
      }, 1500)
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo resetear la contraseña.'))
    }
  }

  return (
    <Dialog open={Boolean(user)} onOpenChange={onClose}>
      <DialogPopup className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Resetear Contraseña</DialogTitle>
        </DialogHeader>
        {success ? (
          <DialogPanel className="text-center">
            <p className="font-medium text-success-foreground">¡Contraseña actualizada!</p>
          </DialogPanel>
        ) : (
          <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col">
            <DialogPanel className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Establecer nueva contraseña para: <span className="font-medium text-foreground">{user?.full_name}</span>
              </p>
              <Field>
                <FieldLabel htmlFor="reset-user-password">Nueva Contraseña *</FieldLabel>
                <Input
                  id="reset-user-password"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="••••••••"
                />
                <PasswordChecklist value={newPassword} />
              </Field>
              {error && (
                <Alert variant="error">
                  <AlertCircle aria-hidden="true" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
            </DialogPanel>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose}>
                Cancelar
              </Button>
              <Button type="submit" loading={resetPwd.isPending}>
                {resetPwd.isPending ? 'Guardando...' : 'Guardar'}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogPopup>
    </Dialog>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export function UsersPage() {
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState<'all' | 'admin' | 'docente'>('all')
  const [activeFilter, setActiveFilter] = useState<'all' | 'active' | 'inactive'>('all')
  const [page, setPage] = useState(1)
  const perPage = 15
  const { data, isLoading, error, refetch } = useUsers({
    search: debouncedSearch || undefined,
    role: roleFilter === 'all' ? undefined : roleFilter,
    active: activeFilter === 'all' ? undefined : activeFilter === 'active',
    page,
    perPage,
  })
  const updateUser = useUpdateUser()

  const [createOpen, setCreateOpen] = useState(false)
  const [resetTarget, setResetTarget] = useState<AuthUser | null>(null)
  const [deactivateTarget, setDeactivateTarget] = useState<AuthUser | null>(null)
  const [deactivateError, setDeactivateError] = useState<string | null>(null)
  const users = data?.items ?? []
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / perPage))

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedSearch(search.trim()), 300)
    return () => window.clearTimeout(timeout)
  }, [search])

  const handleToggleActive = async (u: AuthUser) => {
    await updateUser.mutateAsync({ id: u.id, data: { is_active: !u.is_active } })
  }

  const confirmDeactivate = async () => {
    if (!deactivateTarget) return
    setDeactivateError(null)
    try {
      await handleToggleActive(deactivateTarget)
      setDeactivateTarget(null)
    } catch (err) {
      setDeactivateError(apiErrorMessage(err, 'No se pudo desactivar al usuario.'))
    }
  }

  if (isLoading) {
    return (
      <div role="status" aria-live="polite" aria-label="Cargando usuarios" className="space-y-6">
        <Skeleton className="h-16 w-full max-w-md" />
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-24 rounded-2xl" />
          ))}
        </div>
        <Skeleton className="h-80 rounded-2xl" />
      </div>
    )
  }

  if (error) {
    return (
      <Alert variant="error">
        <AlertCircle aria-hidden="true" />
        <AlertTitle>Error al cargar usuarios</AlertTitle>
        <AlertDescription>No pudimos obtener la lista de usuarios. Intentá nuevamente.</AlertDescription>
        <AlertAction>
          <Button variant="outline" size="sm" onClick={() => void refetch()}>
            Reintentar
          </Button>
        </AlertAction>
      </Alert>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Usuarios del Sistema"
        description={`${data?.summary.total ?? 0} usuarios registrados`}
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <UserPlus aria-hidden="true" />
            Nuevo Usuario
          </Button>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard icon={Users} title="Total" value={data?.summary.total ?? 0} subtitle="Usuarios registrados" tone="primary" />
        <StatCard icon={Shield} title="Administradores" value={data?.summary.admins ?? 0} subtitle="Rol administrativo" tone="info" />
        <StatCard icon={GraduationCap} title="Docentes" value={data?.summary.docentes ?? 0} subtitle="Rol docente" tone="success" />
        <StatCard icon={UserCheck} title="Activos" value={data?.summary.active ?? 0} subtitle="Usuarios activos" tone="primary" />
      </div>

      {/* Server-side search and filters */}
      <Card render={<section aria-label="Filtros de usuarios" />} className="p-5">
        <div className="grid gap-4 md:grid-cols-[minmax(260px,1fr)_220px_220px]">
          <Field>
            <FieldLabel htmlFor="user-search">Buscar usuarios</FieldLabel>
            <div className="relative w-full">
              <Search aria-hidden="true" size={16} className="pointer-events-none absolute left-3 top-1/2 z-10 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="user-search"
                type="search"
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value)
                  setPage(1)
                }}
                placeholder="Nombre, CI, correo o docente vinculado"
                inputClassName="pl-9"
              />
            </div>
          </Field>
          <Field>
            <FieldLabel htmlFor="user-role-filter">Rol</FieldLabel>
            <Select value={roleFilter} items={ROLE_FILTER_ITEMS} onValueChange={(value) => {
              setRoleFilter((value ?? 'all') as typeof roleFilter)
              setPage(1)
            }}>
              <SelectTrigger id="user-role-filter"><SelectValue /></SelectTrigger>
              <SelectPopup>
                <SelectItem value="all">Todos los roles</SelectItem>
                <SelectItem value="admin">Administradores</SelectItem>
                <SelectItem value="docente">Docentes</SelectItem>
              </SelectPopup>
            </Select>
          </Field>
          <Field>
            <FieldLabel htmlFor="user-active-filter">Estado</FieldLabel>
            <Select value={activeFilter} items={ACTIVE_FILTER_ITEMS} onValueChange={(value) => {
              setActiveFilter((value ?? 'all') as typeof activeFilter)
              setPage(1)
            }}>
              <SelectTrigger id="user-active-filter"><SelectValue /></SelectTrigger>
              <SelectPopup>
                <SelectItem value="all">Todos los estados</SelectItem>
                <SelectItem value="active">Activos</SelectItem>
                <SelectItem value="inactive">Inactivos</SelectItem>
              </SelectPopup>
            </Select>
          </Field>
        </div>
      </Card>

      {/* Table */}
      <TableCard
        title="Lista de Usuarios"
        footer={
          data && data.total > 0 ? (
            <nav aria-label="Paginación de usuarios" className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground tabular-nums" aria-live="polite">
                Página {page} de {totalPages} · {data.total} resultado{data.total === 1 ? '' : 's'}
              </p>
              <div className="flex gap-2">
                <Button type="button" variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>
                  Anterior
                </Button>
                <Button type="button" variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((current) => Math.min(totalPages, current + 1))}>
                  Siguiente
                </Button>
              </div>
            </nav>
          ) : undefined
        }
      >
        <caption className="sr-only">Usuarios del sistema y acciones administrativas</caption>
        <TableHeader>
          <TableRow className="bg-muted/40 hover:bg-muted/40">
            {['Nombre', 'CI', 'Rol', 'Vinculado a', 'Estado', 'Último Login', 'Acciones'].map((h) => (
              <TableHead key={h} scope="col" className="h-10 px-4 text-xs font-medium uppercase tracking-wider">
                {h}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {!users.length ? (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={7} className="p-0 whitespace-normal">
                <EmptyState icon={Users} title="No hay usuarios registrados" description="Probá con otros filtros o creá un nuevo usuario." />
              </TableCell>
            </TableRow>
          ) : (
            users.map((u) => (
              <TableRow key={u.id}>
                <TableCell className="px-4 py-3 font-medium text-foreground">{u.full_name}</TableCell>
                <TableCell className="px-4 py-3 font-mono text-xs text-muted-foreground">{u.ci}</TableCell>
                <TableCell className="px-4 py-3">
                  <StatusBadge tone={u.role === 'admin' ? 'info' : 'success'}>
                    {u.role === 'admin' ? 'Admin' : 'Docente'}
                  </StatusBadge>
                </TableCell>
                <TableCell className="px-4 py-3 text-xs text-muted-foreground">{u.teacher_ci ?? '—'}</TableCell>
                <TableCell className="px-4 py-3">
                  <StatusBadge tone={u.is_active ? 'success' : 'neutral'}>
                    {u.is_active ? 'Activo' : 'Inactivo'}
                  </StatusBadge>
                </TableCell>
                <TableCell className="px-4 py-3 text-xs text-muted-foreground">{formatDateTime(u.last_login)}</TableCell>
                <TableCell className="px-4 py-3">
                  <div className="flex items-center gap-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => setResetTarget(u)}
                      title="Resetear contraseña"
                      aria-label={`Resetear contraseña de ${u.full_name}`}
                    >
                      <RotateCcw aria-hidden="true" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      className={u.is_active ? 'hover:text-destructive-foreground' : 'hover:text-success-foreground'}
                      onClick={() => (u.is_active ? setDeactivateTarget(u) : void handleToggleActive(u))}
                      title={u.is_active ? 'Desactivar' : 'Activar'}
                      aria-label={`${u.is_active ? 'Desactivar' : 'Activar'} a ${u.full_name}`}
                    >
                      {u.is_active ? <UserX aria-hidden="true" /> : <UserCheck aria-hidden="true" />}
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </TableCard>

      {/* Dialogs */}
      <CreateUserDialog open={createOpen} onClose={() => setCreateOpen(false)} />
      <ResetPasswordDialog user={resetTarget} onClose={() => setResetTarget(null)} />
      <ConfirmAlertDialog
        summary={
          deactivateTarget
            ? {
                title: 'Desactivar usuario',
                confirmLabel: 'Desactivar',
                tone: 'destructive',
                rows: [
                  { label: 'Usuario', value: deactivateTarget.full_name },
                  { label: 'CI', value: deactivateTarget.ci },
                  { label: 'Rol', value: deactivateTarget.role === 'admin' ? 'Administrador' : 'Docente' },
                ],
                consequence: 'El usuario no podrá ingresar a SIPAD hasta que lo vuelvas a activar.',
              }
            : null
        }
        pending={updateUser.isPending}
        description={deactivateError ?? undefined}
        onConfirm={() => void confirmDeactivate()}
        onCancel={() => {
          setDeactivateTarget(null)
          setDeactivateError(null)
        }}
      />
    </div>
  )
}
