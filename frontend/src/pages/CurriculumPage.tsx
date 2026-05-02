import { useRef, useState } from 'react'
import {
  GraduationCap,
  BookOpen,
  ChevronDown,
  ChevronUp,
  Plus,
  Edit2,
  Trash2,
  Upload,
  FileJson,
  Loader2,
  X,
  Check,
  AlertTriangle,
} from 'lucide-react'
import {
  useCareers,
  useCareer,
  useCreateCareer,
  useUpdateCareer,
  useDeleteCareer,
  useImportCurriculum,
  useCreateSubject,
  useUpdateSubject,
  useDeleteSubject,
} from '@/api/hooks/useScheduling'
import type {
  Career,
  SemesterWithSubjects,
  Subject,
  CurriculumImportResponse,
} from '@/api/hooks/useScheduling'
import { LoadingPage } from '@/components/shared/LoadingSpinner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent } from '@/components/ui/dialog'

// ─── Create Career Dialog ─────────────────────────────────────────────────────

function CreateCareerDialog({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const createCareer = useCreateCareer()
  const [form, setForm] = useState({ code: '', name: '', description: '' })
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.code.trim() || !form.name.trim()) {
      setError('Codigo y nombre son obligatorios.')
      return
    }
    setError(null)
    try {
      await createCareer.mutateAsync({
        code: form.code.trim().toUpperCase(),
        name: form.name.trim(),
        description: form.description.trim() || undefined,
      })
      setForm({ code: '', name: '', description: '' })
      onClose()
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr?.response?.data?.detail ?? 'No se pudo crear la carrera.')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg p-0 overflow-hidden">
        <div className="gradient-navy px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
              <GraduationCap size={20} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Nueva Carrera</h2>
              <p className="text-white/60 text-sm">Registrar una nueva carrera</p>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div className="space-y-1.5">
            <Label className="text-sm">Codigo *</Label>
            <Input
              value={form.code}
              onChange={(e) => setForm((f) => ({ ...f, code: e.target.value.toUpperCase() }))}
              placeholder="ING-SIS"
              className="uppercase"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-sm">Nombre *</Label>
            <Input
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="Ingenieria de Sistemas"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-sm">Descripcion</Label>
            <textarea
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="Descripcion opcional de la carrera..."
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] focus:border-transparent resize-none"
              rows={3}
            />
          </div>

          {error && (
            <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">
              <AlertTriangle size={14} />
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={createCareer.isPending}
              className="text-white"
              style={{ backgroundColor: '#003366' }}
            >
              {createCareer.isPending && <Loader2 size={16} className="animate-spin mr-1" />}
              Crear Carrera
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ─── Edit Career Dialog ───────────────────────────────────────────────────────

function EditCareerDialog({
  open,
  onClose,
  career,
}: {
  open: boolean
  onClose: () => void
  career: Career
}) {
  const updateCareer = useUpdateCareer()
  const [form, setForm] = useState({
    name: career.name,
    description: career.description ?? '',
  })
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim()) {
      setError('El nombre es obligatorio.')
      return
    }
    setError(null)
    try {
      await updateCareer.mutateAsync({
        id: career.id,
        name: form.name.trim(),
        description: form.description.trim() || undefined,
      })
      onClose()
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr?.response?.data?.detail ?? 'No se pudo actualizar la carrera.')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg p-0 overflow-hidden">
        <div className="gradient-navy px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
              <Edit2 size={20} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Editar Carrera</h2>
              <p className="text-white/60 text-sm">{career.code}</p>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div className="space-y-1.5">
            <Label className="text-sm">Nombre *</Label>
            <Input
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-sm">Descripcion</Label>
            <textarea
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] focus:border-transparent resize-none"
              rows={3}
            />
          </div>

          {error && (
            <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">
              <AlertTriangle size={14} />
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={updateCareer.isPending}
              className="text-white"
              style={{ backgroundColor: '#003366' }}
            >
              {updateCareer.isPending && <Loader2 size={16} className="animate-spin mr-1" />}
              Guardar
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ─── Add Subject Dialog ───────────────────────────────────────────────────────

function AddSubjectDialog({
  open,
  onClose,
  semesterId,
}: {
  open: boolean
  onClose: () => void
  semesterId: number
}) {
  const createSubject = useCreateSubject()
  const [form, setForm] = useState({
    code: '',
    name: '',
    theoretical_hours: '0',
    practical_hours: '0',
    credits: '0',
    is_elective: false,
  })
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim()) {
      setError('El nombre de la materia es obligatorio.')
      return
    }
    setError(null)
    try {
      await createSubject.mutateAsync({
        semester_id: semesterId,
        code: form.code.trim() || undefined,
        name: form.name.trim(),
        theoretical_hours: Number(form.theoretical_hours) || 0,
        practical_hours: Number(form.practical_hours) || 0,
        credits: Number(form.credits) || 0,
        is_elective: form.is_elective,
      })
      setForm({
        code: '',
        name: '',
        theoretical_hours: '0',
        practical_hours: '0',
        credits: '0',
        is_elective: false,
      })
      onClose()
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr?.response?.data?.detail ?? 'No se pudo crear la materia.')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg p-0 overflow-hidden">
        <div className="gradient-navy px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
              <BookOpen size={20} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Nueva Materia</h2>
              <p className="text-white/60 text-sm">Agregar materia al semestre</p>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-sm">Codigo</Label>
              <Input
                value={form.code}
                onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
                placeholder="MAT-101"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Nombre *</Label>
              <Input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Calculo I"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <Label className="text-sm">Horas Teoricas</Label>
              <Input
                type="number"
                min="0"
                value={form.theoretical_hours}
                onChange={(e) => setForm((f) => ({ ...f, theoretical_hours: e.target.value }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Horas Practicas</Label>
              <Input
                type="number"
                min="0"
                value={form.practical_hours}
                onChange={(e) => setForm((f) => ({ ...f, practical_hours: e.target.value }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Creditos</Label>
              <Input
                type="number"
                min="0"
                value={form.credits}
                onChange={(e) => setForm((f) => ({ ...f, credits: e.target.value }))}
              />
            </div>
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={form.is_elective}
              onChange={(e) => setForm((f) => ({ ...f, is_elective: e.target.checked }))}
              className="rounded border-gray-300"
            />
            <span className="text-sm text-gray-700">Materia electiva</span>
          </label>

          {error && (
            <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">
              <AlertTriangle size={14} />
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={createSubject.isPending}
              className="text-white"
              style={{ backgroundColor: '#003366' }}
            >
              {createSubject.isPending && <Loader2 size={16} className="animate-spin mr-1" />}
              Agregar Materia
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ─── Edit Subject Dialog ──────────────────────────────────────────────────────

function EditSubjectDialog({
  open,
  onClose,
  subject,
}: {
  open: boolean
  onClose: () => void
  subject: Subject
}) {
  const updateSubject = useUpdateSubject()
  const [form, setForm] = useState({
    code: subject.code ?? '',
    name: subject.name,
    theoretical_hours: String(subject.theoretical_hours),
    practical_hours: String(subject.practical_hours),
    credits: String(subject.credits),
    is_elective: subject.is_elective,
  })
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim()) {
      setError('El nombre de la materia es obligatorio.')
      return
    }
    setError(null)
    try {
      await updateSubject.mutateAsync({
        id: subject.id,
        code: form.code.trim() || undefined,
        name: form.name.trim(),
        theoretical_hours: Number(form.theoretical_hours) || 0,
        practical_hours: Number(form.practical_hours) || 0,
        credits: Number(form.credits) || 0,
        is_elective: form.is_elective,
      })
      onClose()
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr?.response?.data?.detail ?? 'No se pudo actualizar la materia.')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg p-0 overflow-hidden">
        <div className="gradient-navy px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
              <Edit2 size={20} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Editar Materia</h2>
              <p className="text-white/60 text-sm">{subject.name}</p>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-sm">Codigo</Label>
              <Input
                value={form.code}
                onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Nombre *</Label>
              <Input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <Label className="text-sm">Horas Teoricas</Label>
              <Input
                type="number"
                min="0"
                value={form.theoretical_hours}
                onChange={(e) => setForm((f) => ({ ...f, theoretical_hours: e.target.value }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Horas Practicas</Label>
              <Input
                type="number"
                min="0"
                value={form.practical_hours}
                onChange={(e) => setForm((f) => ({ ...f, practical_hours: e.target.value }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Creditos</Label>
              <Input
                type="number"
                min="0"
                value={form.credits}
                onChange={(e) => setForm((f) => ({ ...f, credits: e.target.value }))}
              />
            </div>
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={form.is_elective}
              onChange={(e) => setForm((f) => ({ ...f, is_elective: e.target.checked }))}
              className="rounded border-gray-300"
            />
            <span className="text-sm text-gray-700">Materia electiva</span>
          </label>

          {error && (
            <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">
              <AlertTriangle size={14} />
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={updateSubject.isPending}
              className="text-white"
              style={{ backgroundColor: '#003366' }}
            >
              {updateSubject.isPending && <Loader2 size={16} className="animate-spin mr-1" />}
              Guardar
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ─── Import Result Banner ─────────────────────────────────────────────────────

function ImportResultBanner({
  result,
  onDismiss,
}: {
  result: CurriculumImportResponse
  onDismiss: () => void
}) {
  return (
    <div className="bg-green-50 border border-green-200 rounded-xl p-4">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <Check size={18} className="text-green-600 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-green-800">
              Malla importada exitosamente ({result.career_code})
            </p>
            <p className="text-xs text-green-600 mt-1">
              {result.semesters_created} semestres creados, {result.semesters_existing} existentes
              {' | '}
              {result.subjects_created} materias creadas, {result.subjects_updated} actualizadas
            </p>
            {result.warnings.length > 0 && (
              <div className="mt-2 space-y-1">
                {result.warnings.map((w, i) => (
                  <p key={i} className="text-xs text-amber-700 flex items-center gap-1">
                    <AlertTriangle size={12} />
                    {w}
                  </p>
                ))}
              </div>
            )}
          </div>
        </div>
        <button onClick={onDismiss} className="text-green-400 hover:text-green-600">
          <X size={16} />
        </button>
      </div>
    </div>
  )
}

// ─── Semester Accordion ───────────────────────────────────────────────────────

function SemesterAccordion({ semester }: { semester: SemesterWithSubjects }) {
  const [expanded, setExpanded] = useState(false)
  const [addSubjectOpen, setAddSubjectOpen] = useState(false)
  const [editSubject, setEditSubject] = useState<Subject | null>(null)
  const deleteSubject = useDeleteSubject()
  const [deletingId, setDeletingId] = useState<number | null>(null)

  const handleDeleteSubject = async (subjectId: number) => {
    if (!window.confirm('Eliminar esta materia?')) return
    setDeletingId(subjectId)
    try {
      await deleteSubject.mutateAsync(subjectId)
    } finally {
      setDeletingId(null)
    }
  }

  const ordinalLabel = (n: number) => {
    if (n === 1) return '1er'
    if (n === 2) return '2do'
    if (n === 3) return '3er'
    return `${n}to`
  }

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      {/* Semester header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[#003366]/10 flex items-center justify-center">
            <span className="text-xs font-bold text-[#003366]">{semester.number}</span>
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-800">
              {ordinalLabel(semester.number)} Semestre
            </p>
            <p className="text-xs text-gray-500">
              {semester.subjects.length} materia{semester.subjects.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!semester.is_active && (
            <span className="text-xs px-2 py-0.5 bg-red-100 text-red-700 rounded-full font-medium">
              Inactivo
            </span>
          )}
          {expanded ? (
            <ChevronUp size={18} className="text-gray-400" />
          ) : (
            <ChevronDown size={18} className="text-gray-400" />
          )}
        </div>
      </button>

      {/* Subjects table */}
      {expanded && (
        <div className="p-4">
          {semester.subjects.length === 0 ? (
            <div className="py-8 text-center">
              <BookOpen size={32} className="mx-auto text-gray-300 mb-2" />
              <p className="text-sm text-gray-400">No hay materias en este semestre</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-gray-200">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500 uppercase">
                      Codigo
                    </th>
                    <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500 uppercase">
                      Materia
                    </th>
                    <th className="text-center px-3 py-2 text-xs font-semibold text-gray-500 uppercase">
                      HT
                    </th>
                    <th className="text-center px-3 py-2 text-xs font-semibold text-gray-500 uppercase">
                      HP
                    </th>
                    <th className="text-center px-3 py-2 text-xs font-semibold text-gray-500 uppercase">
                      CR
                    </th>
                    <th className="text-center px-3 py-2 text-xs font-semibold text-gray-500 uppercase">
                      Electiva
                    </th>
                    <th className="text-center px-3 py-2 text-xs font-semibold text-gray-500 uppercase">
                      Estado
                    </th>
                    <th className="text-right px-3 py-2 text-xs font-semibold text-gray-500 uppercase">
                      Acciones
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {semester.subjects.map((subj) => (
                    <tr key={subj.id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-3 py-2 text-gray-600 font-mono text-xs">
                        {subj.code ?? '—'}
                      </td>
                      <td className="px-3 py-2 text-gray-800 font-medium">{subj.name}</td>
                      <td className="px-3 py-2 text-center text-gray-600">
                        {subj.theoretical_hours}
                      </td>
                      <td className="px-3 py-2 text-center text-gray-600">
                        {subj.practical_hours}
                      </td>
                      <td className="px-3 py-2 text-center text-gray-600">{subj.credits}</td>
                      <td className="px-3 py-2 text-center">
                        {subj.is_elective ? (
                          <span className="text-xs px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full font-medium">
                            Si
                          </span>
                        ) : (
                          <span className="text-xs text-gray-400">No</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-center">
                        {subj.is_active ? (
                          <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded-full font-medium">
                            Activa
                          </span>
                        ) : (
                          <span className="text-xs px-2 py-0.5 bg-red-100 text-red-700 rounded-full font-medium">
                            Inactiva
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => setEditSubject(subj)}
                            className="p-1.5 rounded-md hover:bg-blue-50 text-gray-400 hover:text-blue-600 transition-colors"
                            title="Editar"
                          >
                            <Edit2 size={14} />
                          </button>
                          <button
                            onClick={() => handleDeleteSubject(subj.id)}
                            disabled={deletingId === subj.id}
                            className="p-1.5 rounded-md hover:bg-red-50 text-gray-400 hover:text-red-600 transition-colors disabled:opacity-50"
                            title="Eliminar"
                          >
                            {deletingId === subj.id ? (
                              <Loader2 size={14} className="animate-spin" />
                            ) : (
                              <Trash2 size={14} />
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="mt-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setAddSubjectOpen(true)}
              className="gap-1 text-[#003366] border-[#003366]/30 hover:bg-[#003366]/5"
            >
              <Plus size={14} />
              Agregar Materia
            </Button>
          </div>

          {addSubjectOpen && (
            <AddSubjectDialog
              open={addSubjectOpen}
              onClose={() => setAddSubjectOpen(false)}
              semesterId={semester.id}
            />
          )}

          {editSubject && (
            <EditSubjectDialog
              open={!!editSubject}
              onClose={() => setEditSubject(null)}
              subject={editSubject}
            />
          )}
        </div>
      )}
    </div>
  )
}

// ─── Career Detail View ───────────────────────────────────────────────────────

function CareerDetailView({
  careerId,
  onBack,
}: {
  careerId: number
  onBack: () => void
}) {
  const { data: career, isLoading } = useCareer(careerId)
  const [editOpen, setEditOpen] = useState(false)
  const deleteCareer = useDeleteCareer()

  const handleDeactivate = async () => {
    if (!career) return
    if (!window.confirm(`Desactivar la carrera "${career.name}"?`)) return
    await deleteCareer.mutateAsync(career.id)
    onBack()
  }

  if (isLoading) return <LoadingPage />
  if (!career) {
    return (
      <div className="py-16 text-center">
        <GraduationCap size={40} className="mx-auto text-gray-300 mb-3" />
        <p className="text-gray-400 font-medium">Carrera no encontrada</p>
        <Button variant="outline" onClick={onBack} className="mt-4">
          Volver
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Career header */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={onBack}
              className="text-sm text-[#0066CC] hover:underline font-medium"
            >
              Carreras
            </button>
            <span className="text-gray-300">/</span>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold" style={{ color: '#003366' }}>
                  {career.name}
                </h2>
                <span className="text-xs font-mono px-2 py-0.5 bg-gray-100 text-gray-600 rounded">
                  {career.code}
                </span>
                {!career.is_active && (
                  <span className="text-xs px-2 py-0.5 bg-red-100 text-red-700 rounded-full font-medium">
                    Inactiva
                  </span>
                )}
              </div>
              {career.description && (
                <p className="text-sm text-gray-500 mt-0.5">{career.description}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setEditOpen(true)}
              className="gap-1"
            >
              <Edit2 size={14} />
              Editar
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDeactivate}
              disabled={deleteCareer.isPending}
              className="gap-1 text-red-600 border-red-200 hover:bg-red-50"
            >
              {deleteCareer.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Trash2 size={14} />
              )}
              Desactivar
            </Button>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4">
        <div className="card-3d-static p-4">
          <p className="text-xs text-gray-500 uppercase font-semibold tracking-wider">Semestres</p>
          <p className="text-2xl font-bold mt-1" style={{ color: '#003366' }}>
            {career.semesters.length}
          </p>
        </div>
        <div className="card-3d-static p-4">
          <p className="text-xs text-gray-500 uppercase font-semibold tracking-wider">
            Total Materias
          </p>
          <p className="text-2xl font-bold mt-1" style={{ color: '#003366' }}>
            {career.semesters.reduce((acc, s) => acc + s.subjects.length, 0)}
          </p>
        </div>
      </div>

      {/* Semesters accordion */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
            Plan de Estudios
          </h3>
        </div>
        <div className="p-5 space-y-3">
          {career.semesters.length === 0 ? (
            <div className="py-12 text-center">
              <BookOpen size={40} className="mx-auto text-gray-300 mb-3" />
              <p className="text-gray-400 font-medium">
                No hay semestres registrados. Importa una malla curricular para comenzar.
              </p>
            </div>
          ) : (
            career.semesters
              .slice()
              .sort((a, b) => a.number - b.number)
              .map((sem) => <SemesterAccordion key={sem.id} semester={sem} />)
          )}
        </div>
      </div>

      {editOpen && (
        <EditCareerDialog open={editOpen} onClose={() => setEditOpen(false)} career={career} />
      )}
    </div>
  )
}

// ─── Career Card ──────────────────────────────────────────────────────────────

function CareerCard({
  career,
  onSelect,
}: {
  career: Career
  onSelect: (id: number) => void
}) {
  return (
    <button
      onClick={() => onSelect(career.id)}
      className="card-3d-static p-5 text-left hover:shadow-md transition-shadow w-full"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center"
            style={{ backgroundColor: '#003366' }}
          >
            <GraduationCap size={20} className="text-white" />
          </div>
          <div>
            <p className="font-semibold text-gray-800">{career.name}</p>
            <p className="text-xs font-mono text-gray-500">{career.code}</p>
          </div>
        </div>
        {!career.is_active && (
          <span className="text-xs px-2 py-0.5 bg-red-100 text-red-700 rounded-full font-medium">
            Inactiva
          </span>
        )}
      </div>
      <div className="flex items-center gap-4 mt-4">
        <div className="flex items-center gap-1.5 text-xs text-gray-500">
          <BookOpen size={14} />
          <span>
            {career.semester_count} semestre{career.semester_count !== 1 ? 's' : ''}
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-gray-500">
          <FileJson size={14} />
          <span>
            {career.subject_count} materia{career.subject_count !== 1 ? 's' : ''}
          </span>
        </div>
      </div>
    </button>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function CurriculumPage() {
  const { data: careers, isLoading } = useCareers(false)
  const importCurriculum = useImportCurriculum()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [selectedCareerId, setSelectedCareerId] = useState<number | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [importResult, setImportResult] = useState<CurriculumImportResponse | null>(null)
  const [importError, setImportError] = useState<string | null>(null)

  const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    try {
      const text = await file.text()
      const json: unknown = JSON.parse(text)
      setImportError(null)
      const result = await importCurriculum.mutateAsync(json as object)
      setImportResult(result)
      // Navigate to the imported career
      setSelectedCareerId(result.career_id)
    } catch (err: unknown) {
      if (err instanceof SyntaxError) {
        setImportError('El archivo no contiene JSON valido.')
      } else {
        const axiosErr = err as { response?: { data?: { detail?: string } } }
        setImportError(
          axiosErr?.response?.data?.detail ?? 'Error al importar la malla curricular.',
        )
      }
    }
    // Reset the input so the same file can be re-selected
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  // Career detail view
  if (selectedCareerId !== null) {
    return (
      <div className="space-y-6">
        {/* Page header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ backgroundColor: '#003366' }}
            >
              <GraduationCap size={22} className="text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold" style={{ color: '#003366' }}>
                Malla Curricular
              </h1>
              <p className="text-sm text-gray-500">Gestion de plan de estudios</p>
            </div>
          </div>
        </div>

        <CareerDetailView
          careerId={selectedCareerId}
          onBack={() => setSelectedCareerId(null)}
        />
      </div>
    )
  }

  // Career list view
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center"
            style={{ backgroundColor: '#003366' }}
          >
            <GraduationCap size={22} className="text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold" style={{ color: '#003366' }}>
              Malla Curricular
            </h1>
            <p className="text-sm text-gray-500">
              Carreras, semestres y materias del plan de estudios
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            disabled={importCurriculum.isPending}
            className="gap-2"
          >
            {importCurriculum.isPending ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Upload size={16} />
            )}
            Importar Malla
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            onChange={handleImportFile}
            className="hidden"
          />
          <Button
            onClick={() => setCreateOpen(true)}
            className="gap-2 text-white"
            style={{ backgroundColor: '#003366' }}
          >
            <Plus size={16} />
            Nueva Carrera
          </Button>
        </div>
      </div>

      {/* Import result / error banners */}
      {importResult && (
        <ImportResultBanner result={importResult} onDismiss={() => setImportResult(null)} />
      )}
      {importError && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle size={18} className="text-red-500 mt-0.5" />
              <p className="text-sm text-red-700">{importError}</p>
            </div>
            <button
              onClick={() => setImportError(null)}
              className="text-red-400 hover:text-red-600"
            >
              <X size={16} />
            </button>
          </div>
        </div>
      )}

      {/* Career list */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
            Carreras Registradas
          </h3>
          {careers && (
            <span className="text-sm text-gray-500 bg-gray-100 px-2.5 py-1 rounded-full font-medium">
              {careers.length} carrera{careers.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>

        <div className="p-5">
          {isLoading ? (
            <LoadingPage />
          ) : !careers?.length ? (
            <div className="py-16 text-center">
              <GraduationCap size={40} className="mx-auto text-gray-300 mb-3" />
              <p className="text-gray-400 font-medium">No hay carreras registradas</p>
              <p className="text-sm text-gray-400 mt-1">
                Crea una carrera manualmente o importa una malla curricular en formato JSON.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {careers.map((career) => (
                <CareerCard
                  key={career.id}
                  career={career}
                  onSelect={setSelectedCareerId}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {createOpen && (
        <CreateCareerDialog open={createOpen} onClose={() => setCreateOpen(false)} />
      )}
    </div>
  )
}
