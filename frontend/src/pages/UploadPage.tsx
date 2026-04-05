import { useState } from 'react'
import { CheckCircle, AlertCircle, Loader2, Users } from 'lucide-react'
import { useUploadBiometric, useUploadDesignations, useUploadHistory, useUploadTeacherList } from '@/api/hooks/useBiometric'
import { FileUploader } from '@/components/shared/FileUploader'
import { DataTable } from '@/components/shared/DataTable'
import { LoadingPage } from '@/components/shared/LoadingSpinner'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import type { BiometricUploadResult, DesignationUploadResponse, TeacherUploadResponse, BiometricUpload } from '@/api/types'
import type { Column } from '@/components/shared/DataTable'

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`
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
  const [desResult, setDesResult] = useState<DesignationUploadResponse | null>(null)

  // Teacher list state
  const [teacherFile, setTeacherFile] = useState<File | null>(null)
  const [teacherResult, setTeacherResult] = useState<TeacherUploadResponse | null>(null)

  const uploadBiometric = useUploadBiometric()
  const uploadDesignations = useUploadDesignations()
  const uploadTeacherList = useUploadTeacherList()
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

  const handleDesSubmit = () => {
    if (!desFile) return
    setDesResult(null)
    uploadDesignations.mutate(
      { file: desFile },
      {
        onSuccess: (data) => {
          setDesResult(data)
          setDesFile(null)
        },
      },
    )
  }

  const handleTeacherSubmit = () => {
    if (!teacherFile) return
    setTeacherResult(null)
    uploadTeacherList.mutate(teacherFile, {
      onSuccess: (data) => {
        setTeacherResult(data)
        setTeacherFile(null)
      },
    })
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
                    {(uploadBiometric.error as any)?.response?.data?.detail
                      ?? 'Verificá el formato e intentá de nuevo.'}
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
              onFileSelect={(f) => setDesFile(f)}
            />

            <Button
              onClick={handleDesSubmit}
              disabled={!desFile || uploadDesignations.isPending}
              className="w-full h-10"
              style={{ backgroundColor: '#003366' }}
            >
              {uploadDesignations.isPending ? (
                <>
                  <Loader2 size={16} className="animate-spin mr-2" />
                  Procesando...
                </>
              ) : (
                'Subir Designaciones'
              )}
            </Button>

            {uploadDesignations.isError && (
              <div className="flex items-start gap-2 p-3 bg-red-50 rounded-lg border border-red-200">
                <AlertCircle size={16} className="text-red-500 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm text-red-600 font-medium">Error al subir el archivo</p>
                  <p className="text-xs text-red-500 mt-0.5">
                    {(uploadDesignations.error as any)?.response?.data?.detail
                      ?? 'Verificá el formato e intentá de nuevo.'}
                  </p>
                </div>
              </div>
            )}

            {desResult && (
              <div className="space-y-3">
                <div className="flex items-start gap-2 p-3 bg-green-50 rounded-lg border border-green-200">
                  <CheckCircle size={16} className="text-green-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-semibold text-green-700">¡Designaciones cargadas!</p>
                    <p className="text-xs text-green-600 mt-0.5">
                      {desResult.designations_loaded} designaciones · {desResult.teachers_created} docentes nuevos
                      {desResult.teachers_reused > 0 && ` · ${desResult.teachers_reused} reutilizados`}
                      {desResult.skipped > 0 && ` · ${desResult.skipped} omitidos`}
                    </p>
                    {desResult.warnings.length > 0 && (
                      <p className="text-xs text-yellow-600 mt-1">
                        {desResult.warnings.length} advertencia(s)
                      </p>
                    )}
                  </div>
                </div>
                {desResult.users_created > 0 && (
                  <div className="flex items-start gap-2 p-3 bg-blue-50 rounded-lg border border-blue-200">
                    <Users size={16} className="text-blue-600 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-sm font-semibold text-blue-700">
                        {desResult.users_created} usuarios docentes creados automáticamente
                      </p>
                      <p className="text-xs text-blue-600 mt-0.5">
                        Los docentes deberán solicitar el restablecimiento de su contraseña al administrador
                      </p>
                          {desResult.users_skipped > 0 && (
                        <p className="text-xs text-gray-500 mt-0.5">
                          {desResult.users_skipped} usuario(s) no se pudieron crear (posible CI duplicado)
                        </p>
                      )}
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
            <p className="text-sm text-gray-500 mt-0.5">Subí la lista de docentes en formato Excel o JSON</p>
          </div>
          <div className="p-5 space-y-4">
            <FileUploader
              accept=".json,.xlsx,.xls"
              label="Seleccioná la lista de docentes"
              description="Archivo Excel (.xlsx) o JSON con los docentes del semestre"
              onFileSelect={(f) => setTeacherFile(f)}
            />

            <Button
              onClick={handleTeacherSubmit}
              disabled={!teacherFile || uploadTeacherList.isPending}
              className="w-full h-10"
              style={{ backgroundColor: '#003366' }}
            >
              {uploadTeacherList.isPending ? (
                <>
                  <Loader2 size={16} className="animate-spin mr-2" />
                  Procesando...
                </>
              ) : (
                'Subir Lista de Docentes'
              )}
            </Button>

            {uploadTeacherList.isError && (
              <div className="flex items-start gap-2 p-3 bg-red-50 rounded-lg border border-red-200">
                <AlertCircle size={16} className="text-red-500 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm text-red-600 font-medium">Error al subir el archivo</p>
                  <p className="text-xs text-red-500 mt-0.5">
                    {(uploadTeacherList.error as any)?.response?.data?.detail
                      ?? 'Verificá el formato e intentá de nuevo.'}
                  </p>
                </div>
              </div>
            )}

            {teacherResult && (
              <div className="space-y-3">
                <div className="flex items-start gap-2 p-3 bg-green-50 rounded-lg border border-green-200">
                  <CheckCircle size={16} className="text-green-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-semibold text-green-700">¡Lista cargada exitosamente!</p>
                    <p className="text-xs text-green-600 mt-0.5">
                      {teacherResult.created} nuevos
                      {teacherResult.updated > 0 && ` · ${teacherResult.updated} actualizados`}
                      {teacherResult.skipped > 0 && ` · ${teacherResult.skipped} omitidos`}
                      {' '}· {teacherResult.total_processed} total
                    </p>
                    {teacherResult.warnings.length > 0 && (
                      <p className="text-xs text-yellow-600 mt-1">
                        {teacherResult.warnings.length} advertencia(s)
                      </p>
                    )}
                  </div>
                </div>
                {teacherResult.warnings.length > 0 && (
                  <div className="flex items-start gap-2 p-3 bg-blue-50 rounded-lg border border-blue-200">
                    <Users size={16} className="text-blue-600 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-sm font-semibold text-blue-700">Docentes vinculados</p>
                      <ul className="mt-1 space-y-0.5">
                        {teacherResult.warnings.map((w, i) => (
                          <li key={i} className="text-xs text-blue-600">{w}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
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
