import { useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { FileCheck2, Upload } from 'lucide-react'

import {
  applyDesignationBootstrap,
  createDesignationBootstrapAliasArtifact,
  getDesignationBootstrapResolutionContext,
  previewDesignationBootstrap,
} from '@/api/academicManagement'
import type {
  AcademicProgram,
  DesignationBootstrapAliasSelections,
  DesignationBootstrapApplyResult,
  DesignationBootstrapPreview as BootstrapPreview,
  DesignationBootstrapResolutionContext,
} from '@/api/types'
import { DesignationAliasResolver } from '@/components/academic-management/DesignationAliasResolver'
import {
  DesignationBootstrapFields,
  type DesignationBootstrapSelectedFiles,
} from '@/components/academic-management/DesignationBootstrapFields'
import {
  DesignationBootstrapPreview,
} from '@/components/academic-management/DesignationBootstrapPreview'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'

interface DesignationBootstrapDialogProps {
  programs: AcademicProgram[]
  onContinue: (draftId: number) => void
}

const emptyFiles: DesignationBootstrapSelectedFiles = {
  officialWorkbook: null,
  salaryWorkbook: null,
  aliasResolution: null,
}

function requestErrorMessage(error: unknown) {
  const status = (error as { response?: { status?: number } })?.response?.status
  if (status === 413) return 'Uno de los archivos supera el tamaño permitido. Cada libro XLSX debe pesar 20 MiB o menos.'
  if (status === 415) return 'Seleccione libros en formato XLSX. El archivo técnico opcional debe tener el formato indicado.'
  if (status === 409) return 'Los archivos o las opciones cambiaron o vencieron. Genere la resolución nuevamente.'
  if (status === 400 || status === 422) return 'Los archivos no cumplen el formato oficial requerido. Revise las fuentes y vuelva a intentar.'
  return 'No se pudo procesar la importación. Compruebe su conexión e intente nuevamente.'
}

export function DesignationBootstrapDialog({ programs, onContinue }: DesignationBootstrapDialogProps) {
  const queryClient = useQueryClient()
  const activePrograms = programs.filter((program) => program.active)
  const [open, setOpen] = useState(false)
  const [programIdentity, setProgramIdentity] = useState('')
  const [files, setFiles] = useState<DesignationBootstrapSelectedFiles>(emptyFiles)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [preview, setPreview] = useState<BootstrapPreview | null>(null)
  const [resolutionContext, setResolutionContext] = useState<DesignationBootstrapResolutionContext | null>(null)
  const [result, setResult] = useState<DesignationBootstrapApplyResult | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [requestError, setRequestError] = useState<string | null>(null)
  const requestGeneration = useRef(0)

  const previewMutation = useMutation({ mutationFn: previewDesignationBootstrap })
  const resolutionMutation = useMutation({ mutationFn: getDesignationBootstrapResolutionContext })
  const artifactMutation = useMutation({
    mutationFn: ({
      context,
      selections,
    }: {
      context: DesignationBootstrapResolutionContext
      selections: DesignationBootstrapAliasSelections
    }) => createDesignationBootstrapAliasArtifact({
      officialWorkbook: files.officialWorkbook!,
      salaryWorkbook: files.salaryWorkbook!,
    }, context.resolution_token, selections),
  })
  const applyMutation = useMutation({
    mutationFn: ({ digest }: { digest: string }) => applyDesignationBootstrap({
      officialWorkbook: files.officialWorkbook!,
      salaryWorkbook: files.salaryWorkbook!,
      aliasResolution: files.aliasResolution ?? undefined,
      programIdentity,
    }, digest),
  })

  const clearReview = () => {
    setPreview(null)
    setResolutionContext(null)
    setResult(null)
    setConfirmed(false)
    setRequestError(null)
  }

  const reset = () => {
    requestGeneration.current += 1
    setProgramIdentity('')
    setFiles(emptyFiles)
    setFieldErrors({})
    clearReview()
    previewMutation.reset()
    resolutionMutation.reset()
    artifactMutation.reset()
    applyMutation.reset()
  }

  const updateFile = (key: keyof DesignationBootstrapSelectedFiles, file: File | null) => {
    requestGeneration.current += 1
    setFiles((current) => ({ ...current, [key]: file }))
    setFieldErrors((current) => ({ ...current, [key]: '' }))
    clearReview()
  }

  const validateSources = () => {
    const errors: Record<string, string> = {}
    if (!programIdentity) errors.programIdentity = 'Seleccione el programa que recibirá la importación.'
    if (!files.officialWorkbook) errors.officialWorkbook = 'Seleccione el libro oficial de teoría y práctica.'
    if (!files.salaryWorkbook) errors.salaryWorkbook = 'Seleccione el libro salarial de práctica.'
    setFieldErrors(errors)
    return Object.keys(errors).length === 0
  }

  const generatePreview = async (aliasResolution = files.aliasResolution) => {
    if (!validateSources()) return
    const generation = ++requestGeneration.current
    setRequestError(null)
    setResult(null)
    setConfirmed(false)
    setResolutionContext(null)
    try {
      const nextPreview = await previewMutation.mutateAsync({
        officialWorkbook: files.officialWorkbook!,
        salaryWorkbook: files.salaryWorkbook!,
        aliasResolution: aliasResolution ?? undefined,
        programIdentity,
      })
      if (generation !== requestGeneration.current) return
      setPreview(nextPreview)
    } catch (error) {
      if (generation !== requestGeneration.current) return
      setPreview(null)
      setRequestError(requestErrorMessage(error))
    }
  }

  const startResolution = async () => {
    if (!files.officialWorkbook || !files.salaryWorkbook) return
    const generation = ++requestGeneration.current
    setRequestError(null)
    try {
      const context = await resolutionMutation.mutateAsync({
        officialWorkbook: files.officialWorkbook,
        salaryWorkbook: files.salaryWorkbook,
      })
      if (generation !== requestGeneration.current) return
      if (!context.teacher_resolutions.length && !context.subject_resolutions.length) {
        setRequestError('No hay coincidencias manuales disponibles. Corrija los archivos fuente y genere otra vista previa.')
        return
      }
      setResolutionContext(context)
    } catch (error) {
      if (generation !== requestGeneration.current) return
      setRequestError(requestErrorMessage(error))
    }
  }

  const completeResolution = async (selections: DesignationBootstrapAliasSelections) => {
    if (!resolutionContext) return
    const generation = ++requestGeneration.current
    setRequestError(null)
    try {
      const artifact = await artifactMutation.mutateAsync({ context: resolutionContext, selections })
      if (generation !== requestGeneration.current) return
      const aliasFile = new File([artifact], 'designation-alias-v2.json', { type: 'application/json' })
      setFiles((current) => ({ ...current, aliasResolution: aliasFile }))
      await generatePreview(aliasFile)
    } catch (error) {
      if (generation !== requestGeneration.current) return
      setRequestError(requestErrorMessage(error))
    }
  }

  const applyImport = async () => {
    if (!preview?.can_apply || !confirmed) return
    const generation = ++requestGeneration.current
    setRequestError(null)
    try {
      const applied = await applyMutation.mutateAsync({ digest: preview.preview_digest })
      if (generation !== requestGeneration.current) return
      setResult(applied)
      await queryClient.invalidateQueries({ queryKey: ['academic-management', 'schedule-drafts'] })
    } catch (error) {
      if (generation !== requestGeneration.current) return
      setRequestError(requestErrorMessage(error))
    }
  }

  const busy = previewMutation.isPending || resolutionMutation.isPending
    || artifactMutation.isPending || applyMutation.isPending
  const busyStatus = previewMutation.isPending
    ? 'Analizando los archivos y el catálogo.'
    : resolutionMutation.isPending
      ? 'Buscando coincidencias exactas.'
      : artifactMutation.isPending
        ? 'Preparando las equivalencias seleccionadas.'
        : applyMutation.isPending
          ? 'Creando el borrador de horarios.'
          : ''

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => {
      if (!nextOpen && busy) return
      if (nextOpen && !programIdentity && activePrograms.length === 1) setProgramIdentity(activePrograms[0].code)
      if (!nextOpen) reset()
      setOpen(nextOpen)
    }}>
      <DialogTrigger asChild>
        <Button variant="outline"><Upload aria-hidden="true" />Importación inicial</Button>
      </DialogTrigger>
      <DialogContent aria-busy={busy} showCloseButton={false} className="max-h-[92vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Importación inicial de designaciones</DialogTitle>
          <DialogDescription className="max-w-2xl leading-5">
            Cargue una sola vez el libro oficial de teoría y práctica junto con el libro salarial de práctica. Los archivos y las decisiones permanecen en la memoria de este navegador hasta confirmar.
          </DialogDescription>
        </DialogHeader>
        <p role="status" aria-live="polite" className="sr-only">{busyStatus}</p>

        {result ? (
          <section role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 p-5">
            <FileCheck2 aria-hidden="true" className="size-7 text-emerald-700" />
            <h3 className="mt-3 text-lg font-semibold text-emerald-950">Importación aplicada correctamente</h3>
            <p className="mt-1 text-sm leading-5 text-emerald-900">
              Se creó el borrador con {result.theory_block_count + result.practice_block_count} bloques y {result.theory_assignment_count + result.practice_assignment_count} asignaciones. Todavía no se publicó ninguna revisión.
            </p>
            <Button className="mt-4 w-full sm:w-auto" onClick={() => {
              onContinue(result.draft_id)
              setOpen(false)
              reset()
            }}>Continuar en el borrador</Button>
          </section>
        ) : (
          <>
            <DesignationBootstrapFields
              activePrograms={activePrograms}
              programIdentity={programIdentity}
              fieldErrors={fieldErrors}
              disabled={busy}
              onProgramChange={(identity) => {
                requestGeneration.current += 1
                setProgramIdentity(identity)
                setFieldErrors((current) => ({ ...current, programIdentity: '' }))
                clearReview()
              }}
              onFileChange={updateFile}
            />

            {requestError && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{requestError}</p>}
            {previewMutation.isPending && <p role="status" aria-busy="true" className="rounded-lg border bg-slate-50 p-3 text-sm text-slate-700">Analizando ambos libros, el catálogo y la disponibilidad…</p>}
            {preview && !resolutionContext && (
              <DesignationBootstrapPreview
                preview={preview}
                resolving={resolutionMutation.isPending}
                onResolve={() => void startResolution()}
              />
            )}
            {resolutionContext && (
              <DesignationAliasResolver
                key={resolutionContext.resolution_token}
                context={resolutionContext}
                pending={artifactMutation.isPending || previewMutation.isPending}
                onCancel={() => setResolutionContext(null)}
                onSubmit={(selections) => void completeResolution(selections)}
              />
            )}

            {preview?.can_apply && !resolutionContext && (
              <section aria-labelledby="bootstrap-confirm-title" className="rounded-lg border-2 border-sky-300 bg-sky-50 p-4">
                <h3 id="bootstrap-confirm-title" className="font-semibold text-sky-950">Confirmación final</h3>
                <p className="mt-1 text-sm leading-5 text-sky-900">
                  Se aplicarán {preview.planned.theory_block_count + preview.planned.practice_block_count} bloques y {preview.planned.theory_assignment_count + preview.planned.practice_assignment_count} asignaciones, vigentes desde el 21 de agosto de 2026.
                </p>
                <label className="mt-3 flex min-h-11 cursor-pointer items-start gap-3 rounded-md border border-sky-200 bg-white p-3 text-sm text-slate-900 focus-within:ring-3 focus-within:ring-sky-600/30">
                  <input type="checkbox" checked={confirmed} disabled={busy} onChange={(event) => setConfirmed(event.target.checked)} className="mt-0.5 size-5 shrink-0 accent-sky-700" />
                  <span>Confirmo la fecha efectiva y los conteos anteriores. Entiendo que se creará un borrador editable y no se publicará automáticamente.</span>
                </label>
              </section>
            )}

            {!resolutionContext && (
              <div className="flex flex-col-reverse gap-2 border-t pt-4 sm:flex-row sm:justify-end">
                <DialogClose asChild><Button variant="outline" disabled={busy}>Cancelar</Button></DialogClose>
                {!preview?.can_apply && (
                  <Button onClick={() => void generatePreview()} disabled={busy || !activePrograms.length}>
                    {previewMutation.isPending ? 'Generando vista previa…' : preview ? 'Generar nueva vista previa' : 'Generar vista previa'}
                  </Button>
                )}
                {preview?.can_apply && (
                  <Button onClick={() => void applyImport()} disabled={!confirmed || busy}>
                    {applyMutation.isPending ? 'Aplicando importación…' : 'Confirmar y crear borrador'}
                  </Button>
                )}
              </div>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
