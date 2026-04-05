import { useState } from 'react'
import { useMyProfile, useMySchedule, downloadRetentionLetter } from '@/api/hooks/useAuth'
import type { RetentionLetterPayload } from '@/api/hooks/useAuth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { FileText, Download, Loader2 } from 'lucide-react'

// ─── Constants ─────────────────────────────────────────────────────────────────

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

const TITULOS = [
  { value: 'Dr.', label: 'Dr. (Doctor/a)' },
  { value: 'Dra.', label: 'Dra. (Doctora)' },
  { value: 'Lic.', label: 'Lic. (Licenciado/a)' },
  { value: 'Ing.', label: 'Ing. (Ingeniero/a)' },
  { value: 'Arq.', label: 'Arq. (Arquitecto/a)' },
  { value: 'Abog.', label: 'Abog. (Abogado/a)' },
  { value: 'M.Sc.', label: 'M.Sc. (Magíster)' },
  { value: 'Ph.D.', label: 'Ph.D. (Doctor en Filosofía)' },
  { value: 'Prof.', label: 'Prof. (Profesor/a)' },
]

// ─── Letter preview ────────────────────────────────────────────────────────────

interface PreviewProps {
  teacherName: string
  teacherCi: string
  materias: string[]
  form: RetentionLetterPayload
}

function LetterPreview({ teacherName, teacherCi, materias, form }: PreviewProps) {
  const today = new Date()
  const dia = today.getDate()
  const mesHoy = MONTH_NAMES[today.getMonth() + 1] ?? ''
  const anioHoy = today.getFullYear()
  const mesCobro = MONTH_NAMES[form.mes_cobro] ?? '—'
  const materiasText = materias.length > 0 ? materias.join(', ') : '—'

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-100 flex items-center gap-2">
        <FileText size={14} className="text-gray-400" />
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
          Vista previa de la carta
        </span>
      </div>

      {/* A4-style letter area */}
      <div className="p-8 font-serif text-[13px] leading-relaxed text-gray-900 max-w-[680px] mx-auto">
        {/* Logo placeholder */}
        <div className="flex justify-center mb-6">
          <div className="w-10 h-10 rounded-full bg-[#003366]/10 flex items-center justify-center">
            <span className="text-[#003366] font-black text-sm">S</span>
          </div>
        </div>

        {/* Date */}
        <p className="text-right mb-10">
          Cobija, {dia} de {mesHoy} de {anioHoy}
        </p>

        {/* Addressee */}
        <p className="mb-1">Lic. Luis Michel Bravo Alencar</p>
        <p className="font-bold mb-1">
          RECTOR DE LA UNIVERSIDAD PRIVADA DOMINGO SAVIO – UNIPANDO S.R.L.
        </p>
        <p className="font-bold mb-10">PRESENTE.-</p>

        {/* Reference */}
        <p className="text-right font-bold underline mb-8">
          Ref.- SOLICITUD DE RETENCIÓN DE IMPUESTO RC-IVA 13%
        </p>

        {/* Greeting */}
        <p className="mb-4">De mi consideración:</p>

        {/* Body */}
        <p className="text-justify mb-6">
          Por medio de la presente me dirijo a su autoridad con la finalidad de solicitarle
          la retención de impuesto de mis honorarios de acuerdo al contrato del Periodo{' '}
          <span className="font-semibold">{form.periodo || '[Período]'}</span> por concepto
          de docencia correspondiente al mes de{' '}
          <span className="font-semibold">
            {mesCobro} {form.anio_cobro || '[Año]'}
          </span>.
        </p>

        {/* Teacher data */}
        <div className="mb-6 space-y-1">
          <p>
            <span className="font-semibold">{form.titulo || '[Título]'}</span>&nbsp;&nbsp;
            {teacherName}
          </p>
          <p>Matrícula Profesional: {form.matricula || '[Matrícula]'}</p>
          <p>Cédula de identidad: {teacherCi}</p>
          <p>Materia(s): {materiasText}</p>
        </div>

        {/* Farewell */}
        <p className="text-justify mb-16">
          Sin otro particular no dudando de su colaboración, aprovecho la oportunidad para saludar
          a Ud. con las consideraciones más distinguidas.
        </p>

        <p className="mb-16">Atte.</p>

        {/* Signature */}
        <div className="text-center">
          <p className="border-t border-gray-400 inline-block px-8 mb-1 pt-1">
            {form.titulo || '[Título]'} {teacherName}
          </p>
          <p className="text-gray-600">C.I. {teacherCi}</p>
        </div>
      </div>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

interface FormState {
  titulo: string
  matricula: string
  mes_cobro: number
  anio_cobro: number
  periodo: string
}

export function RetentionLetterPage() {
  const { data: profile, isLoading: loadingProfile } = useMyProfile()
  const { data: schedule, isLoading: loadingSchedule } = useMySchedule()
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const currentYear = new Date().getFullYear()
  const currentMonth = new Date().getMonth() + 1

  const [form, setForm] = useState<FormState>({
    titulo: '',
    matricula: '',
    mes_cobro: currentMonth,
    anio_cobro: currentYear,
    periodo: `I/${currentYear}`,
  })

  const materias: string[] = [
    ...new Set(schedule?.designations?.map((d: { subject: string }) => d.subject) ?? []),
  ].sort()

  const isFormValid =
    form.titulo.trim() !== '' &&
    form.matricula.trim() !== '' &&
    form.mes_cobro > 0 &&
    form.anio_cobro > 0 &&
    form.periodo.trim() !== ''

  const handleGenerate = async () => {
    if (!isFormValid) return
    setIsGenerating(true)
    setError(null)
    setSuccess(false)
    try {
      const payload: RetentionLetterPayload = {
        titulo: form.titulo,
        matricula: form.matricula,
        mes_cobro: form.mes_cobro,
        anio_cobro: form.anio_cobro,
        periodo: form.periodo,
      }
      await downloadRetentionLetter(payload, profile?.full_name)
      setSuccess(true)
      setTimeout(() => setSuccess(false), 4000)
    } catch (e) {
      console.error('Error generating retention letter:', e)
      setError('No se pudo generar la carta. Intentá de nuevo.')
    } finally {
      setIsGenerating(false)
    }
  }

  const isLoading = loadingProfile || loadingSchedule

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-8 h-8 border-2 border-[#003366]/30 border-t-[#003366] rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="gradient-navy rounded-xl p-6 text-white animate-fade-in">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-white/20 flex items-center justify-center">
            <FileText size={24} className="text-white" />
          </div>
          <div>
            <h2 className="text-xl font-bold">Carta de Retención RC-IVA</h2>
            <p className="text-white/70 mt-0.5">
              Generá tu carta de solicitud de retención de impuesto
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Form card */}
        <div className="card-3d-static p-6 space-y-5">
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Datos de la carta
          </h3>

          {/* Auto-filled read-only data */}
          <div className="bg-gray-50 rounded-lg p-4 space-y-2 text-sm">
            <p>
              <span className="text-gray-500">Nombre:</span>{' '}
              <span className="font-medium">{profile?.full_name ?? '—'}</span>
            </p>
            <p>
              <span className="text-gray-500">C.I.:</span>{' '}
              <span className="font-medium">{profile?.ci ?? '—'}</span>
            </p>
            <p>
              <span className="text-gray-500">Materias:</span>{' '}
              <span className="font-medium">
                {materias.length > 0 ? materias.join(', ') : '—'}
              </span>
            </p>
          </div>

          {/* Form fields */}
          <div className="grid grid-cols-2 gap-4">
            {/* Título */}
            <div className="space-y-1.5 col-span-2">
              <Label>Título profesional *</Label>
              <Select
                value={form.titulo}
                onValueChange={(v) => setForm((f) => ({ ...f, titulo: v }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Seleccionar..." />
                </SelectTrigger>
                <SelectContent>
                  {TITULOS.map((t) => (
                    <SelectItem key={t.value} value={t.value}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Matrícula */}
            <div className="space-y-1.5 col-span-2">
              <Label>Matrícula profesional *</Label>
              <Input
                value={form.matricula}
                onChange={(e) => setForm((f) => ({ ...f, matricula: e.target.value }))}
                placeholder="Ej: MP-12345"
              />
            </div>

            {/* Mes de cobro */}
            <div className="space-y-1.5">
              <Label>Mes de cobro *</Label>
              <Select
                value={String(form.mes_cobro)}
                onValueChange={(v) => setForm((f) => ({ ...f, mes_cobro: Number(v) }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Seleccionar mes..." />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(MONTH_NAMES).map(([k, v]) => (
                    <SelectItem key={k} value={k}>
                      {v}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Año de cobro */}
            <div className="space-y-1.5">
              <Label>Año de cobro *</Label>
              <Input
                type="number"
                value={form.anio_cobro}
                onChange={(e) => setForm((f) => ({ ...f, anio_cobro: Number(e.target.value) }))}
                placeholder="2026"
                min={2020}
                max={2100}
              />
            </div>

            {/* Período académico */}
            <div className="space-y-1.5 col-span-2">
              <Label>Período académico *</Label>
              <Input
                value={form.periodo}
                onChange={(e) => setForm((f) => ({ ...f, periodo: e.target.value }))}
                placeholder="Ej: I/2026"
              />
            </div>
          </div>

          {/* Error / success messages */}
          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}
          {success && (
            <div className="rounded-lg bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-700">
              ✓ Carta generada y descargada exitosamente.
            </div>
          )}

          {/* Generate button */}
          <Button
            onClick={handleGenerate}
            disabled={isGenerating || !isFormValid}
            className="w-full gap-2 text-white"
            style={{ backgroundColor: '#003366' }}
          >
            {isGenerating ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Generando...
              </>
            ) : (
              <>
                <Download size={16} />
                Generar y Descargar PDF
              </>
            )}
          </Button>
        </div>

        {/* Preview */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Vista previa
          </h3>
          <div className="overflow-y-auto max-h-[640px] rounded-xl border border-gray-100 shadow-sm">
            <LetterPreview
              teacherName={profile?.full_name ?? ''}
              teacherCi={profile?.ci ?? ''}
              materias={materias}
              form={form}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
