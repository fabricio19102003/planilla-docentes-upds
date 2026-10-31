import { useState, useEffect } from 'react'
import type { ReactNode } from 'react'
import { CheckCircle, AlertCircle, Info, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useImportTeacherProfiles, usePreviewTeacherProfiles, useUploadBiometric, useUploadHistory } from '@/api/hooks/useBiometric'
import { DesignationImportWizard } from '@/components/designations/DesignationImportWizard'
import { FileUploader } from '@/components/shared/FileUploader'
import { DataTable } from '@/components/shared/DataTable'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { api } from '@/api/client'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field, FieldDescription, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select, SelectItem, SelectPopup, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { BiometricUploadResult, TeacherProfileImportPreview, TeacherProfileImportResult, BiometricUpload } from '@/api/types'
import type { Column } from '@/components/shared/DataTable'

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

const BIOMETRIC_MONTHS = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
const BIOMETRIC_MONTH_ITEMS = BIOMETRIC_MONTHS.map((m) => ({ value: String(m), label: MONTH_NAMES[m] }))

const PROFILE_FIELD_LABELS: Record<string, string> = {
  email: 'Correo', phone: 'Teléfono', gender: 'Género', external_permanent: 'Tipo',
  academic_level: 'Nivel académico', profession: 'Profesión', specialty: 'Especialidad',
  bank: 'Banco', account_number: 'N.º cuenta', nit: 'NIT', sap_code: 'Código SAP',
  invoice_retention: 'Retención',
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`
}

function getUploadErrorDetail(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: string | { message?: string } } } })?.response?.data?.detail
  return (typeof detail === 'string' ? detail : detail?.message)
    ?? 'Verificá el formato e intentá de nuevo.'
}

const uploadHistoryColumns: Column<BiometricUpload>[] = [
  { key: 'filename', header: 'Archivo', className: 'font-medium' },
  {
    key: 'month',
    header: 'Período',
    render: (item) => `${MONTH_NAMES[item.month]} ${item.year}`,
  },
  {
    key: 'upload_date',
    header: 'Fecha de Subida',
    className: 'tabular-nums',
    render: (item) => formatDate(item.upload_date),
  },
  { key: 'total_records', header: 'Registros', align: 'right' },
  { key: 'total_teachers', header: 'Docentes', align: 'right' },
  {
    key: 'status',
    header: 'Estado',
    render: (item) => (
      <StatusBadge tone={item.status === 'PROCESSED' ? 'success' : 'warning'}>
        {item.status === 'PROCESSED' ? 'Procesado' : item.status}
      </StatusBadge>
    ),
  },
]

function UploadCard({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <Card>
      <CardHeader className="border-b pb-4">
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  )
}

function UploadErrorAlert({ error }: { error: unknown }) {
  return (
    <Alert variant="error">
      <AlertCircle />
      <AlertTitle>Error al subir el archivo</AlertTitle>
      <AlertDescription>{getUploadErrorDetail(error)}</AlertDescription>
    </Alert>
  )
}

function PendingLabel({ children }: { children: ReactNode }) {
  return (
    <>
      <Loader2 className="animate-spin" />
      {children}
    </>
  )
}

export function UploadPage() {
  const currentYear = new Date().getFullYear()
  const currentMonth = new Date().getMonth() + 1

  // Biometric state
  const [bioFile, setBioFile] = useState<File | null>(null)
  const [bioMonth, setBioMonth] = useState<number>(currentMonth)
  const [bioYear, setBioYear] = useState<number>(currentYear)
  const [bioResult, setBioResult] = useState<BiometricUploadResult | null>(null)
  const [bioProgress, setBioProgress] = useState(0)

  // Teacher list state
  const [teacherFile, setTeacherFile] = useState<File | null>(null)
  const [teacherPeriod, setTeacherPeriod] = useState('')
  const [teacherPreview, setTeacherPreview] = useState<TeacherProfileImportPreview | null>(null)
  const [teacherResult, setTeacherResult] = useState<TeacherProfileImportResult | null>(null)

  useEffect(() => {
    api.get<{ academic_period: string }>('/config/active-period')
      .then(res => setTeacherPeriod(res.data.academic_period))
      .catch(() => setTeacherPeriod(''))
  }, [])

  const uploadBiometric = useUploadBiometric()
  const previewTeacherProfiles = usePreviewTeacherProfiles()
  const importTeacherProfiles = useImportTeacherProfiles()
  const { data: history, isLoading: historyLoading } = useUploadHistory()

  const handleBioSubmit = () => {
    if (!bioFile) return
    setBioResult(null)
    setBioProgress(0)
    uploadBiometric.mutate(
      { file: bioFile, month: bioMonth, year: bioYear, onProgress: setBioProgress },
      {
        onSuccess: (data) => {
          setBioResult(data)
          setBioFile(null)
        },
      },
    )
  }

  const handleTeacherPreview = () => {
    if (!teacherFile || !teacherPeriod.trim()) return
    setTeacherPreview(null)
    setTeacherResult(null)
    previewTeacherProfiles.mutate(
      { file: teacherFile, academic_period: teacherPeriod },
      { onSuccess: setTeacherPreview },
    )
  }

  const handleTeacherApply = () => {
    if (!teacherFile || !teacherPreview?.can_apply) return
    importTeacherProfiles.mutate(
      { file: teacherFile, academic_period: teacherPeriod, confirmation_digest: teacherPreview.digest },
      { onSuccess: (data) => { setTeacherResult(data); setTeacherPreview(null); setTeacherFile(null) } },
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Carga de datos"
        description="Subí el reporte biométrico, el Excel de designaciones y la lista de docentes del período."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3">
        {/* Biometric Upload */}
        <UploadCard title="Reporte Biométrico" description="Subí el archivo .xls exportado del sistema biométrico">
          <FileUploader
            accept=".xls,.xlsx"
            label="Seleccioná el reporte biométrico"
            description="Archivo Excel exportado del reloj biométrico"
            onFileSelect={(f) => setBioFile(f)}
            progress={uploadBiometric.isPending ? bioProgress : null}
          />

          <div className="grid grid-cols-2 gap-3">
            <Field>
              <FieldLabel>Mes</FieldLabel>
              <Select
                value={String(bioMonth)}
                items={BIOMETRIC_MONTH_ITEMS}
                onValueChange={(v) => setBioMonth(Number(v))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectPopup>
                  {BIOMETRIC_MONTH_ITEMS.map((item) => (
                    <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>
                  ))}
                </SelectPopup>
              </Select>
            </Field>
            <Field>
              <FieldLabel>Año</FieldLabel>
              <Input
                type="number"
                value={bioYear}
                onChange={(e) => setBioYear(Number(e.target.value))}
                min={2020}
                max={2030}
                inputClassName="tabular-nums"
              />
            </Field>
          </div>

          <Button
            onClick={handleBioSubmit}
            disabled={!bioFile || uploadBiometric.isPending}
            size="lg"
            className="w-full"
          >
            {uploadBiometric.isPending ? <PendingLabel>Subiendo...</PendingLabel> : 'Subir Reporte Biométrico'}
          </Button>

          {uploadBiometric.isError && <UploadErrorAlert error={uploadBiometric.error} />}

          {bioResult && (
            <Alert variant="success">
              <CheckCircle />
              <AlertTitle>¡Archivo subido exitosamente!</AlertTitle>
              <AlertDescription>
                <p>{bioResult.records_count} registros de {bioResult.teachers_found} docentes</p>
                {bioResult.warnings.length > 0 && (
                  <p className="text-warning-foreground">{bioResult.warnings.length} advertencia(s)</p>
                )}
              </AlertDescription>
            </Alert>
          )}
        </UploadCard>

        {/* Designations Upload */}
        <UploadCard title="Designaciones Docentes" description="Importá el Excel de designaciones del semestre con vista previa fila por fila">
          <DesignationImportWizard />
          <p className="text-xs text-muted-foreground">
            Para ver, crear, corregir o finalizar designaciones una por una, entrá a{' '}
            <Link to="/designations" className="font-medium text-foreground underline underline-offset-4">Designaciones</Link>.
          </p>
        </UploadCard>

        {/* Teacher List Upload */}
        <UploadCard title="Lista de Docentes" description="Completá perfiles existentes con vista previa y confirmación">
          <FileUploader
            accept=".json"
            label="Seleccioná el sobre auditado de perfiles"
            description="JSON audit_envelope; nunca sobrescribe valores existentes"
            onFileSelect={(f) => { setTeacherFile(f); setTeacherPreview(null); setTeacherResult(null) }}
          />

          <Field>
            <FieldLabel>Período Académico</FieldLabel>
            <Input
              value={teacherPeriod}
              onChange={e => { setTeacherPeriod(e.target.value); setTeacherPreview(null); setTeacherResult(null) }}
              placeholder="Ej: II/2026"
            />
            <FieldDescription>Sólo completa campos vacíos. No activa períodos, elimina datos ni modifica accesos.</FieldDescription>
          </Field>

          <Button
            onClick={handleTeacherPreview}
            disabled={!teacherFile || !teacherPeriod.trim() || previewTeacherProfiles.isPending || importTeacherProfiles.isPending}
            size="lg"
            className="w-full"
          >
            {previewTeacherProfiles.isPending ? <PendingLabel>Validando...</PendingLabel> : 'Generar vista previa'}
          </Button>

          {(previewTeacherProfiles.isError || importTeacherProfiles.isError) && (
            <UploadErrorAlert error={previewTeacherProfiles.error ?? importTeacherProfiles.error} />
          )}

          {teacherPreview && (
            <>
              <Alert variant={teacherPreview.can_apply ? 'info' : 'error'}>
                {teacherPreview.can_apply ? <Info /> : <AlertCircle />}
                <AlertTitle>Vista previa: {teacherPreview.total_rows} perfiles · {teacherPreview.academic_period}</AlertTitle>
                <AlertDescription className="gap-1 text-xs tabular-nums">
                  <p>Formato: {teacherPreview.parsed_format} · Alcance: {teacherPreview.scope} · Política: completar vacíos</p>
                  <p>Identidades: {teacherPreview.identity.matched} coincidentes · {teacherPreview.identity.missing} ausentes · {teacherPreview.identity.conflicts} conflictos</p>
                  {teacherPreview.warnings.map((warning, index) => <p key={`teacher-warning-${index}`} className="text-warning-foreground">{warning}</p>)}
                  {teacherPreview.errors.map((error, index) => <p key={`teacher-error-${index}`} className="text-destructive-foreground">{error}</p>)}
                </AlertDescription>
              </Alert>
              <div className="max-h-56 overflow-auto rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Campo</TableHead>
                      <TableHead className="text-right">Crear*</TableHead>
                      <TableHead className="text-right">Completar</TableHead>
                      <TableHead className="text-right">Igual</TableHead>
                      <TableHead className="text-right">Conflicto</TableHead>
                      <TableHead className="text-right">Sin dato</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {Object.entries(teacherPreview.fields).map(([name, counts]) => (
                      <TableRow key={name}>
                        <TableCell>{PROFILE_FIELD_LABELS[name] ?? name}</TableCell>
                        <TableCell className="text-right tabular-nums text-destructive-foreground">{counts.creates}</TableCell>
                        <TableCell className="text-right tabular-nums">{counts.fills}</TableCell>
                        <TableCell className="text-right tabular-nums">{counts.noops}</TableCell>
                        <TableCell className="text-right tabular-nums text-destructive-foreground">{counts.conflicts}</TableCell>
                        <TableCell className="text-right tabular-nums">{counts.missing}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <p className="text-xs text-muted-foreground">* “Crear” indica un CI ausente y bloquea la importación; este flujo no crea docentes.</p>
              <Button onClick={handleTeacherApply} disabled={!teacherPreview.can_apply || importTeacherProfiles.isPending} size="lg" className="w-full">
                {importTeacherProfiles.isPending ? <PendingLabel>Aplicando...</PendingLabel> : 'Confirmar e importar'}
              </Button>
            </>
          )}

          {teacherResult && (
            <Alert variant="success">
              <CheckCircle />
              <AlertTitle>¡Perfiles completados!</AlertTitle>
              <AlertDescription>
                <p>{teacherResult.total_rows} filas confirmadas · {teacherResult.rows_with_fills} docentes con campos completados</p>
                <p>No se activó ningún período ni se modificaron contraseñas o accesos.</p>
              </AlertDescription>
            </Alert>
          )}
        </UploadCard>
      </div>

      {/* Upload History */}
      <section className="space-y-3">
        <h3 className="text-base font-semibold text-foreground">Historial de Subidas</h3>
        <DataTable
          columns={uploadHistoryColumns}
          data={history ?? []}
          loading={historyLoading}
          emptyMessage="No hay subidas registradas aún"
        />
      </section>

    </div>
  )
}
