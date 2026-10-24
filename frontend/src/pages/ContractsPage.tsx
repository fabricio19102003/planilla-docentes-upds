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
} from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardPanel, CardTitle, CardDescription } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select, SelectItem, SelectPopup, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatusBadge } from '@/components/shared/StatusBadge'
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

  return (
    <div className="space-y-6">
      <PageHeader
        title="Contratos Docentes"
        description="Emití y consultá contratos consolidados y sus enmiendas inmutables"
      />

      {/* Config card */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <FileSignature size={16} aria-hidden="true" />
            </div>
            <div>
              <CardTitle className="text-base">Configuración de Emisión</CardTitle>
              <CardDescription>Parámetros que se aplicarán a todos los contratos generados</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardPanel>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
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

            <Alert variant="info" className="lg:col-span-3">
              <AlertDescription>
                La carga y vigencia se toman del horario publicado o de la fuente legacy efectiva, sin modificar designaciones históricas. Tarifas: prácticas Bs {settings?.practice_hourly_rate ?? '—'}; teoría Bs {settings?.hourly_rate ?? '—'}.
              </AlertDescription>
            </Alert>
          </div>
        </CardPanel>
      </Card>

      {/* Teacher selection card */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
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
              <Button variant="outline" onClick={() => void handleDownloadAll()} loading={downloadingZip}>
                <ArchiveIcon aria-hidden="true" />
                Descargar Todos (.zip)
              </Button>
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

      <Card render={<section aria-labelledby="contract-history-heading" />}>
        <CardHeader className="border-b">
          <CardTitle id="contract-history-heading" className="text-base">
            Historial Inmutable
          </CardTitle>
          <CardDescription>Originales y enmiendas ordenados por docente y versión.</CardDescription>
        </CardHeader>
        {contractHistory.isLoading && (
          <div role="status" aria-live="polite" aria-busy="true" className="space-y-3 p-6">
            <span className="sr-only">Cargando historial de contratos…</span>
            <Skeleton className="h-5 w-1/3" />
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        )}
        {contractHistory.isError && (
          <Alert variant="error" className="m-6 w-auto">
            <AlertCircle aria-hidden="true" />
            <AlertDescription>No se pudo cargar el historial de contratos.</AlertDescription>
          </Alert>
        )}
        {contractHistory.isSuccess && contractHistory.data.length === 0 && (
          <EmptyState icon={FileText} title="Todavía no se emitieron contratos inmutables." />
        )}
        {contractHistory.isSuccess && contractHistory.data.length > 0 && (
          <ol className="divide-y">
            {contractHistory.data.map((document) => (
              <li key={document.public_id} className="px-6 py-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-sm font-semibold text-foreground">{document.teacher_name}</h3>
                      <StatusBadge tone={document.document_kind === 'original' ? 'success' : 'info'}>
                        {document.document_kind === 'original' ? 'Original' : `Enmienda ${document.amendment_sequence}`}
                      </StatusBadge>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {document.academic_period} · efectiva {formatDate(document.effective_date)} · emitida {formatDate(document.issued_at)}
                    </p>
                    <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
                      {document.lines.map((line) => (
                        <li key={`${document.public_id}-${line.line_number}`}>
                          <span className="font-medium text-foreground">{line.activity_kind === 'theory' ? 'Teoría' : 'Práctica'}:</span>{' '}
                          {line.subject_label} ({line.group_label}) · {line.hours}h · Bs {line.hourly_rate}
                          {line.change_kind !== 'full' ? ` · ${line.change_kind}` : ''}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    className="self-start"
                    onClick={() => void handleHistoryDownload(document)}
                    loading={downloadingFile === document.public_id}
                    aria-label={`Descargar ${document.document_kind === 'original' ? 'contrato original' : `enmienda ${document.amendment_sequence}`} de ${document.teacher_name}`}
                  >
                    <Download aria-hidden="true" />
                    Descargar PDF
                  </Button>
                </div>
              </li>
            ))}
          </ol>
        )}
      </Card>

      {/* Empty state after successful generation with 0 results */}
      {generateBatch.isSuccess && generatedContracts.length === 0 && (
        <Card>
          <EmptyState
            icon={FileSignature}
            title="No se emitieron contratos."
            description="Revisá que los docentes tengan carga efectiva y tarifas completas."
          />
        </Card>
      )}
    </div>
  )
}
