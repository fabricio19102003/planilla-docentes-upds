import { useEffect, useState } from 'react'
import { AlertCircle, CalendarDays, CheckCircle, Download, FileSignature, RotateCcw } from 'lucide-react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardHeader, CardPanel, CardTitle } from '@/components/ui/card'
import { Field, FieldDescription, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select, SelectItem, SelectPopup, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  downloadContractDocument,
  useContractTerms,
  useIssueContract,
  type ContractDocument,
} from '@/api/hooks/useContracts'
import {
  buildIssuePayload,
  formatSpanishDate,
  toTermsForm,
  validateTermsForm,
  type ContractTermsForm,
} from '@/lib/contractTermsForm'

const EMPTY_FORM: ContractTermsForm = { start: '', end: '', signature: '' }

function errorDetail(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  return typeof detail === 'string' ? detail : 'No se pudo emitir el contrato.'
}

interface Props {
  teachers: { ci: string; full_name: string }[]
  department: string
  academicPeriod: string | undefined
}

/** Issue one teacher's contract with custom start, end and signing dates. */
export function IndividualContractCard({ teachers, department, academicPeriod }: Props) {
  const [teacherCi, setTeacherCi] = useState<string | null>(null)
  const [form, setForm] = useState<ContractTermsForm>(EMPTY_FORM)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [issued, setIssued] = useState<ContractDocument | null>(null)
  const [downloading, setDownloading] = useState(false)
  const terms = useContractTerms(teacherCi, academicPeriod)
  const issue = useIssueContract()

  useEffect(() => {
    setForm(terms.data ? toTermsForm(terms.data) : EMPTY_FORM)
  }, [terms.data])

  const selectTeacher = (ci: string | null) => {
    setTeacherCi(ci)
    setIssued(null)
    setValidationError(null)
    issue.reset()
  }

  const submit = (nextForm: ContractTermsForm) => {
    if (!teacherCi || !terms.data || !academicPeriod) return
    setIssued(null)
    const error = validateTermsForm(nextForm, terms.data)
    setValidationError(error)
    if (error) return
    issue.mutate(
      { teacherCi, payload: buildIssuePayload(nextForm, department, academicPeriod) },
      { onSuccess: (document) => setIssued(document) },
    )
  }

  const download = async (document: ContractDocument) => {
    setDownloading(true)
    try {
      await downloadContractDocument(document)
    } finally {
      setDownloading(false)
    }
  }

  const defaults = terms.data
  const defaultStart = defaults?.default_start ? formatSpanishDate(defaults.default_start) : 'sin carga'
  const defaultEnd = defaults?.default_end ? formatSpanishDate(defaults.default_end) : 'sin carga'
  const hasCustom = Boolean(form.start || form.end || form.signature)

  return (
    <Card render={<section aria-labelledby="individual-contract-heading" />}>
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <CalendarDays size={16} aria-hidden="true" />
          </div>
          <div>
            <CardTitle id="individual-contract-heading" className="text-base">Contrato Individual con Fechas</CardTitle>
            <CardDescription>
              Emití el contrato de un docente eligiendo inicio, fin y fecha de firma. Los campos vacíos usan las
              fechas de sus designaciones. La emisión en lote siempre usa las designaciones.
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardPanel className="space-y-4">
        <Field>
          <FieldLabel htmlFor="individual-contract-teacher">Docente</FieldLabel>
          <Select
            value={teacherCi}
            items={teachers.map((t) => ({ value: t.ci, label: `${t.full_name} — CI ${t.ci}` }))}
            onValueChange={(value) => selectTeacher(value)}
          >
            <SelectTrigger id="individual-contract-teacher">
              <SelectValue placeholder="Elegí un docente" />
            </SelectTrigger>
            <SelectPopup>
              {teachers.map((t) => (
                <SelectItem key={t.ci} value={t.ci}>{t.full_name} — CI {t.ci}</SelectItem>
              ))}
            </SelectPopup>
          </Select>
        </Field>

        {teacherCi && terms.isError && (
          <Alert variant="error" role="alert">
            <AlertCircle aria-hidden="true" />
            <AlertDescription>{errorDetail(terms.error)}</AlertDescription>
          </Alert>
        )}

        {teacherCi && defaults && (
          <>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <Field>
                <FieldLabel htmlFor="contract-start">Fecha de inicio</FieldLabel>
                <Input
                  id="contract-start"
                  type="date"
                  min={defaults.period_start}
                  max={defaults.period_end}
                  value={form.start}
                  onChange={(e) => setForm({ ...form, start: e.target.value })}
                />
                <FieldDescription>Vacío: {defaultStart}.</FieldDescription>
              </Field>
              <Field>
                <FieldLabel htmlFor="contract-end">Fecha de fin</FieldLabel>
                <Input
                  id="contract-end"
                  type="date"
                  min={defaults.period_start}
                  max={defaults.period_end}
                  value={form.end}
                  onChange={(e) => setForm({ ...form, end: e.target.value })}
                />
                <FieldDescription>Vacío: {defaultEnd}.</FieldDescription>
              </Field>
              <Field>
                <FieldLabel htmlFor="contract-signature">Fecha de firma</FieldLabel>
                <Input
                  id="contract-signature"
                  type="date"
                  value={form.signature}
                  onChange={(e) => setForm({ ...form, signature: e.target.value })}
                />
                <FieldDescription>Vacío: la fecha de inicio del contrato.</FieldDescription>
              </Field>
            </div>

            <p className="text-xs text-muted-foreground">
              Si las fechas o la fecha de firma cambian respecto del último contrato, se agrega un contrato nuevo
              completo al historial y el anterior queda sin cambios. Las fechas elegidas siguen vigentes para este
              docente hasta que las restablezcas.
            </p>

            {(validationError || issue.isError) && (
              <Alert variant={validationError ? 'warning' : 'error'} role="alert">
                <AlertCircle aria-hidden="true" />
                <AlertDescription>{validationError ?? errorDetail(issue.error)}</AlertDescription>
              </Alert>
            )}

            <div className="flex flex-wrap gap-2">
              <Button onClick={() => submit(form)} loading={issue.isPending}>
                <FileSignature aria-hidden="true" />
                Emitir contrato
              </Button>
              <Button
                variant="outline"
                disabled={!hasCustom || issue.isPending}
                onClick={() => {
                  setForm(EMPTY_FORM)
                  submit(EMPTY_FORM)
                }}
              >
                <RotateCcw aria-hidden="true" />
                Usar fechas de designaciones
              </Button>
            </div>

            {issued && (
              <Alert variant="success" role="status">
                <CheckCircle aria-hidden="true" />
                <AlertDescription className="flex flex-wrap items-center gap-3">
                  <span>
                    {issued.teacher_name}: {issued.document_kind === 'original' ? 'contrato original' : `versión ${issued.version}`} listo.
                  </span>
                  <Button variant="outline" size="sm" loading={downloading} onClick={() => void download(issued)}>
                    <Download aria-hidden="true" />
                    PDF
                  </Button>
                </AlertDescription>
              </Alert>
            )}
          </>
        )}
      </CardPanel>
    </Card>
  )
}
