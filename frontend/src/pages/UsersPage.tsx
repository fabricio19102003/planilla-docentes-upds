import { useEffect, useState } from 'react'
import { useUsers, useCreateUser, useUpdateUser, useResetUserPassword } from '@/api/hooks/useAuth'
import { useTeachers } from '@/api/hooks/useTeachers'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { StatCard } from '@/components/shared/StatCard'
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
  Loader2,
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
            className={`flex items-center gap-1.5 text-xs ${ok ? 'text-green-600' : 'text-gray-400'}`}
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
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <UserPlus size={20} className="text-primary" />
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
              <div className="flex items-center gap-2 mb-3">
                <IdCard size={14} className="text-gray-400" />
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Identificación</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="create-user-ci" className="text-sm">CI *</Label>
                  <Input
                    id="create-user-ci"
                    value={form.ci}
                    onChange={(e) => setForm((f) => ({ ...f, ci: e.target.value }))}
                    placeholder="12345678"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="create-user-role" className="text-sm">Rol *</Label>
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
                          <Shield size={14} className="text-blue-600" />
                          Administrador
                        </div>
                      </SelectItem>
                      <SelectItem value="docente">
                        <div className="flex items-center gap-2">
                          <GraduationCap size={14} className="text-green-600" />
                          Docente
                        </div>
                      </SelectItem>
                    </SelectPopup>
                  </Select>
                </div>
              </div>
            </div>

            {/* Section 2: Personal info */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <UserIcon size={14} className="text-gray-400" />
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Datos Personales</p>
              </div>
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label htmlFor="create-user-name" className="text-sm">Nombre Completo *</Label>
                  <Input
                    id="create-user-name"
                    value={form.full_name}
                    onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
                    placeholder="Juan Pérez García"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="create-user-email" className="text-sm">Email</Label>
                  <Input
                    id="create-user-email"
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                    placeholder="juan@upds.edu.bo"
                  />
                </div>
              </div>
            </div>

            {/* Section 3: Access */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <KeyRound size={14} className="text-gray-400" />
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Acceso</p>
              </div>
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label htmlFor="create-user-password" className="text-sm">Contraseña *</Label>
                  <Input
                    id="create-user-password"
                    type="password"
                    value={form.password}
                    onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                    placeholder="••••••••"
                  />
                  <PasswordChecklist value={form.password} />
                </div>
                {form.role === 'docente' && (
                  <div className="space-y-1.5">
                    <Label htmlFor="create-user-teacher" className="text-sm">Docente vinculado</Label>
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
                  </div>
                )}
              </div>
            </div>

            {error && (
              <p role="alert" className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

          </DialogPanel>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={createUser.isPending}
            >
              {createUser.isPending ? (
                <>
                  <Loader2 size={16} className="animate-spin mr-2" />
                  Creando...
                </>
              ) : (
                <>
                  <UserPlus size={16} className="mr-2" />
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
            <p className="text-green-600 font-medium">¡Contraseña actualizada!</p>
          </DialogPanel>
        ) : (
          <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col">
            <DialogPanel className="space-y-4">
              <p className="text-sm text-gray-500">
                Establecer nueva contraseña para: <span className="font-medium text-gray-700">{user?.full_name}</span>
              </p>
              <div className="space-y-1.5">
                <Label htmlFor="reset-user-password">Nueva Contraseña *</Label>
                <Input
                  id="reset-user-password"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="••••••••"
                />
                <PasswordChecklist value={newPassword} />
              </div>
              {error && (
                <p role="alert" className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
                  {error}
                </p>
              )}
            </DialogPanel>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose}>
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={resetPwd.isPending}
              >
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
  const { data, isLoading, error } = useUsers({
    search: debouncedSearch || undefined,
    role: roleFilter === 'all' ? undefined : roleFilter,
    active: activeFilter === 'all' ? undefined : activeFilter === 'active',
    page,
    perPage,
  })
  const updateUser = useUpdateUser()

  const [createOpen, setCreateOpen] = useState(false)
  const [resetTarget, setResetTarget] = useState<AuthUser | null>(null)
  const users = data?.items ?? []
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / perPage))

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedSearch(search.trim()), 300)
    return () => window.clearTimeout(timeout)
  }, [search])

  const handleToggleActive = async (u: AuthUser) => {
    await updateUser.mutateAsync({ id: u.id, data: { is_active: !u.is_active } })
  }

  if (isLoading) {
    return (
      <div role="status" aria-live="polite" className="flex items-center justify-center gap-3 py-24 text-sm text-gray-500">
        <div className="w-8 h-8 border-2 border-[#003366]/30 border-t-[#003366] rounded-full animate-spin motion-reduce:animate-none" />
        Cargando usuarios...
      </div>
    )
  }

  if (error) {
    return (
      <div role="alert" className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <p className="text-red-600 font-medium">Error al cargar usuarios</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold" style={{ color: '#003366' }}>
            Usuarios del Sistema
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            {data?.summary.total ?? 0} usuarios registrados
          </p>
        </div>
        <Button
          onClick={() => setCreateOpen(true)}
          className="gap-2 text-white"
          style={{ backgroundColor: '#003366' }}
        >
          <UserPlus size={16} />
          Nuevo Usuario
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <div>
          <StatCard icon={Users} title="Total" value={data?.summary.total ?? 0} subtitle="Usuarios registrados" color="#003366" />
        </div>
        <div>
          <StatCard icon={Shield} title="Administradores" value={data?.summary.admins ?? 0} subtitle="Rol administrativo" color="#1d4ed8" />
        </div>
        <div>
          <StatCard icon={GraduationCap} title="Docentes" value={data?.summary.docentes ?? 0} subtitle="Rol docente" color="#15803d" />
        </div>
        <div>
          <StatCard icon={UserCheck} title="Activos" value={data?.summary.active ?? 0} subtitle="Usuarios activos" color="#0066CC" />
        </div>
      </div>

      {/* Server-side search and filters */}
      <section aria-label="Filtros de usuarios" className="card-3d-static p-5">
        <div className="grid gap-4 md:grid-cols-[minmax(260px,1fr)_220px_220px]">
          <div className="space-y-1.5">
            <Label htmlFor="user-search">Buscar usuarios</Label>
            <div className="relative">
              <Search aria-hidden="true" size={16} className="pointer-events-none absolute left-3 top-1/2 z-10 -translate-y-1/2 text-gray-400" />
              <Input
                id="user-search"
                type="search"
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value)
                  setPage(1)
                }}
                placeholder="Nombre, CI, correo o docente vinculado"
                className="pl-9"
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="user-role-filter">Rol</Label>
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
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="user-active-filter">Estado</Label>
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
          </div>
        </div>
      </section>

      {/* Table */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <h3 className="text-base font-semibold" style={{ color: '#003366' }}>Lista de Usuarios</h3>
        </div>
        <div className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">Usuarios del sistema y acciones administrativas</caption>
              <thead>
                <tr style={{ backgroundImage: 'linear-gradient(135deg, #003366 0%, #004d99 50%, #0066CC 100%)' }}>
                  {['Nombre', 'CI', 'Rol', 'Vinculado a', 'Estado', 'Último Login', 'Acciones'].map((h) => (
                    <th
                      key={h}
                      scope="col"
                      className="text-left text-white font-semibold text-xs uppercase tracking-wider px-4 py-3"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {!users.length ? (
                  <tr>
                    <td colSpan={7} className="text-center py-12 text-gray-400">
                      No hay usuarios registrados
                    </td>
                  </tr>
                ) : (
                  users.map((u, i) => (
                    <tr
                      key={u.id}
                      className={`border-b last:border-0 hover:bg-blue-50 transition-colors ${
                        i % 2 === 1 ? 'bg-gray-50' : 'bg-white'
                      }`}
                    >
                      <td className="px-4 py-3 font-medium text-gray-800">{u.full_name}</td>
                      <td className="px-4 py-3 text-gray-600 font-mono text-xs">{u.ci}</td>
                      <td className="px-4 py-3">
                        <Badge
                          className={
                            u.role === 'admin'
                              ? 'bg-blue-100 text-blue-700 border-blue-200'
                              : 'bg-green-100 text-green-700 border-green-200'
                          }
                        >
                          {u.role === 'admin' ? 'Admin' : 'Docente'}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs">
                        {u.teacher_ci ?? '—'}
                      </td>
                      <td className="px-4 py-3">
                        <Badge
                          className={
                            u.is_active
                              ? 'bg-green-100 text-green-700 border-green-200'
                              : 'bg-gray-100 text-gray-500 border-gray-200'
                          }
                        >
                          {u.is_active ? 'Activo' : 'Inactivo'}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs">
                        {formatDateTime(u.last_login)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => setResetTarget(u)}
                            className="p-1.5 rounded text-gray-400 hover:text-[#003366] hover:bg-blue-50 transition-colors"
                            title="Resetear contraseña"
                            aria-label={`Resetear contraseña de ${u.full_name}`}
                          >
                            <RotateCcw size={14} />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleToggleActive(u)}
                            className={`p-1.5 rounded transition-colors ${
                              u.is_active
                                ? 'text-gray-400 hover:text-red-500 hover:bg-red-50'
                                : 'text-gray-400 hover:text-green-600 hover:bg-green-50'
                            }`}
                            title={u.is_active ? 'Desactivar' : 'Activar'}
                            aria-label={`${u.is_active ? 'Desactivar' : 'Activar'} a ${u.full_name}`}
                          >
                            {u.is_active ? <UserX size={14} /> : <UserCheck size={14} />}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          {data && data.total > 0 && (
            <nav aria-label="Paginación de usuarios" className="flex items-center justify-between border-t border-gray-100 px-5 py-4">
              <p className="text-sm text-gray-500" aria-live="polite">
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
          )}
        </div>
      </div>

      {/* Dialogs */}
      <CreateUserDialog open={createOpen} onClose={() => setCreateOpen(false)} />
      <ResetPasswordDialog user={resetTarget} onClose={() => setResetTarget(null)} />
    </div>
  )
}
