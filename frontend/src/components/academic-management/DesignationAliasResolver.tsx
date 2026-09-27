import { useState } from 'react'

import type {
  DesignationBootstrapAliasSelections,
  DesignationBootstrapResolutionContext,
} from '@/api/types'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { designationAliasSelectionState } from '@/lib/designationBootstrapState'

const selectClassName = 'h-11 w-full rounded-lg border border-input bg-white px-3 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 md:text-sm'

export function DesignationAliasResolver({
  context,
  pending,
  onCancel,
  onSubmit,
}: {
  context: DesignationBootstrapResolutionContext
  pending: boolean
  onCancel: () => void
  onSubmit: (selections: DesignationBootstrapAliasSelections) => void
}) {
  const [teacherSelections, setTeacherSelections] = useState<Record<string, string>>({})
  const [subjectSelections, setSubjectSelections] = useState<Record<string, string>>({})
  const { complete, selections } = designationAliasSelectionState(
    context, teacherSelections, subjectSelections,
  )

  return (
    <section aria-labelledby="alias-resolution-title" className="rounded-lg border-2 border-sky-300 bg-sky-50 p-4">
      <h3 id="alias-resolution-title" className="font-semibold text-sky-950">Resolver coincidencias exactas</h3>
      <p className="mt-1 max-w-2xl text-sm leading-5 text-sky-900">
        El sistema no elegirá por similitud. Revise cada origen y seleccione explícitamente su correspondencia.
      </p>

      <div className="mt-4 space-y-5">
        {context.teacher_resolutions.map((resolution, index) => {
          const id = `teacher-alias-${index}`
          return (
            <fieldset key={resolution.official_teacher_key} className="rounded-lg border border-sky-200 bg-white p-3">
              <legend className="px-1 text-sm font-semibold text-slate-950">Docente de práctica</legend>
              <p className="break-words text-sm text-slate-900">{resolution.official_teacher_display}</p>
              <p className="break-all text-xs text-slate-600">Clave oficial: {resolution.official_teacher_key}</p>
              <Label htmlFor={id} className="mt-3">Coincidencia en el libro salarial *</Label>
              <select
                id={id}
                value={teacherSelections[resolution.official_teacher_key] ?? ''}
                onChange={(event) => setTeacherSelections((current) => ({ ...current, [resolution.official_teacher_key]: event.target.value }))}
                aria-describedby={`${id}-description`}
                className={selectClassName}
              >
                <option value="">Seleccione una coincidencia</option>
                {resolution.candidates.map((candidate) => (
                  <option key={candidate.candidate_token} value={candidate.candidate_token}>
                    {candidate.salary_teacher_display} · {candidate.masked_ci} · {candidate.salary_teacher_key}
                  </option>
                ))}
              </select>
              <p id={`${id}-description`} className="mt-1 text-xs text-slate-600">El CI completo permanece protegido en el servidor.</p>
              {!resolution.candidates.length && <p role="alert" className="mt-2 text-sm text-red-700">No hay una identidad salarial elegible en el mismo semestre. Corrija los archivos fuente.</p>}
            </fieldset>
          )
        })}

        {context.subject_resolutions.map((resolution, index) => {
          const key = `${resolution.semester}:${resolution.salary_subject_key}`
          const id = `subject-alias-${index}`
          return (
            <fieldset key={key} className="rounded-lg border border-sky-200 bg-white p-3">
              <legend className="px-1 text-sm font-semibold text-slate-950">Materia de práctica · semestre {resolution.semester}</legend>
              <p className="break-words text-sm text-slate-900">{resolution.salary_subject_display}</p>
              <p className="break-all text-xs text-slate-600">Clave salarial: {resolution.salary_subject_key}</p>
              <Label htmlFor={id} className="mt-3">Materia oficial del mismo semestre *</Label>
              <select
                id={id}
                value={subjectSelections[key] ?? ''}
                onChange={(event) => setSubjectSelections((current) => ({ ...current, [key]: event.target.value }))}
                aria-describedby={`${id}-description`}
                className={selectClassName}
              >
                <option value="">Seleccione una materia</option>
                {resolution.candidates.map((candidate) => (
                  <option key={candidate.official_subject_key} value={candidate.official_subject_key}>
                    {candidate.official_subject_display} · {candidate.official_subject_key}
                  </option>
                ))}
              </select>
              <p id={`${id}-description`} className="mt-1 text-xs text-slate-600">Solo se muestran materias oficiales del semestre {resolution.semester}.</p>
              {!resolution.candidates.length && <p role="alert" className="mt-2 text-sm text-red-700">No hay una materia oficial elegible en este semestre. Corrija el catálogo fuente.</p>}
            </fieldset>
          )
        })}
      </div>

      {!context.teacher_resolutions.length && !context.subject_resolutions.length && (
        <p role="status" className="mt-4 text-sm text-slate-700">No hay coincidencias manuales pendientes para estos archivos.</p>
      )}
      <div className="mt-4 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="outline" onClick={onCancel} disabled={pending}>Volver</Button>
        <Button type="button" onClick={() => onSubmit(selections)} disabled={!complete || pending}>
          {pending ? 'Validando coincidencias…' : 'Usar estas coincidencias'}
        </Button>
      </div>
    </section>
  )
}
