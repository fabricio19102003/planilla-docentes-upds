import { useState } from 'react'
import { useMyProfile, useChangePassword } from '@/api/hooks/useAuth'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { User, Mail, Phone, BookOpen, Lock, CheckCircle, AlertCircle } from 'lucide-react'

interface ProfileResponse {
  ci: string
  full_name: string
  email: string | null
  phone: string | null
  gender: string | null
  academic_level: string | null
  profession: string | null
  specialty: string | null
  designations: Array<{
    id: number
    subject: string
    semester: string
    group_code: string
    weekly_hours_calculated: number | null
    semester_hours: number | null
  }>
}

function InfoRow({ icon: Icon, label, value }: { icon: typeof User; label: string; value: string | null }) {
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-gray-100 last:border-0">
      <div
        className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
        style={{ backgroundColor: 'rgba(0,51,102,0.08)' }}
      >
        <Icon size={15} style={{ color: '#003366' }} />
      </div>
      <div>
        <p className="text-xs text-gray-400 font-medium">{label}</p>
        <p className="text-sm text-gray-700 font-medium mt-0.5">{value || '—'}</p>
      </div>
    </div>
  )
}

function ChangePasswordSection() {
  const changePwd = useChangePassword()
  const [form, setForm] = useState({ current: '', newPwd: '', confirm: '' })
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.current || !form.newPwd) {
      setError('Completá todos los campos.')
      return
    }
    if (form.newPwd !== form.confirm) {
      setError('Las contraseñas nuevas no coinciden.')
      return
    }
    if (form.newPwd.length < 4) {
      setError('La contraseña nueva debe tener al menos 4 caracteres.')
      return
    }
    setError(null)
    try {
      await changePwd.mutateAsync({
        current_password: form.current,
        new_password: form.newPwd,
      })
      setSuccess(true)
      setForm({ current: '', newPwd: '', confirm: '' })
      setTimeout(() => setSuccess(false), 3000)
    } catch {
      setError('Contraseña actual incorrecta.')
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Lock size={16} style={{ color: '#003366' }} />
          <CardTitle className="text-base font-semibold" style={{ color: '#003366' }}>
            Cambiar Contraseña
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        {success ? (
          <div className="flex items-center gap-2.5 bg-green-50 border border-green-200 rounded-lg px-4 py-3">
            <CheckCircle size={16} className="text-green-600" />
            <p className="text-green-700 font-medium text-sm">¡Contraseña actualizada correctamente!</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4 max-w-sm">
            <div className="space-y-1.5">
              <Label>Contraseña actual *</Label>
              <Input
                type="password"
                value={form.current}
                onChange={(e) => setForm((f) => ({ ...f, current: e.target.value }))}
                placeholder="••••••••"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Nueva contraseña *</Label>
              <Input
                type="password"
                value={form.newPwd}
                onChange={(e) => setForm((f) => ({ ...f, newPwd: e.target.value }))}
                placeholder="••••••••"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Confirmar nueva contraseña *</Label>
              <Input
                type="password"
                value={form.confirm}
                onChange={(e) => setForm((f) => ({ ...f, confirm: e.target.value }))}
                placeholder="••••••••"
              />
            </div>
            {error && (
              <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg px-3 py-2.5">
                <AlertCircle size={14} className="text-red-500 flex-shrink-0 mt-0.5" />
                <p className="text-red-600 text-sm">{error}</p>
              </div>
            )}
            <Button
              type="submit"
              disabled={changePwd.isPending}
              className="text-white"
              style={{ backgroundColor: '#003366' }}
            >
              {changePwd.isPending ? 'Guardando...' : 'Cambiar Contraseña'}
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  )
}

export function MyProfilePage() {
  const { user } = useAuth()
  const { data: profile, isLoading } = useMyProfile()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-8 h-8 border-2 border-[#003366]/30 border-t-[#003366] rounded-full animate-spin" />
      </div>
    )
  }

  const p = profile as ProfileResponse | undefined

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Profile header */}
      <div
        className="rounded-xl p-6 text-white"
        style={{ background: 'linear-gradient(135deg, #003366 0%, #0066CC 100%)' }}
      >
        <div className="flex items-center gap-5">
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center text-2xl font-black flex-shrink-0"
            style={{ backgroundColor: 'rgba(255,255,255,0.15)' }}
          >
            {user?.full_name?.charAt(0).toUpperCase() ?? 'D'}
          </div>
          <div>
            <h2 className="text-xl font-bold">{p?.full_name ?? user?.full_name}</h2>
            <p className="text-white/70 text-sm mt-0.5">CI: {p?.ci ?? user?.ci}</p>
            <Badge className="mt-2 bg-white/20 text-white border-white/30 text-xs">
              Docente
            </Badge>
          </div>
        </div>
      </div>

      {/* Personal data */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <User size={16} style={{ color: '#003366' }} />
            <CardTitle className="text-base font-semibold" style={{ color: '#003366' }}>
              Datos Personales
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <InfoRow icon={User} label="Nombre Completo" value={p?.full_name ?? null} />
          <InfoRow icon={User} label="Cédula de Identidad" value={p?.ci ?? null} />
          <InfoRow icon={Mail} label="Email" value={p?.email ?? null} />
          <InfoRow icon={Phone} label="Teléfono" value={p?.phone ?? null} />
          <InfoRow icon={BookOpen} label="Nivel Académico" value={p?.academic_level ?? null} />
          <InfoRow icon={BookOpen} label="Profesión" value={p?.profession ?? null} />
          <InfoRow icon={BookOpen} label="Especialidad" value={p?.specialty ?? null} />
        </CardContent>
      </Card>

      {/* Designations */}
      {p?.designations && p.designations.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <BookOpen size={16} style={{ color: '#003366' }} />
              <CardTitle className="text-base font-semibold" style={{ color: '#003366' }}>
                Materias Asignadas ({p.designations.length})
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ backgroundColor: '#003366' }}>
                    {['Materia', 'Semestre', 'Grupo', 'Hs/Semana'].map((h) => (
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
                  {p.designations.map((d, i) => (
                    <tr
                      key={d.id}
                      className={`border-b last:border-0 ${i % 2 === 1 ? 'bg-gray-50' : 'bg-white'}`}
                    >
                      <td className="px-4 py-3 font-medium text-gray-800">{d.subject}</td>
                      <td className="px-4 py-3 text-gray-600">{d.semester}</td>
                      <td className="px-4 py-3">
                        <Badge className="bg-blue-100 text-blue-700 border-blue-200 font-mono">
                          {d.group_code}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-gray-700">
                        {d.weekly_hours_calculated ?? d.semester_hours ?? '—'}h
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Change Password */}
      <ChangePasswordSection />
    </div>
  )
}
