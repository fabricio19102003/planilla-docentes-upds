import { useState, useEffect } from 'react'
import { CheckCircle, AlertCircle, Loader2, Users } from 'lucide-react'
import { useImportTeacherProfiles, usePreviewDesignations, usePreviewTeacherProfiles, useUploadBiometric, useUploadDesignations, useUploadHistory } from '@/api/hooks/useBiometric'
import { FileUploader } from '@/components/shared/FileUploader'
import { DataTable } from '@/components/shared/DataTable'
import { LoadingPage } from '@/components/shared/LoadingSpinner'
import { api } from '@/api/client'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { BiometricUploadResult, DesignationImportPreview, DesignationUploadResponse, TeacherProfileImportPreview, TeacherProfileImportResult, BiometricUpload } from '@/api/types'
import type { Column } from '@/components/shared/DataTable'

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

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
  { key: 'filename', header: 'Archivo' },
  {
    key: 'month',
    header: 'Período',
    render: (item) => `${MONTH_NAMES[item.month]} ${item.year}`,
  },
  {
    key: 'upload_date',
    header: 'Fecha de Subida',
    render: (item) => formatDate(item.upload_date),
  },
  { key: 'total_records', header: 'Registros' },
  { key: 'total_teachers', header: 'Docentes' },
  {
    key: 'status',
    header: 'Estado',
    render: (item) => (
      <Badge
        className={
          item.status === 'PROCESSED'
            ? 'bg-green-100 text-green-700'
            : 'bg-yellow-100 text-yellow-700'
        }
      >
        {item.status === 'PROCESSED' ? 'Procesado' : item.status}
      </Badge>
    ),
  },
]

export function UploadPage() {
  const currentYear = new Date().getFullYear()
  const currentMonth = new Date().getMonth() + 1

  // Biometric state
  const [bioFile, setBioFile] = useState<File | null>(null)
  const [bioMonth, setBioMonth] = useState<number>(currentMonth)
  const [bioYear, setBioYear] = useState<number>(currentYear)
  const [bioResult, setBioResult] = useState<BiometricUploadResult | null>(null)

  // Designations state
  const [desFile, setDesFile] = useState<File | null>(null)
  const [desPreview, setDesPreview] = useState<DesignationImportPreview | null>(null)
  const [desResult, setDesResult] = useState<DesignationUploadResponse | null>(null)
  // The server value is only a suggested selection; importing never activates a period.
  const [academicPeriod, setAcademicPeriod] = useState('')

  // Teacher list state
  const [teacherFile, setTeacherFile] = useState<File | null>(null)
  const [teacherPeriod, setTeacherPeriod] = useState('')
  const [teacherPreview, setTeacherPreview] = useState<TeacherProfileImportPreview | null>(null)
  const [teacherResult, setTeacherResult] = useState<TeacherProfileImportResult | null>(null)

  useEffect(() => {
    api.get<{ academic_period: string }>('/config/active-period')
      .then(res => { setAcademicPeriod(res.data.academic_period); setTeacherPeriod(res.data.academic_period) })
      .catch(() => { setAcademicPeriod(''); setTeacherPeriod('') })
  }, [])

  const uploadBiometric = useUploadBiometric()
  const previewDesignations = usePreviewDesignations()
  const uploadDesignations = useUploadDesignations()
  const previewTeacherProfiles = usePreviewTeacherProfiles()
  const importTeacherProfiles = useImportTeacherProfiles()
  const { data: history, isLoading: historyLoading } = useUploadHistory()

  const handleBioSubmit = () => {
    if (!bioFile) return
    setBioResult(null)
    uploadBiometric.mutate(
      { file: bioFile, month: bioMonth, year: bioYear },
      {
        onSuccess: (data) => {
          setBioResult(data)
          setBioFile(null)
        },
      },
    )
  }

  const handleDesPreview = () => {
    if (!desFile || !academicPeriod.trim()) return
    setDesPreview(null)
    setDesResult(null)
    previewDesignations.mutate(
      { file: desFile, academic_period: academicPeriod },
      {
        onSuccess: setDesPreview,
      },
    )
  }

  const handleDesApply = () => {
    if (!desFile || !desPreview?.can_apply) return
    uploadDesignations.mutate(
      { file: desFile, academic_period: academicPeriod, confirmation_digest: desPreview.digest },
      { onSuccess: (data) => { setDesResult(data); setDesPreview(null); setDesFile(null) } },
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
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
        {/* Biometric Upload */}
        <div className="card-3d overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h3 className="text-base font-semibold" style={{ color: '#003366' }}>Reporte Biométrico</h3>
            <p className="text-sm text-gray-500 mt-0.5">Subí el archivo .xls exportado del sistema biométrico</p>
          </div>
          <div className="p-5 space-y-4">
            <FileUploader
              accept=".xls,.xlsx"
              label="Seleccioná el reporte biométrico"
              description="Archivo Excel exportado del reloj biométrico"
              onFileSelect={(f) => setBioFile(f)}
            />

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Mes</label>
                <select
                  value={bioMonth}
                  onChange={(e) => setBioMonth(Number(e.target.value))}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC]"
                >
                  {[3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((m) => (
                    <option key={m} value={m}>{MONTH_NAMES[m]}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Año</label>
                <input
                  type="number"
                  value={bioYear}
                  onChange={(e) => setBioYear(Number(e.target.value))}
                  min={2020}
                  max={2030}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC]"
                />
              </div>
            </div>

            <Button
              onClick={handleBioSubmit}
              disabled={!bioFile || uploadBiometric.isPending}
              className="w-full h-10"
              style={{ backgroundColor: '#003366' }}
            >
              {uploadBiometric.isPending ? (
                <>
                  <Loader2 size={16} className="animate-spin mr-2" />
                  Subiendo...
                </>
              ) : (
                'Subir Reporte Biométrico'
              )}
            </Button>

            {uploadBiometric.isError && (
              <div className="flex items-start gap-2 p-3 bg-red-50 rounded-lg border border-red-200">
                <AlertCircle size={16} className="text-red-500 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm text-red-600 font-medium">Error al subir el archivo</p>
                  <p className="text-xs text-red-500 mt-0.5">
                    {getUploadErrorDetail(uploadBiometric.error)}
                  </p>
                </div>
              </div>
            )}

            {bioResult && (
              <div className="flex items-start gap-2 p-3 bg-green-50 rounded-lg border border-green-200">
                <CheckCircle size={16} className="text-green-600 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm font-semibold text-green-700">¡Archivo subido exitosamente!</p>
                  <p className="text-xs text-green-600 mt-0.5">
                    {bioResult.records_count} registros de {bioResult.teachers_found} docentes
                  </p>
                  {bioResult.warnings.length > 0 && (
                    <p className="text-xs text-yellow-600 mt-1">
                      {bioResult.warnings.length} advertencia(s)
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Designations Upload */}
        <div className="card-3d overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h3 className="text-base font-semibold" style={{ color: '#003366' }}>Designaciones Docentes</h3>
            <p className="text-sm text-gray-500 mt-0.5">Subí el archivo de designaciones docentes (JSON o Excel)</p>
          </div>
          <div className="p-5 space-y-4">
            <FileUploader
              accept=".json,.xlsx"
              label="Seleccioná el archivo de designaciones"
              description="Archivo JSON o Excel con las designaciones del semestre"
              onFileSelect={(f) => { setDesFile(f); setDesPreview(null); setDesResult(null) }}
            />

            <div className="space-y-1.5">
              <Label className="text-sm font-medium text-gray-700">Período Académico</Label>
              <Input
                value={academicPeriod}
                onChange={e => { setAcademicPeriod(e.target.value); setDesPreview(null); setDesResult(null) }}
                placeholder="Ej: I/2026, II/2025"
                className="text-sm"
              />
              <p className="text-xs text-gray-400">La importación usa este período, pero no lo activa automáticamente.</p>
            </div>

            <Button
              onClick={handleDesPreview}
              disabled={!desFile || !academicPeriod.trim() || previewDesignations.isPending || uploadDesignations.isPending}
              className="w-full h-10"
              style={{ backgroundColor: '#003366' }}
            >
              {previewDesignations.isPending ? (
                <>
                  <Loader2 size={16} className="animate-spin mr-2" />
                  Validando...
                </>
              ) : (
                'Generar vista previa'
              )}
            </Button>

            {(previewDesignations.isError || uploadDesignations.isError) && (
              <div className="flex items-start gap-2 p-3 bg-red-50 rounded-lg border border-red-200">
                <AlertCircle size={16} className="text-red-500 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm text-red-600 font-medium">Error al subir el archivo</p>
                  <p className="text-xs text-red-500 mt-0.5">
                    {getUploadErrorDetail(previewDesignations.error ?? uploadDesignations.error)}
                  </p>
                </div>
              </div>
            )}

            {desPreview && (
              <div className={`space-y-3 rounded-lg border p-3 ${desPreview.can_apply ? 'border-blue-200 bg-blue-50' : 'border-red-200 bg-red-50'}`}>
                <div>
                  <p className="text-sm font-semibold text-gray-800">Vista previa: {desPreview.total_rows} filas · {desPreview.academic_period}</p>
                  <p className="text-xs text-gray-600 mt-1">Formato: {desPreview.parsed_format}</p>
                </div>
                <div className="grid grid-cols-1 gap-1 text-xs text-gray-700">
                  <p>Docentes: {desPreview.teachers.creates} nuevos · {desPreview.teachers.updates} actualizaciones · {desPreview.teachers.noops} sin cambios</p>
                  <p>Designaciones: {desPreview.designations.creates} nuevas · {desPreview.designations.updates} actualizaciones · {desPreview.designations.noops} sin cambios</p>
                  <p>Usuarios: {desPreview.users.creates} nuevos · {desPreview.users.updates} vinculaciones · {desPreview.users.noops} sin cambios</p>
                </div>
                {desPreview.warnings.map((warning, index) => <p key={`warning-${index}`} className="text-xs text-yellow-700">{warning}</p>)}
                {desPreview.errors.map((error, index) => <p key={`error-${index}`} className="text-xs text-red-700">{error}</p>)}
                <Button
                  onClick={handleDesApply}
                  disabled={!desPreview.can_apply || uploadDesignations.isPending}
                  className="w-full h-10"
                  style={{ backgroundColor: '#003366' }}
                >
                  {uploadDesignations.isPending ? <><Loader2 size={16} className="animate-spin mr-2" />Aplicando...</> : 'Confirmar e importar'}
                </Button>
              </div>
            )}

            {desResult && (
              <div className="space-y-3">
                <div className="flex items-start gap-2 p-3 bg-green-50 rounded-lg border border-green-200">
                  <CheckCircle size={16} className="text-green-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-semibold text-green-700">¡Designaciones cargadas!</p>
                    <p className="text-xs text-green-600 mt-0.5">
                      {desResult.total_rows} filas aplicadas · {desResult.designations.creates} nuevas · {desResult.designations.updates} actualizadas · {desResult.designations.noops} sin cambios
                    </p>
                    {desResult.warnings.length > 0 && (
                      <p className="text-xs text-yellow-600 mt-1">
                        {desResult.warnings.length} advertencia(s)
                      </p>
                    )}
                  </div>
                </div>
                {desResult.users.creates > 0 && (
                  <div className="flex items-start gap-2 p-3 bg-blue-50 rounded-lg border border-blue-200">
                    <Users size={16} className="text-blue-600 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-sm font-semibold text-blue-700">
                        {desResult.users.creates} usuarios docentes creados automáticamente
                      </p>
                      <p className="text-xs text-blue-600 mt-0.5">
                        Los docentes deberán solicitar el restablecimiento de su contraseña al administrador
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
        {/* Teacher List Upload */}
        <div className="card-3d overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h3 className="text-base font-semibold" style={{ color: '#003366' }}>Lista de Docentes</h3>
            <p className="text-sm text-gray-500 mt-0.5">Completá perfiles existentes con vista previa y confirmación</p>
          </div>
          <div className="p-5 space-y-4">
            <FileUploader
              accept=".json"
              label="Seleccioná el sobre auditado de perfiles"
              description="JSON audit_envelope; nunca sobrescribe valores existentes"
              onFileSelect={(f) => { setTeacherFile(f); setTeacherPreview(null); setTeacherResult(null) }}
            />

            <div className="space-y-1.5">
              <Label className="text-sm font-medium text-gray-700">Período Académico</Label>
              <Input
                value={teacherPeriod}
                onChange={e => { setTeacherPeriod(e.target.value); setTeacherPreview(null); setTeacherResult(null) }}
                placeholder="Ej: II/2026"
              />
              <p className="text-xs text-gray-400">Sólo completa campos vacíos. No activa períodos, elimina datos ni modifica accesos.</p>
            </div>

            <Button
              onClick={handleTeacherPreview}
              disabled={!teacherFile || !teacherPeriod.trim() || previewTeacherProfiles.isPending || importTeacherProfiles.isPending}
              className="w-full h-10"
              style={{ backgroundColor: '#003366' }}
            >
              {previewTeacherProfiles.isPending ? (
                <>
                  <Loader2 size={16} className="animate-spin mr-2" />
                  Validando...
                </>
              ) : (
                'Generar vista previa'
              )}
            </Button>

            {(previewTeacherProfiles.isError || importTeacherProfiles.isError) && (
              <div className="flex items-start gap-2 p-3 bg-red-50 rounded-lg border border-red-200">
                <AlertCircle size={16} className="text-red-500 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm text-red-600 font-medium">Error al subir el archivo</p>
                  <p className="text-xs text-red-500 mt-0.5">
                    {getUploadErrorDetail(previewTeacherProfiles.error ?? importTeacherProfiles.error)}
                  </p>
                </div>
              </div>
            )}

            {teacherPreview && (
              <div className={`space-y-3 rounded-lg border p-3 ${teacherPreview.can_apply ? 'border-blue-200 bg-blue-50' : 'border-red-200 bg-red-50'}`}>
                <div>
                  <p className="text-sm font-semibold text-gray-800">Vista previa: {teacherPreview.total_rows} perfiles · {teacherPreview.academic_period}</p>
                  <p className="text-xs text-gray-600 mt-1">Formato: {teacherPreview.parsed_format} · Alcance: {teacherPreview.scope} · Política: completar vacíos</p>
                  <p className="text-xs text-gray-600 mt-1">Identidades: {teacherPreview.identity.matched} coincidentes · {teacherPreview.identity.missing} ausentes · {teacherPreview.identity.conflicts} conflictos</p>
                </div>
                <div className="max-h-56 overflow-auto rounded border border-gray-200 bg-white">
                  <table className="w-full text-xs">
                    <thead><tr className="bg-gray-50"><th className="p-1.5 text-left">Campo</th><th>Crear*</th><th>Completar</th><th>Igual</th><th>Conflicto</th><th>Sin dato</th></tr></thead>
                    <tbody>
                      {Object.entries(teacherPreview.fields).map(([name, counts]) => (
                        <tr key={name} className="border-t"><td className="p-1.5">{PROFILE_FIELD_LABELS[name] ?? name}</td><td className="text-center text-red-600">{counts.creates}</td><td className="text-center">{counts.fills}</td><td className="text-center">{counts.noops}</td><td className="text-center text-red-600">{counts.conflicts}</td><td className="text-center">{counts.missing}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="text-[11px] text-gray-500">* “Crear” indica un CI ausente y bloquea la importación; este flujo no crea docentes.</p>
                {teacherPreview.warnings.map((warning, index) => <p key={`teacher-warning-${index}`} className="text-xs text-yellow-700">{warning}</p>)}
                {teacherPreview.errors.map((error, index) => <p key={`teacher-error-${index}`} className="text-xs text-red-700">{error}</p>)}
                <Button onClick={handleTeacherApply} disabled={!teacherPreview.can_apply || importTeacherProfiles.isPending} className="w-full h-10" style={{ backgroundColor: '#003366' }}>
                  {importTeacherProfiles.isPending ? <><Loader2 size={16} className="animate-spin mr-2" />Aplicando...</> : 'Confirmar e importar'}
                </Button>
              </div>
            )}

            {teacherResult && (
              <div className="flex items-start gap-2 p-3 bg-green-50 rounded-lg border border-green-200">
                <CheckCircle size={16} className="text-green-600 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm font-semibold text-green-700">¡Perfiles completados!</p>
                  <p className="text-xs text-green-600 mt-0.5">{teacherResult.total_rows} filas confirmadas · {teacherResult.rows_with_fills} docentes con campos completados</p>
                  <p className="text-xs text-green-600 mt-1">No se activó ningún período ni se modificaron contraseñas o accesos.</p>
                  </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Upload History */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <h3 className="text-base font-semibold" style={{ color: '#003366' }}>Historial de Subidas</h3>
        </div>
        <div className="p-5">
          {historyLoading ? (
            <LoadingPage />
          ) : (
            <DataTable
              columns={uploadHistoryColumns}
              data={history ?? []}
              emptyMessage="No hay subidas registradas aún"
            />
          )}
        </div>
      </div>
    </div>
  )
}
