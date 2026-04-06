import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search,
  Users,
  Plus,
  UserPlus,
  IdCard,
  GraduationCap,
  CreditCard,
  Loader2,
  Trash2,
} from 'lucide-react'
import { useTeachers, useCreateTeacher, useBulkDeleteTeachers } from '@/api/hooks/useTeachers'
import { LoadingPage } from '@/components/shared/LoadingSpinner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

import type { Teacher } from '@/api/types'

// ─── Create Teacher Dialog ────────────────────────────────────────────────────
function CreateTeacherDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const createTeacher = useCreateTeacher()
  const [form, setForm] = useState({
    ci: '',
    full_name: '',
    email: '',
    phone: '',
    gender: '',
    external_permanent: '',
    academic_level: '',
    profession: '',
    specialty: '',
    bank: '',
    account_number: '',
    sap_code: '',
    invoice_retention: '',
  })
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.ci || !form.full_name) {
      setError('CI y nombre completo son obligatorios.')
      return
    }
    setError(null)
    try {
      await createTeacher.mutateAsync({
        ci: form.ci,
        full_name: form.full_name,
        email: form.email || undefined,
        phone: form.phone || undefined,
        gender: form.gender || undefined,
        external_permanent: form.external_permanent || undefined,
        academic_level: form.academic_level || undefined,
        profession: form.profession || undefined,
        specialty: form.specialty || undefined,
        bank: form.bank || undefined,
        account_number: form.account_number || undefined,
        sap_code: form.sap_code || undefined,
        invoice_retention: form.invoice_retention || undefined,
      })
      setForm({
        ci: '',
        full_name: '',
        email: '',
        phone: '',
        gender: '',
        external_permanent: '',
        academic_level: '',
        profession: '',
        specialty: '',
        bank: '',
        account_number: '',
        sap_code: '',
        invoice_retention: '',
      })
      onClose()
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr?.response?.data?.detail ?? 'No se pudo crear el docente.')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl p-0 overflow-hidden max-h-[90vh] overflow-y-auto">
        {/* Gradient header */}
        <div className="gradient-navy px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
              <UserPlus size={20} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Nuevo Docente</h2>
              <p className="text-white/60 text-sm">Completá los datos del docente</p>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-5">
          {/* Section: Identificación */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <IdCard size={14} className="text-gray-400" />
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                Identificación
              </p>
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
                <Label className="text-sm">Nombre Completo *</Label>
                <Input
                  value={form.full_name}
                  onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
                  placeholder="Juan Pérez García"
                />
              </div>
            </div>
          </div>

          {/* Section: Datos Personales */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <IdCard size={14} className="text-gray-400" />
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                Datos Personales
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-sm">Email</Label>
                <Input
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                  placeholder="docente@upds.edu.bo"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm">Teléfono</Label>
                <Input
                  value={form.phone}
                  onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
                  placeholder="70012345"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm">Género</Label>
                <Select
                  value={form.gender}
                  onValueChange={(v) => setForm((f) => ({ ...f, gender: v }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Seleccionar..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="M">Masculino</SelectItem>
                    <SelectItem value="F">Femenino</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm">Tipo</Label>
                <Select
                  value={form.external_permanent}
                  onValueChange={(v) => setForm((f) => ({ ...f, external_permanent: v }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Seleccionar..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="EXTERNO">Externo</SelectItem>
                    <SelectItem value="PERMANENTE">Permanente</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          {/* Section: Datos Académicos */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <GraduationCap size={14} className="text-gray-400" />
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                Datos Académicos
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-sm">Nivel Académico</Label>
                <Select
                  value={form.academic_level}
                  onValueChange={(v) => setForm((f) => ({ ...f, academic_level: v }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Seleccionar..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Licenciatura">Licenciatura</SelectItem>
                    <SelectItem value="Maestría">Maestría</SelectItem>
                    <SelectItem value="Doctorado">Doctorado</SelectItem>
                    <SelectItem value="Especialidad">Especialidad</SelectItem>
                    <SelectItem value="Técnico Superior">Técnico Superior</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm">Profesión</Label>
                <Input
                  value={form.profession}
                  onChange={(e) => setForm((f) => ({ ...f, profession: e.target.value }))}
                  placeholder="Ej: Ingeniero de Sistemas"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm">Especialidad</Label>
                <Input
                  value={form.specialty}
                  onChange={(e) => setForm((f) => ({ ...f, specialty: e.target.value }))}
                  placeholder="Ej: Desarrollo de Software"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm">Código SAP</Label>
                <Input
                  value={form.sap_code}
                  onChange={(e) => setForm((f) => ({ ...f, sap_code: e.target.value }))}
                  placeholder="Ej: SAP-001"
                />
              </div>
            </div>
          </div>

          {/* Section: Datos Bancarios */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <CreditCard size={14} className="text-gray-400" />
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                Datos Bancarios
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-sm">Banco</Label>
                <Input
                  value={form.bank}
                  onChange={(e) => setForm((f) => ({ ...f, bank: e.target.value }))}
                  placeholder="Ej: Banco Unión"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm">Número de Cuenta</Label>
                <Input
                  value={form.account_number}
                  onChange={(e) => setForm((f) => ({ ...f, account_number: e.target.value }))}
                  placeholder="Ej: 1234567890"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm">Retención Factura</Label>
                <Input
                  value={form.invoice_retention}
                  onChange={(e) => setForm((f) => ({ ...f, invoice_retention: e.target.value }))}
                  placeholder="Ej: IT, IUE"
                />
              </div>
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
              disabled={createTeacher.isPending}
              style={{ backgroundColor: '#003366' }}
              className="text-white"
            >
              {createTeacher.isPending ? (
                <>
                  <Loader2 size={16} className="animate-spin mr-2" />
                  Creando...
                </>
              ) : (
                <>
                  <UserPlus size={16} className="mr-2" />
                  Crear Docente
                </>
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export function TeachersPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [page, setPage] = useState(1)
  const [createOpen, setCreateOpen] = useState(false)
  const [selectedCIs, setSelectedCIs] = useState<Set<string>>(new Set())
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)
  const bulkDelete = useBulkDeleteTeachers()

  const { data, isLoading } = useTeachers({
    search: debouncedSearch || undefined,
    page,
    perPage: 15,
  })

  const totalPages = data ? Math.ceil(data.total / 15) : 1

  const handleSearchChange = (value: string) => {
    setSearch(value)
    setPage(1)
    if (searchTimeout.current) clearTimeout(searchTimeout.current)
    searchTimeout.current = setTimeout(() => {
      setDebouncedSearch(value)
    }, 300)
  }

  const allOnPageSelected =
    (data?.items?.length ?? 0) > 0 &&
    (data?.items ?? []).every((t) => selectedCIs.has(t.ci))

  return (
    <div className="space-y-6">
      {/* Search */}
      <div className="card-3d-static overflow-hidden">
        <div className="py-4 px-5">
          <div className="relative max-w-md">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Buscar por nombre o C.I."
              value={search}
              onChange={(e) => handleSearchChange(e.target.value)}
              className="w-full pl-9 pr-4 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] focus:border-transparent transition-shadow bg-gray-50/50"
            />
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
            Listado de Docentes
          </h3>
          <div className="flex items-center gap-3">
            {data && (
              <span className="text-sm text-gray-500 bg-gray-100 px-2.5 py-1 rounded-full font-medium">
                {data.total} docente{data.total !== 1 ? 's' : ''}
              </span>
            )}
            <Button
              onClick={() => setCreateOpen(true)}
              className="gap-2 text-white"
              style={{ backgroundColor: '#003366' }}
            >
              <Plus size={16} />
              Nuevo Docente
            </Button>
          </div>
        </div>

        {/* Bulk actions bar */}
        {selectedCIs.size > 0 && (
          <div className="mx-5 mt-4 flex items-center justify-between px-4 py-3 bg-red-50 border border-red-200 rounded-lg">
            <span className="text-sm text-red-700 font-medium">
              {selectedCIs.size} docente{selectedCIs.size !== 1 ? 's' : ''} seleccionado{selectedCIs.size !== 1 ? 's' : ''}
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedCIs(new Set())}
                className="text-gray-600"
              >
                Deseleccionar
              </Button>
              <Button
                size="sm"
                className="bg-red-600 hover:bg-red-700 text-white gap-1"
                onClick={() => setShowDeleteConfirm(true)}
              >
                <Trash2 size={14} />
                Eliminar seleccionados
              </Button>
            </div>
          </div>
        )}

        <div className="p-5">
          {isLoading ? (
            <LoadingPage />
          ) : !data?.items.length ? (
            <div className="py-16 text-center">
              <Users size={40} className="mx-auto text-gray-300 mb-3" />
              <p className="text-gray-400 font-medium">
                {debouncedSearch
                  ? `No se encontraron docentes para "${debouncedSearch}"`
                  : 'No hay docentes registrados aún'}
              </p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto rounded-lg border border-gray-200">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ backgroundImage: 'linear-gradient(135deg, #003366 0%, #004d99 50%, #0066CC 100%)' }}>
                      <th className="px-3 py-2.5 w-10">
                        <input
                          type="checkbox"
                          checked={allOnPageSelected}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedCIs(new Set(data?.items?.map((t) => t.ci) ?? []))
                            } else {
                              setSelectedCIs(new Set())
                            }
                          }}
                          className="rounded border-white/50 cursor-pointer"
                        />
                      </th>
                      {['Nombre Completo', 'C.I.', 'Correo', 'Profesión', 'Tipo', 'Detalle'].map((h) => (
                        <th
                          key={h}
                          className="text-left text-white font-semibold text-xs uppercase tracking-wider px-3 py-2.5 whitespace-nowrap"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((teacher: Teacher, i: number) => (
                      <tr
                        key={teacher.ci}
                        className={`border-b last:border-0 hover:bg-blue-50/70 transition-colors ${
                          selectedCIs.has(teacher.ci)
                            ? 'bg-red-50'
                            : i % 2 === 1
                              ? 'bg-gray-50'
                              : 'bg-white'
                        }`}
                      >
                        <td className="px-3 py-2.5 w-10">
                          <input
                            type="checkbox"
                            checked={selectedCIs.has(teacher.ci)}
                            onChange={(e) => {
                              const next = new Set(selectedCIs)
                              if (e.target.checked) next.add(teacher.ci)
                              else next.delete(teacher.ci)
                              setSelectedCIs(next)
                            }}
                            className="rounded cursor-pointer"
                          />
                        </td>
                        <td className="px-3 py-2.5 font-medium text-gray-800">{teacher.full_name}</td>
                        <td className="px-3 py-2.5 text-gray-600">{teacher.ci}</td>
                        <td className="px-3 py-2.5 text-gray-600">{teacher.email ?? '—'}</td>
                        <td className="px-3 py-2.5 text-gray-600">{teacher.profession ?? '—'}</td>
                        <td className="px-3 py-2.5 text-gray-600">
                          {!teacher.external_permanent
                            ? '—'
                            : teacher.external_permanent === 'EXTERNO'
                              ? 'Externo'
                              : 'Permanente'}
                        </td>
                        <td className="px-3 py-2.5">
                          <button
                            onClick={() => navigate(`/teachers/${teacher.ci}`)}
                            className="text-[#0066CC] hover:underline text-sm font-medium"
                          >
                            Ver más →
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-100">
                  <p className="text-sm text-gray-500">
                    Página {page} de {totalPages}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page <= 1}
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                    >
                      Anterior
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page >= totalPages}
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    >
                      Siguiente
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <CreateTeacherDialog open={createOpen} onClose={() => setCreateOpen(false)} />

      {/* Bulk Delete Confirmation Dialog */}
      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent>
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
                <Trash2 size={20} className="text-red-600" />
              </div>
              <div>
                <h3 className="font-semibold text-gray-800">
                  Eliminar {selectedCIs.size} docente{selectedCIs.size !== 1 ? 's' : ''}
                </h3>
                <p className="text-sm text-gray-500">
                  Esta acción eliminará también sus designaciones, asistencia y cuentas de usuario
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={() => setShowDeleteConfirm(false)}>
                Cancelar
              </Button>
              <Button
                className="bg-red-600 hover:bg-red-700 text-white"
                disabled={bulkDelete.isPending}
                onClick={async () => {
                  await bulkDelete.mutateAsync([...selectedCIs])
                  setSelectedCIs(new Set())
                  setShowDeleteConfirm(false)
                }}
              >
                {bulkDelete.isPending ? 'Eliminando...' : 'Confirmar eliminación'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
