import { useState } from 'react'

import { useDeleteDesignation, useFinalizeDesignation } from '@/api/hooks/useDesignationAdmin'
import type { DesignationAdminItem, DesignationAdminMutation } from '@/api/types'
import { DesignationProblems } from '@/components/designations/DesignationProblems'
import { Button } from '@/components/ui/button'
import { Dialog, DialogDescription, DialogFooter, DialogHeader, DialogPanel, DialogPopup, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { getTodayInBolivia } from '@/lib/boliviaDates'
import { errorDetails, formatDate, type ProblemDetails } from '@/lib/designationAdminState'

function describe(item: DesignationAdminItem) {
  return `${item.subject} · ${item.group_code} · ${item.teacher_name}`
}

/** Default last day: today, kept inside the designation's own dates. */
function defaultEndDate(item: DesignationAdminItem) {
  const today = getTodayInBolivia()
  if (item.contract_end_date && today > item.contract_end_date) return item.contract_end_date
  if (item.contract_start_date && today < item.contract_start_date) return item.contract_start_date
  return today
}

export function FinalizeDesignationDialog({ item, onClose, onDone }: {
  item: DesignationAdminItem
  onClose: () => void
  onDone: (result: DesignationAdminMutation) => void
}) {
  const [endDate, setEndDate] = useState(() => defaultEndDate(item))
  const [problems, setProblems] = useState<ProblemDetails | null>(null)
  const finalize = useFinalizeDesignation()

  const confirm = () => {
    if (!endDate) {
      setProblems({ title: 'Elegí el último día que dicta la materia.', items: [] })
      return
    }
    finalize.mutate({ id: item.id, endDate }, {
      onSuccess: (result) => onDone(result!),
      onError: (error) => setProblems(errorDetails(error, 'No se pudo finalizar la designación.')),
    })
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogPopup>
        <DialogHeader>
          <DialogTitle>Finalizar designación</DialogTitle>
          <DialogDescription>{describe(item)}</DialogDescription>
        </DialogHeader>
        <DialogPanel className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">
            Usalo cuando el docente deja de dictar la materia. Se le paga hasta el día que elijas (inclusive) y la
            designación queda guardada en el historial.
          </p>
          <div>
            <Label htmlFor="finalize-end-date">Último día que dicta la materia</Label>
            <Input
              id="finalize-end-date"
              type="date"
              value={endDate}
              min={item.contract_start_date ?? undefined}
              max={item.contract_end_date ?? undefined}
              onChange={(event) => { setEndDate(event.target.value); setProblems(null) }}
            />
            {item.contract_end_date && (
              <p className="mt-1 text-xs text-muted-foreground">Hoy termina el {formatDate(item.contract_end_date)}; solo podés adelantar el fin.</p>
            )}
          </div>
          <DesignationProblems problems={problems} />
        </DialogPanel>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>Cancelar</Button>
          <Button type="button" onClick={confirm} disabled={finalize.isPending}>
            {finalize.isPending ? 'Finalizando…' : 'Finalizar'}
          </Button>
        </DialogFooter>
      </DialogPopup>
    </Dialog>
  )
}

export function DeleteDesignationDialog({ item, onClose, onDone, onFinalizeInstead }: {
  item: DesignationAdminItem
  onClose: () => void
  onDone: () => void
  onFinalizeInstead: (item: DesignationAdminItem) => void
}) {
  const [problems, setProblems] = useState<ProblemDetails | null>(null)
  const remove = useDeleteDesignation()
  const allowed = item.actions.delete.allowed
  const canFinalize = item.actions.finalize.allowed

  const confirm = () => remove.mutate(item.id, {
    onSuccess: onDone,
    onError: (error) => setProblems(errorDetails(error, 'No se pudo eliminar la designación.')),
  })

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogPopup>
        <DialogHeader>
          <DialogTitle>{allowed ? '¿Eliminar esta designación?' : 'Esta designación no se puede eliminar'}</DialogTitle>
          <DialogDescription>{describe(item)}</DialogDescription>
        </DialogHeader>
        <DialogPanel className="flex flex-col gap-3 text-sm">
          {allowed ? (
            <p>Se borra por completo. Usalo solo si se cargó por error: nadie registró asistencia, no tiene contrato y no entró en ninguna planilla.</p>
          ) : (
            <>
              <p className="font-medium">{item.actions.delete.reason}</p>
              <p className="text-muted-foreground">
                Eliminar es solo para designaciones cargadas por error. Como esta ya se usó, para que deje de pagarse
                finalizala en la fecha en que el docente dejó la materia.
              </p>
            </>
          )}
          <DesignationProblems problems={problems} />
        </DialogPanel>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>{allowed ? 'Cancelar' : 'Cerrar'}</Button>
          {allowed ? (
            <Button type="button" variant="destructive" onClick={confirm} disabled={remove.isPending}>
              {remove.isPending ? 'Eliminando…' : 'Eliminar'}
            </Button>
          ) : canFinalize && (
            <Button type="button" onClick={() => onFinalizeInstead(item)}>Finalizar en su lugar</Button>
          )}
        </DialogFooter>
      </DialogPopup>
    </Dialog>
  )
}
