import { useState } from 'react'
import { useMyProfile, useMySchedule, downloadRetentionLetter } from '@/api/hooks/useAuth'
import type { RetentionLetterPayload } from '@/api/hooks/useAuth'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectItem,
  SelectPopup,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { PageHeader } from '@/components/shared/PageHeader'
import { AlertCircle, CheckCircle2, FileText, Download, Info, Loader2 } from 'lucide-react'

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

// The letter is a sheet of paper: it keeps its serif body, its A4-like width and its own spacing so it
// reads and prints the same as the generated PDF. Only the colors come from theme tokens.
function LetterPreview({ teacherName, teacherCi, materias, form }: PreviewProps) {
  const today = new Date()
  const dia = today.getDate()
  const mesHoy = MONTH_NAMES[today.getMonth() + 1] ?? ''
  const anioHoy = today.getFullYear()
  const mesCobro = MONTH_NAMES[form.mes_cobro] ?? '—'
  const materiasText = materias.length > 0 ? materias.join(', ') : '—'

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center gap-2 border-b bg-muted/40 px-4 py-3">
        <FileText size={14} className="text-muted-foreground" aria-hidden="true" />
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Vista previa de la carta
        </span>
      </div>

      {/* A4-style letter area */}
      <div className="mx-auto max-w-[680px] p-8 font-serif text-[13px] leading-relaxed text-foreground">
        {/* Logo placeholder */}
        <div className="mb-6 flex justify-center">
          <div className="flex size-10 items-center justify-center rounded-full bg-primary/10">
            <span className="text-sm font-semibold text-primary">S</span>
          </div>
        </div>

        {/* Date */}
        <p className="mb-10 text-right">
          Cobija, {dia} de {mesHoy} de {anioHoy}
        </p>

        {/* Addressee */}
        <p className="mb-1">Lic. Luis Michel Bravo Alencar</p>
        <p className="mb-1 font-bold">
          RECTOR DE LA UNIVERSIDAD PRIVADA DOMINGO SAVIO – UNIPANDO S.R.L.
        </p>
        <p className="mb-10 font-bold">PRESENTE.-</p>

        {/* Reference */}
        <p className="mb-8 text-right font-bold underline">
          Ref.- SOLICITUD DE RETENCIÓN DE IMPUESTO RC-IVA 13%
        </p>

        {/* Greeting */}
        <p className="mb-4">De mi consideración:</p>

        {/* Body */}
        <p className="mb-6 text-justify">
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
        <p className="mb-16 text-justify">
          Sin otro particular no dudando de su colaboración, aprovecho la oportunidad para saludar
          a Ud. con las consideraciones más distinguidas.
        </p>

        <p className="mb-16">Atte.</p>

        {/* Signature */}
        <div className="text-center">
          <p className="mb-1 inline-block border-t border-foreground/40 px-8 pt-1">
            {form.titulo || '[Título]'} {teacherName}
          </p>
          <p className="text-muted-foreground">C.I. {teacherCi}</p>
        </div>
      </div>
    </Card>
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

  const noRetention = profile?.has_retention === false

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
    if (!isFormValid || noRetention) return
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

  const header = (
    <PageHeader
      title="Carta de Retención RC-IVA"
      description="Generá tu carta de solicitud de retención de impuesto"
    />
  )

  if (isLoading) {
    return (
      <div className="max-w-4xl">
        {header}
        <div role="status" aria-busy="true" className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <span className="sr-only">Cargando datos de la carta</span>
          <Skeleton className="h-96 rounded-2xl" />
          <Skeleton className="h-96 rounded-2xl" />
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl space-y-4 sm:space-y-6">
      {header}

      {noRetention && (
        <Alert variant="info" role="status">
          <Info aria-hidden="true" />
          <AlertDescription className="text-info-foreground">
            Vos emitís factura: no necesitás carta de retención.
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Form card */}
        <Card>
          <fieldset disabled={noRetention} className="min-w-0 space-y-5 p-4 disabled:opacity-60 sm:p-6">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-foreground">
              Datos de la carta
            </h3>

            {/* Auto-filled read-only data */}
            <div className="space-y-2 rounded-lg bg-muted/50 p-4 text-sm">
              <p>
                <span className="text-muted-foreground">Nombre:</span>{' '}
                <span className="font-medium">{profile?.full_name ?? '—'}</span>
              </p>
              <p>
                <span className="text-muted-foreground">C.I.:</span>{' '}
                <span className="font-medium tabular-nums">{profile?.ci ?? '—'}</span>
              </p>
              <p>
                <span className="text-muted-foreground">Materias:</span>{' '}
                <span className="font-medium">
                  {materias.length > 0 ? materias.join(', ') : '—'}
                </span>
              </p>
            </div>

            {/* Form fields */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {/* Título */}
              <Field className="sm:col-span-2">
                <FieldLabel htmlFor="retention-title">Título profesional *</FieldLabel>
                <Select
                  value={form.titulo || null}
                  items={TITULOS}
                  onValueChange={(v) => setForm((f) => ({ ...f, titulo: v ?? '' }))}
                >
                  <SelectTrigger
                    id="retention-title"
                    aria-invalid={Boolean(error)}
                    aria-describedby={error ? 'retention-form-error' : undefined}
                  >
                    <SelectValue placeholder="Seleccionar..." />
                  </SelectTrigger>
                  <SelectPopup>
                    {TITULOS.map((t) => (
                      <SelectItem key={t.value} value={t.value}>
                        {t.label}
                      </SelectItem>
                    ))}
                  </SelectPopup>
                </Select>
              </Field>

              {/* Matrícula */}
              <Field className="sm:col-span-2">
                <FieldLabel htmlFor="retention-registration">Matrícula profesional *</FieldLabel>
                <Input
                  id="retention-registration"
                  value={form.matricula}
                  onChange={(e) => setForm((f) => ({ ...f, matricula: e.target.value }))}
                  placeholder="Ej: MP-12345"
                  aria-invalid={Boolean(error)}
                  aria-describedby={error ? 'retention-form-error' : undefined}
                />
              </Field>

              {/* Mes de cobro */}
              <Field>
                <FieldLabel htmlFor="retention-month">Mes de cobro *</FieldLabel>
                <Select
                  value={String(form.mes_cobro)}
                  items={MONTH_NAMES}
                  onValueChange={(v) => setForm((f) => ({ ...f, mes_cobro: v ? Number(v) : f.mes_cobro }))}
                >
                  <SelectTrigger
                    id="retention-month"
                    aria-invalid={Boolean(error)}
                    aria-describedby={error ? 'retention-form-error' : undefined}
                  >
                    <SelectValue placeholder="Seleccionar mes..." />
                  </SelectTrigger>
                  <SelectPopup>
                    {Object.entries(MONTH_NAMES).map(([k, v]) => (
                      <SelectItem key={k} value={k}>
                        {v}
                      </SelectItem>
                    ))}
                  </SelectPopup>
                </Select>
              </Field>

              {/* Año de cobro */}
              <Field>
                <FieldLabel htmlFor="retention-year">Año de cobro *</FieldLabel>
                <Input
                  id="retention-year"
                  type="number"
                  value={form.anio_cobro}
                  onChange={(e) => setForm((f) => ({ ...f, anio_cobro: Number(e.target.value) }))}
                  placeholder="2026"
                  min={2020}
                  max={2100}
                  inputClassName="tabular-nums"
                  aria-invalid={Boolean(error)}
                  aria-describedby={error ? 'retention-form-error' : undefined}
                />
              </Field>

              {/* Período académico */}
              <Field className="sm:col-span-2">
                <FieldLabel htmlFor="retention-period">Período académico *</FieldLabel>
                <Input
                  id="retention-period"
                  value={form.periodo}
                  onChange={(e) => setForm((f) => ({ ...f, periodo: e.target.value }))}
                  placeholder="Ej: I/2026"
                  aria-invalid={Boolean(error)}
                  aria-describedby={error ? 'retention-form-error' : undefined}
                />
              </Field>
            </div>

            {/* Error / success messages */}
            {error && (
              <Alert id="retention-form-error" variant="error">
                <AlertCircle aria-hidden="true" />
                <AlertDescription className="text-destructive-foreground">{error}</AlertDescription>
              </Alert>
            )}
            {success && (
              <Alert variant="success" role="status" aria-live="polite">
                <CheckCircle2 aria-hidden="true" />
                <AlertDescription className="text-success-foreground">
                  ✓ Carta generada y descargada exitosamente.
                </AlertDescription>
              </Alert>
            )}

            {/* Generate button */}
            <div className="space-y-2">
              <Button
                type="button"
                onClick={handleGenerate}
                disabled={isGenerating || !isFormValid || noRetention}
                aria-describedby={!isFormValid && !noRetention ? 'retention-generate-hint' : undefined}
                className="w-full gap-2"
              >
                {isGenerating ? (
                  <>
                    <Loader2 size={16} className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
                    Generando...
                  </>
                ) : (
                  <>
                    <Download size={16} aria-hidden="true" />
                    Generar y Descargar PDF
                  </>
                )}
              </Button>
              {!isFormValid && !noRetention && (
                <p id="retention-generate-hint" className="text-xs text-muted-foreground">
                  Completá los campos marcados con * para generar la carta.
                </p>
              )}
            </div>
          </fieldset>
        </Card>

        {/* Preview */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-foreground">
            Vista previa
          </h3>
          <div className="max-h-[640px] overflow-y-auto rounded-2xl">
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
