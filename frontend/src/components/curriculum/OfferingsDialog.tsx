import { CalendarPlus } from 'lucide-react'
import { useState } from 'react'

import { useGenerateOfferings } from '@/api/hooks/useAcademicRecords'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Dialog, DialogClose, DialogDescription, DialogFooter, DialogHeader, DialogPanel, DialogPopup, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { offeringSummary } from '@/lib/curriculumEditing'
import { apiErrorMessage } from '@/lib/userCredentials'

/** Generate a period's offerings from the curriculum. */
export function OfferingsDialog({ planId, open, onOpenChange }: { planId: number; open: boolean; onOpenChange: (open: boolean) => void }) {
  const [period, setPeriod] = useState('')
  const generate = useGenerateOfferings(planId)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Generar ofertas de un período</DialogTitle>
          <DialogDescription>Crea las ofertas con las materias, semestres y horas de esta malla. Las que ya existen no se tocan; después se ajustan en Gestión académica.</DialogDescription>
        </DialogHeader>
        <DialogPanel className="space-y-3">
          <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); generate.mutate(period.trim().toUpperCase()) }}>
            <div>
              <Label htmlFor="offerings-period">Período</Label>
              <Input id="offerings-period" value={period} placeholder="I/2027" onChange={(event) => setPeriod(event.target.value)} />
            </div>
            <Button type="submit" loading={generate.isPending} disabled={!period.trim()}><CalendarPlus aria-hidden="true" />Generar ofertas</Button>
          </form>
          {generate.isError && <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(generate.error, 'No se pudieron generar las ofertas. Usá el formato I/2027, II/2027, INV/2027 o VER/2027.')}</AlertTitle></Alert>}
          {generate.data && (
            <Alert variant="success" role="status">
              <AlertTitle>{offeringSummary(generate.data)}</AlertTitle>
              {generate.data.skipped.length > 0 && (
                <AlertDescription>
                  No generadas: {generate.data.skipped.map((item) => `${item.name} (sem. ${item.semester}: ${item.reason})`).join(' · ')}
                </AlertDescription>
              )}
            </Alert>
          )}
        </DialogPanel>
        <DialogFooter>
          <DialogClose render={<Button type="button" variant="outline" />}>Cerrar</DialogClose>
        </DialogFooter>
      </DialogPopup>
    </Dialog>
  )
}
