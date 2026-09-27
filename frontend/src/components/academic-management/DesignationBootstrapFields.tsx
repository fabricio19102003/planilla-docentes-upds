import type { AcademicProgram } from '@/api/types'
import {
  DESIGNATION_BOOTSTRAP_EFFECTIVE_DATE,
  DESIGNATION_BOOTSTRAP_PERIOD,
} from '@/api/academicManagement'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export interface DesignationBootstrapSelectedFiles {
  officialWorkbook: File | null
  salaryWorkbook: File | null
  aliasResolution: File | null
}

function FileField({
  id,
  label,
  description,
  accept,
  required,
  disabled,
  error,
  onChange,
}: {
  id: string
  label: string
  description: string
  accept: string
  required?: boolean
  disabled?: boolean
  error?: string
  onChange: (file: File | null) => void
}) {
  const descriptionId = `${id}-description`
  const errorId = `${id}-error`
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}{required ? ' *' : ''}</Label>
      <Input
        id={id}
        type="file"
        accept={accept}
        required={required}
        disabled={disabled}
        aria-invalid={Boolean(error)}
        aria-describedby={`${descriptionId}${error ? ` ${errorId}` : ''}`}
        onChange={(event) => onChange(event.target.files?.[0] ?? null)}
        className="h-11 py-2"
      />
      <p id={descriptionId} className="text-xs leading-5 text-slate-600">{description}</p>
      {error && <p id={errorId} role="alert" className="text-sm text-red-700">{error}</p>}
    </div>
  )
}

export function DesignationBootstrapFields({
  activePrograms,
  programIdentity,
  fieldErrors,
  disabled,
  onProgramChange,
  onFileChange,
}: {
  activePrograms: AcademicProgram[]
  programIdentity: string
  fieldErrors: Record<string, string>
  disabled: boolean
  onProgramChange: (identity: string) => void
  onFileChange: (key: keyof DesignationBootstrapSelectedFiles, file: File | null) => void
}) {
  return (
    <>
      <section aria-labelledby="bootstrap-scope-title" className="rounded-lg border bg-slate-50 p-4">
        <h3 id="bootstrap-scope-title" className="font-semibold text-slate-950">Alcance fijo de la importación</h3>
        <dl className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
          <div><dt className="text-slate-600">Período</dt><dd className="font-semibold text-slate-950">{DESIGNATION_BOOTSTRAP_PERIOD}</dd></div>
          <div><dt className="text-slate-600">Vigente desde</dt><dd className="font-semibold text-slate-950">21 de agosto de 2026</dd></div>
        </dl>
        <input type="hidden" value={DESIGNATION_BOOTSTRAP_EFFECTIVE_DATE} readOnly />
      </section>

      <div className="space-y-1.5">
        <Label htmlFor="bootstrap-program">Programa académico *</Label>
        <select
          id="bootstrap-program"
          value={programIdentity}
          required
          disabled={disabled}
          aria-invalid={Boolean(fieldErrors.programIdentity)}
          aria-describedby={fieldErrors.programIdentity ? 'bootstrap-program-error' : 'bootstrap-program-description'}
          onChange={(event) => onProgramChange(event.target.value)}
          className="h-11 w-full rounded-lg border border-input bg-white px-3 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-invalid:border-red-600 md:text-sm"
        >
          <option value="">Seleccione un programa</option>
          {activePrograms.map((program) => <option key={program.id} value={program.code}>{program.code} · {program.name}</option>)}
        </select>
        <p id="bootstrap-program-description" className="text-xs text-slate-600">El catálogo, los grupos y las ofertas deben estar preparados para II/2026.</p>
        {fieldErrors.programIdentity && <p id="bootstrap-program-error" role="alert" className="text-sm text-red-700">{fieldErrors.programIdentity}</p>}
        {!activePrograms.length && <p role="alert" className="text-sm text-red-700">No hay programas activos. Registre o active uno en Gestión académica antes de importar.</p>}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <FileField
          id="bootstrap-official-workbook"
          label="Libro oficial de teoría y práctica"
          description="Archivo XLSX oficial que contiene horarios, aulas, grupos y docentes. Máximo 20 MiB."
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          required
          disabled={disabled}
          error={fieldErrors.officialWorkbook}
          onChange={(file) => onFileChange('officialWorkbook', file)}
        />
        <FileField
          id="bootstrap-salary-workbook"
          label="Libro salarial de práctica"
          description="Archivo XLSX que confirma las identidades y asignaciones de práctica. Máximo 20 MiB."
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          required
          disabled={disabled}
          error={fieldErrors.salaryWorkbook}
          onChange={(file) => onFileChange('salaryWorkbook', file)}
        />
      </div>

      <details className="rounded-lg border border-slate-200 bg-slate-50 p-3">
        <summary className="cursor-pointer font-medium text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-600">Opciones avanzadas</summary>
        <div className="mt-3">
          <FileField
            id="bootstrap-alias-resolution"
            label="Archivo técnico de equivalencias"
            description="Solo para migraciones preparadas previamente. La resolución normal se realiza en esta pantalla."
            accept=".json,application/json"
            disabled={disabled}
            onChange={(file) => onFileChange('aliasResolution', file)}
          />
        </div>
      </details>
    </>
  )
}
