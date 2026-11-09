import { useEffect, useState } from 'react'
import { AlertCircle, CalendarDays, CheckCircle, ChevronsUpDown, Download, FileSignature, RotateCcw, X } from 'lucide-react'

import { TONE_CHIP } from '@/components/shared/tones'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardHeader, CardPanel, CardTitle } from '@/components/ui/card'
import { Field, FieldDescription, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import {
  Combobox,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
  ComboboxPopup,
  ComboboxTrigger,
} from '@/components/ui/combobox'
import { Skeleton } from '@/components/ui/skeleton'
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
import { matchesTeacher, teacherOptionLabel } from '@/lib/contractTeacherPicker'
import { cn } from '@/lib/utils'

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
  const [pickerOpen, setPickerOpen] = useState(false)
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

  const selectedTeacher = teachers.find((t) => t.ci === teacherCi) ?? null
  const defaults = terms.data
  const defaultStart = defaults?.default_start ? formatSpanishDate(defaults.default_start) : 'sin carga'
  const defaultEnd = defaults?.default_end ? formatSpanishDate(defaults.default_end) : 'sin carga'
  const hasCustom = Boolean(form.start || form.end || form.signature)

  return (
    <Card render={<section aria-labelledby="individual-contract-heading" />}>
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className={cn('flex size-9 items-center justify-center rounded-xl', TONE_CHIP.primary)}>
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
          <FieldLabel id="individual-contract-teacher-label" htmlFor="individual-contract-teacher">Docente</FieldLabel>
          <div className="flex w-full items-center gap-1">
            <Combobox
              items={teachers}
              open={pickerOpen}
              onOpenChange={setPickerOpen}
              value={selectedTeacher}
              onValueChange={(teacher) => {
                if (!teacher) return
                selectTeacher(teacher.ci)
                setPickerOpen(false)
              }}
              filter={matchesTeacher}
              itemToStringLabel={teacherOptionLabel}
              isItemEqualToValue={(item, other) => item.ci === other.ci}
            >
              <ComboboxTrigger
                render={
                  <Button
                    id="individual-contract-teacher"
                    aria-labelledby="individual-contract-teacher-label individual-contract-teacher"
                    type="button"
                    variant="outline"
                    className={cn('min-w-0 flex-1 justify-between font-normal', !selectedTeacher && 'text-muted-foreground')}
                  />
                }
              >
                <span className="truncate">{selectedTeacher ? teacherOptionLabel(selectedTeacher) : 'Elegí un docente'}</span>
                <ChevronsUpDown className="opacity-50" aria-hidden="true" />
              </ComboboxTrigger>
              <ComboboxPopup className="w-(--anchor-width) min-w-72">
                <div className="border-b p-2">
                  <ComboboxInput aria-label="Buscar docente" placeholder="Buscar por nombre o CI…" maxLength={60} showTrigger={false} />
                </div>
                <ComboboxEmpty>Ningún docente coincide con la búsqueda.</ComboboxEmpty>
                <ComboboxList>
                  {(teacher: (typeof teachers)[number]) => (
                    <ComboboxItem key={teacher.ci} value={teacher}>
                      <span className="flex items-center gap-2">
                        <span className="truncate">{teacher.full_name}</span>
                        <span className="ml-auto shrink-0 whitespace-nowrap text-xs text-muted-foreground">CI {teacher.ci}</span>
                      </span>
                    </ComboboxItem>
                  )}
                </ComboboxList>
              </ComboboxPopup>
            </Combobox>
            {teacherCi && (
              <Button type="button" size="icon" variant="ghost" aria-label="Quitar docente" onClick={() => selectTeacher(null)}>
                <X aria-hidden="true" />
              </Button>
            )}
          </div>
        </Field>

        <div aria-live="polite" className="empty:hidden">
          {teacherCi && terms.isLoading && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">Calculando la carga del docente…</p>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-3" aria-hidden="true">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="space-y-2">
                    <Skeleton className="h-4 w-28" />
                    <Skeleton className="h-9 w-full rounded-lg" />
                    <Skeleton className="h-3 w-40" />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

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
