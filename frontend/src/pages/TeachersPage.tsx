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
  Trash2,
  AlertCircle,
} from 'lucide-react'
import { useTeachers, useCreateTeacher, useBulkDeleteTeachers } from '@/api/hooks/useTeachers'
import { PageHeader } from '@/components/shared/PageHeader'
import { TableCard } from '@/components/shared/TableCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { ConfirmAlertDialog } from '@/components/shared/ConfirmAlertDialog'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogDescription, DialogFooter, DialogHeader, DialogPanel, DialogPopup, DialogTitle } from '@/components/ui/dialog'
import {
  Select,
  SelectItem,
  SelectPopup,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

import type { Teacher } from '@/api/types'
import { apiErrorMessage } from '@/lib/userCredentials'
import { TEACHER_TYPE_OPTIONS, teacherTypeLabel } from '@/domain/teacherTypes'
import type { TeacherType } from '@/domain/teacherTypes'

const GENDER_ITEMS = [
  { value: 'M', label: 'Masculino' },
  { value: 'F', label: 'Femenino' },
]

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
        external_permanent: (form.external_permanent || undefined) as TeacherType | undefined,
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
      <DialogPopup className="max-w-2xl">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-primary/10">
              <UserPlus size={20} className="text-primary" />
            </div>
            <div className="flex flex-col gap-1">
              <DialogTitle>Nuevo Docente</DialogTitle>
              <DialogDescription>Completá los datos del docente</DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col">
          <DialogPanel className="space-y-5">
            {/* Section: Identificación */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <IdCard size={14} className="text-muted-foreground" />
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Identificación
                </p>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <Field>
                  <FieldLabel>CI *</FieldLabel>
                  <Input
                    value={form.ci}
                    onChange={(e) => setForm((f) => ({ ...f, ci: e.target.value }))}
                    placeholder="12345678"
                  />
                </Field>
                <Field>
                  <FieldLabel>Nombre Completo *</FieldLabel>
                  <Input
                    value={form.full_name}
                    onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
                    placeholder="Juan Pérez García"
                  />
                </Field>
              </div>
            </div>

            {/* Section: Datos Personales */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <IdCard size={14} className="text-muted-foreground" />
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Datos Personales
                </p>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <Field>
                  <FieldLabel>Email</FieldLabel>
                  <Input
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                    placeholder="docente@upds.edu.bo"
                  />
                </Field>
                <Field>
                  <FieldLabel>Teléfono</FieldLabel>
                  <Input
                    value={form.phone}
                    onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
                    placeholder="70012345"
                  />
                </Field>
                <Field>
                  <FieldLabel>Género</FieldLabel>
                  <Select
                    value={form.gender || null}
                    items={GENDER_ITEMS}
                    onValueChange={(v) => setForm((f) => ({ ...f, gender: v ?? '' }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Seleccionar..." />
                    </SelectTrigger>
                    <SelectPopup>
                      <SelectItem value="M">Masculino</SelectItem>
                      <SelectItem value="F">Femenino</SelectItem>
                    </SelectPopup>
                  </Select>
                </Field>
                <Field>
                  <FieldLabel>Tipo</FieldLabel>
                  <Select
                    value={form.external_permanent || null}
                    items={TEACHER_TYPE_OPTIONS}
                    onValueChange={(v) => setForm((f) => ({ ...f, external_permanent: v ?? '' }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Seleccionar..." />
                    </SelectTrigger>
                    <SelectPopup>
                      {TEACHER_TYPE_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                      ))}
                    </SelectPopup>
                  </Select>
                </Field>
              </div>
            </div>

            {/* Section: Datos Académicos */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <GraduationCap size={14} className="text-muted-foreground" />
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Datos Académicos
                </p>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <Field>
                  <FieldLabel>Nivel Académico</FieldLabel>
                  <Select
                    value={form.academic_level || null}
                    onValueChange={(v) => setForm((f) => ({ ...f, academic_level: v ?? '' }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Seleccionar..." />
                    </SelectTrigger>
                    <SelectPopup>
                      <SelectItem value="Licenciatura">Licenciatura</SelectItem>
                      <SelectItem value="Maestría">Maestría</SelectItem>
                      <SelectItem value="Doctorado">Doctorado</SelectItem>
                      <SelectItem value="Especialidad">Especialidad</SelectItem>
                      <SelectItem value="Técnico Superior">Técnico Superior</SelectItem>
                    </SelectPopup>
                  </Select>
                </Field>
                <Field>
                  <FieldLabel>Profesión</FieldLabel>
                  <Input
                    value={form.profession}
                    onChange={(e) => setForm((f) => ({ ...f, profession: e.target.value }))}
                    placeholder="Ej: Ingeniero de Sistemas"
                  />
                </Field>
                <Field>
                  <FieldLabel>Especialidad</FieldLabel>
                  <Input
                    value={form.specialty}
                    onChange={(e) => setForm((f) => ({ ...f, specialty: e.target.value }))}
                    placeholder="Ej: Desarrollo de Software"
                  />
                </Field>
                <Field>
                  <FieldLabel>Código SAP</FieldLabel>
                  <Input
                    value={form.sap_code}
                    onChange={(e) => setForm((f) => ({ ...f, sap_code: e.target.value }))}
                    placeholder="Ej: SAP-001"
                  />
                </Field>
              </div>
            </div>

            {/* Section: Datos Bancarios */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <CreditCard size={14} className="text-muted-foreground" />
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Datos Bancarios
                </p>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <Field>
                  <FieldLabel>Banco</FieldLabel>
                  <Input
                    value={form.bank}
                    onChange={(e) => setForm((f) => ({ ...f, bank: e.target.value }))}
                    placeholder="Ej: Banco Unión"
                  />
                </Field>
                <Field>
                  <FieldLabel>Número de Cuenta</FieldLabel>
                  <Input
                    value={form.account_number}
                    onChange={(e) => setForm((f) => ({ ...f, account_number: e.target.value }))}
                    placeholder="Ej: 1234567890"
                  />
                </Field>
                <Field>
                  <FieldLabel>Retención Factura</FieldLabel>
                  <Input
                    value={form.invoice_retention}
                    onChange={(e) => setForm((f) => ({ ...f, invoice_retention: e.target.value }))}
                    placeholder="Ej: IT, IUE"
                  />
                </Field>
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
            <Button type="submit" loading={createTeacher.isPending}>
              {createTeacher.isPending ? (
                'Creando...'
              ) : (
                <>
                  <UserPlus aria-hidden="true" />
                  Crear Docente
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogPopup>
    </Dialog>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────
const TABLE_HEADERS = ['Nombre Completo', 'C.I.', 'Correo', 'Profesión', 'Tipo', 'Detalle']
const SKELETON_ROWS = 6

export function TeachersPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [page, setPage] = useState(1)
  const [createOpen, setCreateOpen] = useState(false)
  const [selectedCIs, setSelectedCIs] = useState<Set<string>>(new Set())
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)
  const bulkDelete = useBulkDeleteTeachers()

  const { data, isLoading, error, refetch } = useTeachers({
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

  const selectedLabel = `${selectedCIs.size} docente${selectedCIs.size !== 1 ? 's' : ''}`

  const confirmBulkDelete = async () => {
    setDeleteError(null)
    try {
      await bulkDelete.mutateAsync([...selectedCIs])
      setSelectedCIs(new Set())
      setShowDeleteConfirm(false)
    } catch (err) {
      setDeleteError(apiErrorMessage(err, 'No se pudo eliminar a los docentes seleccionados.'))
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Docentes"
        description="Buscá, creá y administrá el padrón de docentes de la sede."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus aria-hidden="true" />
            Nuevo Docente
          </Button>
        }
      />

      {error && (
        <Alert variant="error">
          <AlertCircle aria-hidden="true" />
          <AlertTitle>No se pudo cargar el listado de docentes</AlertTitle>
          <AlertDescription>Revisá tu conexión e intentá nuevamente.</AlertDescription>
          <AlertAction>
            <Button variant="outline" size="sm" onClick={() => void refetch()}>
              Reintentar
            </Button>
          </AlertAction>
        </Alert>
      )}

      <div className="relative w-full sm:max-w-sm">
        <Search size={16} aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 z-10 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          aria-label="Buscar docentes"
          placeholder="Buscar por nombre o C.I."
          value={search}
          onChange={(e) => handleSearchChange(e.target.value)}
          inputClassName="pl-9"
        />
      </div>

      <TableCard
        title="Listado de Docentes"
        description={data ? `${data.total} docente${data.total !== 1 ? 's' : ''}` : undefined}
        footer={
          totalPages > 1 ? (
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground tabular-nums">
                Página {page} de {totalPages}
              </p>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                  Anterior
                </Button>
                <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>
                  Siguiente
                </Button>
              </div>
            </div>
          ) : undefined
        }
      >
        <TableHeader>
          {selectedCIs.size > 0 && (
            <TableRow className="bg-destructive/4 hover:bg-destructive/4">
              <TableCell colSpan={TABLE_HEADERS.length + 1} className="px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-sm font-medium text-destructive-foreground">
                    {selectedCIs.size} docente{selectedCIs.size !== 1 ? 's' : ''} seleccionado{selectedCIs.size !== 1 ? 's' : ''}
                  </span>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={() => setSelectedCIs(new Set())}>
                      Deseleccionar
                    </Button>
                    <Button variant="destructive" size="sm" onClick={() => setShowDeleteConfirm(true)}>
                      <Trash2 aria-hidden="true" />
                      Eliminar seleccionados
                    </Button>
                  </div>
                </div>
              </TableCell>
            </TableRow>
          )}
          <TableRow className="bg-muted/40 hover:bg-muted/40">
            <TableHead className="w-10 px-4">
              <Checkbox
                aria-label="Seleccionar todos los docentes de la página"
                checked={allOnPageSelected}
                onCheckedChange={(checked) => {
                  setSelectedCIs(checked ? new Set(data?.items?.map((t) => t.ci) ?? []) : new Set())
                }}
              />
            </TableHead>
            {TABLE_HEADERS.map((h) => (
              <TableHead key={h} className="h-10 px-4 text-xs font-medium uppercase tracking-wider">
                {h}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            Array.from({ length: SKELETON_ROWS }, (_, rowIndex) => (
              <TableRow key={rowIndex}>
                {Array.from({ length: TABLE_HEADERS.length + 1 }, (_, cellIndex) => (
                  <TableCell key={cellIndex} className="px-4 py-3">
                    <Skeleton className="h-4 w-full max-w-32" />
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : !data?.items.length ? (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={TABLE_HEADERS.length + 1} className="p-0 whitespace-normal">
                <EmptyState
                  icon={Users}
                  title={
                    debouncedSearch
                      ? `No se encontraron docentes para "${debouncedSearch}"`
                      : 'No hay docentes registrados aún'
                  }
                  description={debouncedSearch ? 'Probá con otro nombre o C.I.' : 'Creá el primer docente con el botón Nuevo Docente.'}
                />
              </TableCell>
            </TableRow>
          ) : (
            data.items.map((teacher: Teacher) => (
              <TableRow key={teacher.ci} data-state={selectedCIs.has(teacher.ci) ? 'selected' : undefined}>
                <TableCell className="w-10 px-4 py-3">
                  <Checkbox
                    aria-label={`Seleccionar a ${teacher.full_name}`}
                    checked={selectedCIs.has(teacher.ci)}
                    onCheckedChange={(checked) => {
                      const next = new Set(selectedCIs)
                      if (checked) next.add(teacher.ci)
                      else next.delete(teacher.ci)
                      setSelectedCIs(next)
                    }}
                  />
                </TableCell>
                <TableCell className="px-4 py-3 font-medium text-foreground">{teacher.full_name}</TableCell>
                <TableCell className="px-4 py-3 text-muted-foreground tabular-nums">{teacher.ci}</TableCell>
                <TableCell className="px-4 py-3 text-muted-foreground">{teacher.email ?? '—'}</TableCell>
                <TableCell className="px-4 py-3 text-muted-foreground">{teacher.profession ?? '—'}</TableCell>
                <TableCell className="px-4 py-3 text-muted-foreground">{teacherTypeLabel(teacher.external_permanent)}</TableCell>
                <TableCell className="px-4 py-3">
                  <Button variant="link" size="sm" className="px-0 text-primary" onClick={() => navigate(`/teachers/${teacher.ci}`)}>
                    Ver más →
                  </Button>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </TableCard>

      <CreateTeacherDialog open={createOpen} onClose={() => setCreateOpen(false)} />

      <ConfirmAlertDialog
        summary={
          showDeleteConfirm
            ? {
                title: `Eliminar ${selectedLabel}`,
                confirmLabel: 'Confirmar eliminación',
                tone: 'destructive',
                rows: [{ label: 'Docentes seleccionados', value: String(selectedCIs.size) }],
                warning: 'Esta acción eliminará también sus designaciones, asistencia y cuentas de usuario.',
                consequence: 'No se puede deshacer.',
              }
            : null
        }
        pending={bulkDelete.isPending}
        description={deleteError ?? undefined}
        onConfirm={() => void confirmBulkDelete()}
        onCancel={() => {
          setShowDeleteConfirm(false)
          setDeleteError(null)
        }}
      />
    </div>
  )
}
