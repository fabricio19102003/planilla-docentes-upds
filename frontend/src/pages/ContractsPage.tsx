import { useState } from 'react'
import {
  FileSignature,
  Download,
  Loader2,
  CheckCircle,
  Users,
  Search,
  FileText,
  ArchiveIcon,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useTeachers } from '@/api/hooks/useTeachers'
import {
  useGenerateBatchContracts,
  downloadContract,
  downloadContractsZip,
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

// ─── Page ─────────────────────────────────────────────────────────────────────

export function ContractsPage() {
  // Config
  const [department, setDepartment] = useState('Pando')
  const [durationText, setDurationText] = useState('4 meses y 13 días')
  const [startDate, setStartDate] = useState('05 de marzo de 2026')
  const [endDate, setEndDate] = useState('18 de julio de 2026')
  const [hourlyRate, setHourlyRate] = useState('70,00')
  const [hourlyRateLiteral, setHourlyRateLiteral] = useState('Setenta bolivianos 00/100')

  // Teacher selection
  const [selectMode, setSelectMode] = useState<'all' | 'select'>('all')
  const [selectedCis, setSelectedCis] = useState<Set<string>>(new Set())
  const [searchTerm, setSearchTerm] = useState('')

  // Results
  const [generatedContracts, setGeneratedContracts] = useState<ContractFileInfo[]>([])
  const [downloadingZip, setDownloadingZip] = useState(false)
  const [downloadingFile, setDownloadingFile] = useState<string | null>(null)

  const { data: teachersData } = useTeachers({ page: 1, perPage: 500 })
  const teachers = teachersData?.items ?? []
  const generateBatch = useGenerateBatchContracts()

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

  const isConfigValid =
    department.trim() !== '' &&
    durationText.trim() !== '' &&
    startDate.trim() !== '' &&
    endDate.trim() !== '' &&
    hourlyRate.trim() !== '' &&
    hourlyRateLiteral.trim() !== ''

  const canGenerate =
    isConfigValid &&
    (selectMode === 'all' || selectedCis.size > 0)

  const handleGenerate = () => {
    setGeneratedContracts([])
    const payload: BatchContractRequest = {
      department,
      duration_text: durationText,
      start_date: startDate,
      end_date: endDate,
      hourly_rate: hourlyRate,
      hourly_rate_literal: hourlyRateLiteral,
      teacher_cis: selectMode === 'select' ? [...selectedCis] : null,
    }
    generateBatch.mutate(payload, {
      onSuccess: (data) => {
        setGeneratedContracts(data.contracts)
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

  const handleDownloadOne = async (filename: string) => {
    setDownloadingFile(filename)
    try {
      await downloadContract(filename)
    } finally {
      setDownloadingFile(null)
    }
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold" style={{ color: '#003366' }}>
          Generación de Contratos
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Generá contratos de prestación de servicios para los docentes
        </p>
      </div>

      {/* Config card */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-6 py-5 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg gradient-stat-navy flex items-center justify-center">
              <FileSignature size={16} className="text-white" />
            </div>
            <div>
              <h2 className="text-base font-semibold" style={{ color: '#003366' }}>
                Configuración del Contrato
              </h2>
              <p className="text-xs text-gray-500">
                Parámetros que se aplicarán a todos los contratos generados
              </p>
            </div>
          </div>
        </div>
        <div className="px-6 py-5">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Department */}
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">
                Departamento
              </label>
              <select
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC]"
              >
                {DEPARTMENTS.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>

            {/* Duration */}
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">
                Duración del contrato
              </label>
              <input
                type="text"
                value={durationText}
                onChange={(e) => setDurationText(e.target.value)}
                placeholder="ej: 4 meses y 13 días"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC]"
              />
            </div>

            {/* Hourly rate */}
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">
                Tarifa por hora (Bs)
              </label>
              <input
                type="text"
                value={hourlyRate}
                onChange={(e) => setHourlyRate(e.target.value)}
                placeholder="ej: 70,00"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC]"
              />
            </div>

            {/* Start date */}
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">
                Fecha de inicio
              </label>
              <input
                type="text"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                placeholder="ej: 05 de marzo de 2026"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC]"
              />
            </div>

            {/* End date */}
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">
                Fecha de fin
              </label>
              <input
                type="text"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                placeholder="ej: 18 de julio de 2026"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC]"
              />
            </div>

            {/* Hourly rate literal */}
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">
                Tarifa en letras
              </label>
              <input
                type="text"
                value={hourlyRateLiteral}
                onChange={(e) => setHourlyRateLiteral(e.target.value)}
                placeholder="ej: Setenta bolivianos 00/100"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC]"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Teacher selection card */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-6 py-5 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg gradient-stat-navy flex items-center justify-center">
              <Users size={16} className="text-white" />
            </div>
            <div>
              <h2 className="text-base font-semibold" style={{ color: '#003366' }}>
                Selección de Docentes
              </h2>
              <p className="text-xs text-gray-500">
                Elegí para quiénes generar contratos
              </p>
            </div>
          </div>
        </div>
        <div className="px-6 py-5 space-y-4">
          {/* Toggle all/select */}
          <div className="flex gap-2">
            <button
              onClick={() => setSelectMode('all')}
              className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
                selectMode === 'all'
                  ? 'bg-[#003366] text-white border-[#003366]'
                  : 'bg-white text-gray-600 border-gray-300 hover:border-[#003366]'
              }`}
            >
              Todos los docentes
            </button>
            <button
              onClick={() => setSelectMode('select')}
              className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
                selectMode === 'select'
                  ? 'bg-[#003366] text-white border-[#003366]'
                  : 'bg-white text-gray-600 border-gray-300 hover:border-[#003366]'
              }`}
            >
              Seleccionar docentes
            </button>
          </div>

          {selectMode === 'select' && (
            <>
              {/* Search */}
              <div className="relative max-w-sm">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder="Buscar por nombre o CI..."
                  className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] bg-gray-50/50"
                />
              </div>

              {/* Counter */}
              {selectedCis.size > 0 && (
                <p className="text-sm font-medium text-[#003366]">
                  {selectedCis.size} docente{selectedCis.size !== 1 ? 's' : ''} seleccionado{selectedCis.size !== 1 ? 's' : ''}
                </p>
              )}

              {/* Teacher list */}
              <div className="max-h-72 overflow-y-auto rounded-lg border border-gray-200 divide-y divide-gray-100">
                {filteredTeachers.length === 0 ? (
                  <p className="text-center text-gray-400 text-sm py-6">
                    No se encontraron docentes
                  </p>
                ) : (
                  filteredTeachers.map((teacher) => (
                    <label
                      key={teacher.ci}
                      className="flex items-center gap-3 px-4 py-2.5 hover:bg-blue-50/50 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedCis.has(teacher.ci)}
                        onChange={() => toggleTeacher(teacher.ci)}
                        className="rounded border-gray-300 text-[#003366] focus:ring-[#0066CC]"
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-800 truncate">{teacher.full_name}</p>
                        <p className="text-xs text-gray-500">CI: {teacher.ci}</p>
                      </div>
                      {selectedCis.has(teacher.ci) && (
                        <CheckCircle size={16} className="text-green-500 flex-shrink-0" />
                      )}
                    </label>
                  ))
                )}
              </div>
            </>
          )}

          {selectMode === 'all' && (
            <p className="text-sm text-gray-500">
              Se generarán contratos para <span className="font-medium text-gray-700">{teachers.length}</span> docentes con designaciones.
            </p>
          )}
        </div>
      </div>

      {/* Generate button */}
      <div className="flex items-center gap-4">
        <Button
          onClick={handleGenerate}
          disabled={!canGenerate || generateBatch.isPending}
          className="gap-2 text-white"
          style={{ backgroundColor: '#003366' }}
        >
          {generateBatch.isPending ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              Generando contratos...
            </>
          ) : (
            <>
              <FileSignature size={16} />
              Generar Contratos
            </>
          )}
        </Button>
        {!canGenerate && !generateBatch.isPending && (
          <p className="text-xs text-gray-400">
            {!isConfigValid
              ? 'Completá todos los campos de configuración'
              : 'Seleccioná al menos un docente'}
          </p>
        )}
      </div>

      {/* Error state */}
      {generateBatch.isError && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-600">
            Error al generar contratos. Verificá la configuración y volvé a intentarlo.
          </p>
        </div>
      )}

      {/* Results card */}
      {generatedContracts.length > 0 && (
        <div className="card-3d-static overflow-hidden border-l-4" style={{ borderLeftColor: '#16a34a' }}>
          <div className="px-6 py-5 border-b border-gray-100 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <CheckCircle size={20} className="text-green-600" />
              <div>
                <h3 className="text-base font-semibold text-green-700">
                  {generatedContracts.length} contrato{generatedContracts.length !== 1 ? 's' : ''} generado{generatedContracts.length !== 1 ? 's' : ''}
                </h3>
                <p className="text-xs text-gray-500">Listos para descargar</p>
              </div>
            </div>
            <Button
              variant="outline"
              className="gap-2 border-[#003366] text-[#003366] hover:bg-blue-50"
              onClick={() => void handleDownloadAll()}
              disabled={downloadingZip}
            >
              {downloadingZip ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <ArchiveIcon size={14} />
              )}
              Descargar Todos (.zip)
            </Button>
          </div>
          <div className="divide-y divide-gray-100 max-h-96 overflow-y-auto">
            {generatedContracts.map((contract) => (
              <div
                key={contract.filename}
                className="flex items-center justify-between px-6 py-3 hover:bg-gray-50/50"
              >
                <div className="flex items-center gap-3">
                  <FileText size={16} className="text-[#003366] flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-gray-800">{contract.teacher_name}</p>
                    <p className="text-xs text-gray-500">
                      CI: {contract.teacher_ci} · {formatBytes(contract.file_size)}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => void handleDownloadOne(contract.filename)}
                  disabled={downloadingFile === contract.filename}
                  className="inline-flex items-center gap-1.5 text-[#0066CC] hover:underline text-sm font-medium disabled:opacity-50"
                >
                  {downloadingFile === contract.filename ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Download size={14} />
                  )}
                  PDF
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state after successful generation with 0 results */}
      {generateBatch.isSuccess && generatedContracts.length === 0 && (
        <div className="card-3d-static p-8 text-center">
          <p className="text-gray-400 text-sm">
            No se generaron contratos. Verificá que los docentes seleccionados tengan designaciones.
          </p>
        </div>
      )}
    </div>
  )
}
