import { useState } from 'react'
import {
  FileSignature,
  Download,
  CheckCircle,
  AlertCircle,
  Users,
  Search,
  FileText,
  ArchiveIcon,
  Banknote,
  Clock,
  FilePenLine,
  X,
} from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardPanel, CardTitle, CardDescription } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select, SelectItem, SelectPopup, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Sheet, SheetDescription, SheetHeader, SheetPanel, SheetPopup, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { ContractHistoryToolbar } from '@/components/contracts/ContractHistoryToolbar'
import { ContractLinesTable } from '@/components/contracts/ContractLinesTable'
import { IndividualContractCard } from '@/components/contracts/IndividualContractCard'
import { CountUp } from '@/components/shared/CountUp'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { PersonAvatar } from '@/components/shared/PersonAvatar'
import { StatCard } from '@/components/shared/StatCard'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { TeacherTypeBadge } from '@/components/shared/TeacherTypeBadge'
import { TONE_CHIP, TONE_DOT } from '@/components/shared/tones'
import { teacherTypeLabel } from '@/domain/teacherTypes'
import {
  filterHistory,
  groupByTeacher,
  historyKpis,
  historyPeriods,
  kindCounts,
  type KindFilter,
} from '@/lib/contractHistoryView'
import { cn } from '@/lib/utils'
import { useTeachers } from '@/api/hooks/useTeachers'
import { useAppSettings } from '@/api/hooks/useAppSettings'
import {
  useGenerateBatchContracts,
  useContractHistory,
  downloadContractFile,
  downloadContractDocument,
  downloadContractsZip,
  type ContractDocument,
  type ContractFileInfo,
  type BatchContractRequest,
} from '@/api/hooks/useContracts'

// ─── Constants ────────────────────────────────────────────────────────────────

const DEPARTMENTS = [
  'Pando', 'La Paz', 'Cochabamba', 'Santa Cruz',
  'Beni', 'Oruro', 'Potosí', 'Chuquisaca', 'Tarija',
]

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function getContractErrorMessage(error: unknown): string {
  const axiosError = error as { response?: { data?: { detail?: string } } }
  return axiosError.response?.data?.detail ?? 'No se pudo emitir el contrato desde la carga académica efectiva.'
}

const hoursFormatter = new Intl.NumberFormat('es-BO', { maximumFractionDigits: 1 })
const amountFormatter = new Intl.NumberFormat('es-BO', { maximumFractionDigits: 0 })

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('es-BO', { dateStyle: 'medium', timeZone: 'UTC' }).format(new Date(value))
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function ContractsPage() {
  // Config
  const [department, setDepartment] = useState('Pando')

  // Teacher selection
  const [selectMode, setSelectMode] = useState<'all' | 'select'>('all')
  const [selectedCis, setSelectedCis] = useState<Set<string>>(new Set())
  const [searchTerm, setSearchTerm] = useState('')

  // Emission panel and ledger filters
  const [sheetOpen, setSheetOpen] = useState(false)
  const [historySearch, setHistorySearch] = useState('')
  const [historyPeriod, setHistoryPeriod] = useState('all')
  const [historyKind, setHistoryKind] = useState<KindFilter>('all')

  // Results
  const [generatedContracts, setGeneratedContracts] = useState<ContractFileInfo[]>([])
  const [generationErrors, setGenerationErrors] = useState<string[]>([])
  const [downloadingZip, setDownloadingZip] = useState(false)
  const [downloadingFile, setDownloadingFile] = useState<string | null>(null)

  const { data: teachersData } = useTeachers({ page: 1, perPage: 500 })
  const { data: settings } = useAppSettings()
  // Exclude placeholder TEMP teachers — they have no real CI and should not get contracts
  const teachers = (teachersData?.items ?? []).filter((t) => !t.ci.startsWith('TEMP-'))
  const generateBatch = useGenerateBatchContracts()
  const contractHistory = useContractHistory()

  const teacherTypes = new Map((teachersData?.items ?? []).map((t) => [t.ci, t.external_permanent]))
  const history = contractHistory.data ?? []
  const kpis = historyKpis(history)
  const periods = historyPeriods(history)
  const kindTotals = kindCounts(filterHistory(history, { search: historySearch, period: historyPeriod }))
  const visibleGroups = groupByTeacher(filterHistory(history, { search: historySearch, period: historyPeriod, kind: historyKind }))
  const hasFilters = historySearch.trim() !== '' || historyPeriod !== 'all' || historyKind !== 'all'

  const clearFilters = () => {
    setHistorySearch('')
    setHistoryPeriod('all')
    setHistoryKind('all')
  }

  const filteredTeachers = teachers.filter((t) => {
    if (!searchTerm) return true
    const term = searchTerm.toLowerCase()
    return (
      t.full_name.toLowerCase().includes(term) ||
      t.ci.includes(term)
    )
  })

  const toggleTeacher = (ci: string) => {
    setSelectedCis((prev) => {
      const next = new Set(prev)
      if (next.has(ci)) next.delete(ci)
      else next.add(ci)
      return next
    })
  }

  const isConfigValid = department.trim() !== ''

  const canGenerate =
    isConfigValid &&
    (selectMode === 'all' || selectedCis.size > 0)

  const handleGenerate = () => {
    setGeneratedContracts([])
    setGenerationErrors([])
    const payload: BatchContractRequest = {
      department,
      teacher_cis: selectMode === 'select' ? [...selectedCis] : null,
    }
    generateBatch.mutate(payload, {
      onSuccess: (data) => {
        setGeneratedContracts(data.contracts)
        setGenerationErrors(data.errors ?? [])
      },
    })
  }

  const handleDownloadAll = async () => {
    if (generatedContracts.length === 0) return
    setDownloadingZip(true)
    try {
      await downloadContractsZip(generatedContracts.map((c) => c.filename))
    } finally {
      setDownloadingZip(false)
    }
  }

  const handleDownloadOne = async (contract: ContractFileInfo) => {
    setDownloadingFile(contract.public_id ?? contract.filename)
    try {
      await downloadContractFile(contract)
    } finally {
      setDownloadingFile(null)
    }
  }

  const handleHistoryDownload = async (document: ContractDocument) => {
    setDownloadingFile(document.public_id)
    try {
      await downloadContractDocument(document)
    } finally {
      setDownloadingFile(null)
    }
  }

  const dismissResults = () => {
    setGeneratedContracts([])
    setGenerationErrors([])
    generateBatch.reset()
  }

  // The same outcome block lives in the panel while it is open and on the page once it closes,
  // so the download links survive closing the panel.
  const renderEmissionResults = (onDismiss?: () => void) => (
    <>
      {/* Error state */}
      {generateBatch.isError && (
        <Alert variant="error" role="alert">
          <AlertCircle aria-hidden="true" />
          <AlertDescription>{getContractErrorMessage(generateBatch.error)}</AlertDescription>
        </Alert>
      )}

      {generationErrors.length > 0 && (
        <Alert variant="warning" role="status" aria-live="polite">
          <AlertCircle aria-hidden="true" />
          <AlertTitle>Algunos docentes se omitieron:</AlertTitle>
          <AlertDescription>
            <ul className="list-disc space-y-1 pl-5 text-xs">
              {generationErrors.map((error) => (
                <li key={error}>{error}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {/* Results card */}
      {generatedContracts.length > 0 && (
        <Card role="status" aria-live="polite">
          <CardHeader className="border-b">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <CheckCircle size={20} className="text-success" aria-hidden="true" />
                <div>
                  <CardTitle className="text-base text-success-foreground">
                    {generatedContracts.length} contrato{generatedContracts.length !== 1 ? 's' : ''} emitido{generatedContracts.length !== 1 ? 's' : ''} o recuperado{generatedContracts.length !== 1 ? 's' : ''}
                  </CardTitle>
                  <CardDescription>Listos para descargar</CardDescription>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="outline" onClick={() => void handleDownloadAll()} loading={downloadingZip}>
                  <ArchiveIcon aria-hidden="true" />
                  Descargar Todos (.zip)
                </Button>
                {onDismiss && (
                  <Button variant="ghost" size="icon" aria-label="Cerrar resultados de emisión" onClick={onDismiss}>
                    <X aria-hidden="true" />
                  </Button>
                )}
              </div>
            </div>
          </CardHeader>
          <div className="max-h-96 divide-y overflow-y-auto">
            {generatedContracts.map((contract) => (
              <div key={contract.filename} className="flex items-center justify-between gap-3 px-6 py-3 hover:bg-accent/50">
                <div className="flex min-w-0 items-center gap-3">
                  <FileText size={16} className="shrink-0 text-primary" aria-hidden="true" />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">{contract.teacher_name}</p>
                    <p className="text-xs text-muted-foreground tabular-nums">
                      CI: {contract.teacher_ci} · {formatBytes(contract.file_size)}
                    </p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-primary"
                  onClick={() => void handleDownloadOne(contract)}
                  loading={downloadingFile === (contract.public_id ?? contract.filename)}
                >
                  <Download aria-hidden="true" />
                  PDF
                </Button>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Empty state after successful generation with 0 results */}
      {generateBatch.isSuccess && generatedContracts.length === 0 && (
        <Card>
          <EmptyState illustration="empty-document"
            icon={FileSignature}
            title="No se emitieron contratos."
            description="Revisá que los docentes tengan carga efectiva y tarifas completas."
          />
        </Card>
      )}
    </>
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Contratos Docentes"
        description="Emití y consultá contratos consolidados y sus enmiendas inmutables"
        actions={
          <Button onClick={() => setSheetOpen(true)}>
            <FileSignature aria-hidden="true" />
            Emitir contratos
          </Button>
        }
      />

      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetPopup className="sm:max-w-2xl">
          <SheetHeader>
            <SheetTitle>Emitir contratos</SheetTitle>
            <SheetDescription>Emití un contrato individual o por lote. Cada emisión queda en el historial inmutable.</SheetDescription>
          </SheetHeader>
          <SheetPanel className="space-y-6">
            {/* Config card */}
            <Card>
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className={cn('flex size-9 items-center justify-center rounded-xl', TONE_CHIP.primary)}>
                    <FileSignature size={16} aria-hidden="true" />
                  </div>
                  <div>
                    <CardTitle className="text-base">Configuración de Emisión</CardTitle>
                    <CardDescription>Parámetros que se aplicarán a todos los contratos generados</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardPanel>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  {/* Department */}
                  <Field>
                    <FieldLabel htmlFor="contract-department">Departamento</FieldLabel>
                    <Select
                      value={department}
                      items={DEPARTMENTS.map((d) => ({ value: d, label: d }))}
                      onValueChange={(value) => setDepartment(value ?? department)}
                    >
                      <SelectTrigger id="contract-department">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectPopup>
                        {DEPARTMENTS.map((d) => (
                          <SelectItem key={d} value={d}>{d}</SelectItem>
                        ))}
                      </SelectPopup>
                    </Select>
                  </Field>

                  <Alert variant="info" className="md:col-span-2">
                    <AlertDescription>
                      La carga y vigencia se toman del horario publicado o de la fuente legacy efectiva, sin modificar designaciones históricas. Tarifas: prácticas Bs {settings?.practice_hourly_rate ?? '—'}; teoría Bs {settings?.hourly_rate ?? '—'}.
                    </AlertDescription>
                  </Alert>
                </div>
              </CardPanel>
            </Card>

            <IndividualContractCard
              teachers={teachers}
              department={department}
              academicPeriod={settings?.active_academic_period}
            />

            {/* Teacher selection card */}
            <Card>
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className={cn('flex size-9 items-center justify-center rounded-xl', TONE_CHIP.primary)}>
                    <Users size={16} aria-hidden="true" />
                  </div>
                  <div>
                    <CardTitle className="text-base">Selección de Docentes</CardTitle>
                    <CardDescription>Elegí para quiénes generar contratos</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardPanel className="space-y-4">
                {/* Toggle all/select */}
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant={selectMode === 'all' ? 'default' : 'outline'}
                    aria-pressed={selectMode === 'all'}
                    onClick={() => setSelectMode('all')}
                  >
                    Todos los docentes
                  </Button>
                  <Button
                    type="button"
                    variant={selectMode === 'select' ? 'default' : 'outline'}
                    aria-pressed={selectMode === 'select'}
                    onClick={() => setSelectMode('select')}
                  >
                    Seleccionar docentes
                  </Button>
                </div>

                {selectMode === 'select' && (
                  <>
                    {/* Search */}
                    <div className="relative max-w-sm">
                      <Search size={16} aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 z-10 -translate-y-1/2 text-muted-foreground" />
                      <Input
                        type="search"
                        aria-label="Buscar docentes"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        placeholder="Buscar por nombre o CI..."
                        inputClassName="pl-9"
                      />
                    </div>

                    {/* Counter */}
                    {selectedCis.size > 0 && (
                      <p className="text-sm font-medium text-primary">
                        {selectedCis.size} docente{selectedCis.size !== 1 ? 's' : ''} seleccionado{selectedCis.size !== 1 ? 's' : ''}
                      </p>
                    )}

                    {/* Teacher list */}
                    <div className="max-h-72 divide-y overflow-y-auto rounded-lg border">
                      {filteredTeachers.length === 0 ? (
                        <p className="py-6 text-center text-sm text-muted-foreground">No se encontraron docentes</p>
                      ) : (
                        filteredTeachers.map((teacher) => (
                          <label
                            key={teacher.ci}
                            className="flex cursor-pointer items-center gap-3 px-4 py-2.5 hover:bg-accent/50"
                          >
                            <Checkbox
                              checked={selectedCis.has(teacher.ci)}
                              onCheckedChange={() => toggleTeacher(teacher.ci)}
                            />
                            <PersonAvatar name={teacher.full_name} colorKey={teacher.ci} size="sm" />
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-sm font-medium text-foreground">{teacher.full_name}</p>
                              <p className="text-xs text-muted-foreground">CI: {teacher.ci}</p>
                            </div>
                            {selectedCis.has(teacher.ci) && (
                              <CheckCircle size={16} className="shrink-0 text-success" aria-hidden="true" />
                            )}
                          </label>
                        ))
                      )}
                    </div>
                  </>
                )}

                {selectMode === 'all' && (
                  <p className="text-sm text-muted-foreground">
                    Se generarán contratos para <span className="font-medium text-foreground">{teachers.length}</span> docentes con designaciones.
                  </p>
                )}
              </CardPanel>
            </Card>

            {/* Generate button */}
            <div className="flex flex-wrap items-center gap-4">
              <Button onClick={handleGenerate} disabled={!canGenerate} loading={generateBatch.isPending}>
                {generateBatch.isPending ? (
                  'Emitiendo contratos...'
                ) : (
                  <>
                    <FileSignature aria-hidden="true" />
                    Emitir o Recuperar Contratos
                  </>
                )}
              </Button>
              {!canGenerate && !generateBatch.isPending && (
                <p className="text-xs text-muted-foreground">
                  {!isConfigValid
                    ? 'Completá el departamento'
                    : 'Seleccioná al menos un docente'}
                </p>
              )}
            </div>

            {renderEmissionResults()}
          </SheetPanel>
        </SheetPopup>
      </Sheet>

      {/* Outcome of the last batch, kept on the page once the panel is closed */}
      {!sheetOpen && <div className="space-y-4">{renderEmissionResults(dismissResults)}</div>}

      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3">
        <StatCard
          icon={FileText}
          tone="primary"
          title="Documentos emitidos"
          value={contractHistory.isSuccess ? <CountUp value={kpis.documents} /> : '—'}
          hint="Originales y enmiendas del historial"
        />
        <StatCard
          icon={FileSignature}
          tone="success"
          title="Originales"
          value={contractHistory.isSuccess ? <CountUp value={kpis.originals} /> : '—'}
          hint="Primer contrato de cada docente y período"
        />
        <StatCard
          icon={FilePenLine}
          tone="info"
          title="Enmiendas"
          value={contractHistory.isSuccess ? <CountUp value={kpis.amendments} /> : '—'}
          hint="Cambios posteriores a un original"
        />
        <StatCard
          icon={Users}
          tone="violet"
          title="Docentes con contrato"
          value={contractHistory.isSuccess ? <CountUp value={kpis.teachers} /> : '—'}
          hint="Docentes con al menos un documento"
        />
        <StatCard
          icon={Clock}
          tone="cyan"
          title="Horas vigentes"
          value={contractHistory.isSuccess ? <CountUp value={kpis.hours} format={(n) => hoursFormatter.format(n)} /> : '—'}
          hint="Carga vigente de cada docente: último original más sus enmiendas"
        />
        <StatCard
          icon={Banknote}
          tone="warning"
          title="Monto estimado"
          value={contractHistory.isSuccess ? <CountUp value={kpis.amount} format={(n) => `Bs ${amountFormatter.format(n)}`} /> : '—'}
          hint="Horas × tarifa de la carga vigente de cada docente"
        />
      </div>

      <section aria-labelledby="contract-history-heading" className="space-y-4">
        <div className="space-y-1">
          <h3 id="contract-history-heading" className="text-base font-semibold text-foreground">
            Historial Inmutable
          </h3>
          <p className="text-sm text-muted-foreground">Originales y enmiendas ordenados por docente y versión.</p>
        </div>

        <ContractHistoryToolbar
          search={historySearch}
          onSearchChange={setHistorySearch}
          period={historyPeriod}
          periods={periods}
          onPeriodChange={setHistoryPeriod}
          kind={historyKind}
          counts={kindTotals}
          onKindChange={setHistoryKind}
        />

        {contractHistory.isLoading && (
          <div role="status" aria-live="polite" aria-busy="true" className="space-y-3">
            <span className="sr-only">Cargando historial de contratos…</span>
            <Skeleton className="h-32 w-full rounded-xl" />
            <Skeleton className="h-32 w-full rounded-xl" />
          </div>
        )}
        {contractHistory.isError && (
          <Alert variant="error">
            <AlertCircle aria-hidden="true" />
            <AlertDescription>No se pudo cargar el historial de contratos.</AlertDescription>
          </Alert>
        )}
        {contractHistory.isSuccess && history.length === 0 && (
          <Card>
            <EmptyState illustration="empty-document" icon={FileText} title="Todavía no se emitieron contratos inmutables." />
          </Card>
        )}
        {contractHistory.isSuccess && history.length > 0 && visibleGroups.length === 0 && (
          <Card>
            <EmptyState
              illustration="empty-search"
              icon={Search}
              title="Ningún documento coincide con los filtros."
              action={hasFilters ? <Button variant="outline" onClick={clearFilters}>Limpiar filtros</Button> : undefined}
            />
          </Card>
        )}
        {visibleGroups.length > 0 && (
          <ul className="space-y-4">
            {visibleGroups.map((group) => {
              const teacherType = teacherTypes.get(group.teacher_ci)
              return (
                <li key={group.teacher_ci}>
                  <Card>
                    <CardHeader className="border-b">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="flex min-w-0 items-center gap-3">
                          <PersonAvatar name={group.teacher_name} colorKey={group.teacher_ci} />
                          <div className="min-w-0">
                            <h4 className="truncate text-sm font-semibold text-foreground">{group.teacher_name}</h4>
                            <p className="text-xs text-muted-foreground tabular-nums">CI: {group.teacher_ci}</p>
                          </div>
                          {teacherType && <TeacherTypeBadge type={teacherType} label={teacherTypeLabel(teacherType)} />}
                        </div>
                        <StatusBadge tone="primary">
                          {group.documents.length} {group.documents.length === 1 ? 'versión' : 'versiones'}
                        </StatusBadge>
                      </div>
                    </CardHeader>
                    <CardPanel>
                      <ol>
                        {group.documents.map((document, index) => {
                          const isOriginal = document.document_kind === 'original'
                          const tone = isOriginal ? 'success' : 'info'
                          const label = isOriginal ? 'contrato original' : `enmienda ${document.amendment_sequence}`
                          return (
                            <li key={document.public_id} className={cn('relative pl-7', index < group.documents.length - 1 && 'pb-6')}>
                              {index < group.documents.length - 1 && (
                                <span aria-hidden="true" className="absolute top-4 bottom-0 left-[5px] w-px bg-border" />
                              )}
                              <span aria-hidden="true" className={cn('absolute top-1.5 left-0 size-3 rounded-full ring-4 ring-card', TONE_DOT[tone])} />
                              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <div className="flex flex-wrap items-center gap-2">
                                    <StatusBadge tone={tone}>
                                      {isOriginal ? 'Original' : `Enmienda ${document.amendment_sequence}`}
                                    </StatusBadge>
                                    <span className="text-sm font-medium text-foreground">{document.academic_period}</span>
                                  </div>
                                  <p className="mt-1 text-xs text-muted-foreground">
                                    Efectiva {formatDate(document.effective_date)} · emitida {formatDate(document.issued_at)}
                                  </p>
                                </div>
                                <Button
                                  type="button"
                                  variant="outline"
                                  className="self-start"
                                  onClick={() => void handleHistoryDownload(document)}
                                  loading={downloadingFile === document.public_id}
                                  aria-label={`Descargar ${label} de ${document.teacher_name}`}
                                >
                                  <Download aria-hidden="true" />
                                  Descargar PDF
                                </Button>
                              </div>
                              <div className="mt-3">
                                <ContractLinesTable lines={document.lines} documentLabel={`${label} de ${document.teacher_name}`} />
                              </div>
                            </li>
                          )
                        })}
                      </ol>
                    </CardPanel>
                  </Card>
                </li>
              )
            })}
          </ul>
        )}
      </section>
    </div>
  )
}
