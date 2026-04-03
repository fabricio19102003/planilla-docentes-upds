import { useState } from 'react'
import { useUsers, useCreateUser, useUpdateUser, useResetUserPassword } from '@/api/hooks/useAuth'
import { useTeachers } from '@/api/hooks/useTeachers'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { StatCard } from '@/components/shared/StatCard'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
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
} from 'lucide-react'
import type { AuthUser, UserCreate } from '@/api/types'

const MONTH_NAMES: Record<number, string> = {
  1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun',
  7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic',
}

function formatDateTime(dt: string | null) {
  if (!dt) return '—'
  const d = new Date(dt)
  return `${String(d.getDate()).padStart(2, '0')} ${MONTH_NAMES[d.getMonth() + 1]} ${d.getFullYear()}`
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
    try {
      await createUser.mutateAsync({
        ...form,
        email: form.email || undefined,
        teacher_ci: form.role === 'docente' ? form.teacher_ci || undefined : undefined,
      })
      setForm({ ci: '', full_name: '', email: '', password: '', role: 'docente', teacher_ci: '' })
      onClose()
    } catch {
      setError('No se pudo crear el usuario. Verificá que el CI no esté duplicado.')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg p-0 overflow-hidden">
        {/* Header with gradient */}
        <div className="gradient-navy px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
              <UserPlus size={20} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Nuevo Usuario</h2>
              <p className="text-white/60 text-sm">Completá los datos para crear un nuevo usuario</p>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-5">
          {/* Section 1: Identification */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <IdCard size={14} className="text-gray-400" />
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Identificación</p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-sm">CI *</Label>
                <Input
                  value={form.ci}
                  onChange={(e) => setForm((f) => ({ ...f, ci: e.target.value }))}
                  placeholder="12345678"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm">Rol *</Label>
                <Select value={form.role} onValueChange={(v) => setForm((f) => ({ ...f, role: v }))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
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
                  </SelectContent>
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
                <Label className="text-sm">Nombre Completo *</Label>
                <Input
                  value={form.full_name}
                  onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
                  placeholder="Juan Pérez García"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm">Email</Label>
                <Input
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
                <Label className="text-sm">Contraseña *</Label>
                <Input
                  type="password"
                  value={form.password}
                  onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                  placeholder="••••••••"
                />
              </div>
              {form.role === 'docente' && (
                <div className="space-y-1.5">
                  <Label className="text-sm">Docente vinculado</Label>
                  <Select
                    value={form.teacher_ci ?? ''}
                    onValueChange={(v) => setForm((f) => ({ ...f, teacher_ci: v }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Seleccionar docente..." />
                    </SelectTrigger>
                    <SelectContent className="max-h-48">
                      {teachers?.items?.map((t) => (
                        <SelectItem key={t.ci} value={t.ci}>
                          {t.full_name} — {t.ci}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={createUser.isPending}
              style={{ backgroundColor: '#003366' }}
              className="text-white"
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
          </div>
        </form>
      </DialogContent>
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
    if (!newPassword || newPassword.length < 4) {
      setError('La contraseña debe tener al menos 4 caracteres.')
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
    } catch {
      setError('No se pudo resetear la contraseña.')
    }
  }

  return (
    <Dialog open={Boolean(user)} onOpenChange={onClose}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle style={{ color: '#003366' }}>Resetear Contraseña</DialogTitle>
        </DialogHeader>
        {success ? (
          <div className="py-4 text-center">
            <p className="text-green-600 font-medium">¡Contraseña actualizada!</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <p className="text-sm text-gray-500">
              Establecer nueva contraseña para: <span className="font-medium text-gray-700">{user?.full_name}</span>
            </p>
            <div className="space-y-1.5">
              <Label>Nueva Contraseña *</Label>
              <Input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>
            {error && (
              <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
                {error}
              </p>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose}>
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={resetPwd.isPending}
                style={{ backgroundColor: '#003366' }}
              >
                {resetPwd.isPending ? 'Guardando...' : 'Guardar'}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export function UsersPage() {
  const { data: users, isLoading, error } = useUsers()
  const updateUser = useUpdateUser()

  const [createOpen, setCreateOpen] = useState(false)
  const [resetTarget, setResetTarget] = useState<AuthUser | null>(null)

  const handleToggleActive = async (u: AuthUser) => {
    await updateUser.mutateAsync({ id: u.id, data: { is_active: !u.is_active } })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-8 h-8 border-2 border-[#003366]/30 border-t-[#003366] rounded-full animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
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
            {users?.length ?? 0} usuarios registrados
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
        <div className="animate-fade-in-up stagger-1">
          <StatCard icon={Users} title="Total" value={users?.length ?? 0} subtitle="Usuarios registrados" color="#003366" />
        </div>
        <div className="animate-fade-in-up stagger-2">
          <StatCard icon={Shield} title="Administradores" value={users?.filter(u => u.role === 'admin').length ?? 0} subtitle="Rol administrativo" color="#1d4ed8" />
        </div>
        <div className="animate-fade-in-up stagger-3">
          <StatCard icon={GraduationCap} title="Docentes" value={users?.filter(u => u.role === 'docente').length ?? 0} subtitle="Rol docente" color="#15803d" />
        </div>
        <div className="animate-fade-in-up stagger-4">
          <StatCard icon={UserCheck} title="Activos" value={users?.filter(u => u.is_active).length ?? 0} subtitle="Usuarios activos" color="#0066CC" />
        </div>
      </div>

      {/* Table */}
      <div className="card-3d-static overflow-hidden animate-fade-in-up stagger-5">
        <div className="px-5 py-4 border-b border-gray-100">
          <h3 className="text-base font-semibold" style={{ color: '#003366' }}>Lista de Usuarios</h3>
        </div>
        <div className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ backgroundImage: 'linear-gradient(135deg, #003366 0%, #004d99 50%, #0066CC 100%)' }}>
                  {['Nombre', 'CI', 'Rol', 'Vinculado a', 'Estado', 'Último Login', 'Acciones'].map((h) => (
                    <th
                      key={h}
                      className="text-left text-white font-semibold text-xs uppercase tracking-wider px-4 py-3"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {!users?.length ? (
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
                            onClick={() => setResetTarget(u)}
                            className="p-1.5 rounded text-gray-400 hover:text-[#003366] hover:bg-blue-50 transition-colors"
                            title="Resetear contraseña"
                          >
                            <RotateCcw size={14} />
                          </button>
                          <button
                            onClick={() => handleToggleActive(u)}
                            className={`p-1.5 rounded transition-colors ${
                              u.is_active
                                ? 'text-gray-400 hover:text-red-500 hover:bg-red-50'
                                : 'text-gray-400 hover:text-green-600 hover:bg-green-50'
                            }`}
                            title={u.is_active ? 'Desactivar' : 'Activar'}
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
        </div>
      </div>

      {/* Dialogs */}
      <CreateUserDialog open={createOpen} onClose={() => setCreateOpen(false)} />
      <ResetPasswordDialog user={resetTarget} onClose={() => setResetTarget(null)} />
    </div>
  )
}
