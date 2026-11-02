import { useState } from 'react'

import { Alert, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogDescription, DialogFooter, DialogHeader, DialogPanel, DialogPopup, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { slotFormProblem, slotPayload, type SlotForm, type SlotPayload } from '@/lib/curriculumEditing'

const selectClass = 'h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'

/** Add or edit one curriculum subject; `initial` null closes the dialog. */
export function SlotDialog({ initial, title, totalSemesters, pending, error, onSave, onClose }: {
  initial: SlotForm | null; title: string; totalSemesters: number; pending: boolean; error: string | null
  onSave: (payload: SlotPayload) => void; onClose: () => void
}) {
  return (
    <Dialog open={initial !== null} onOpenChange={(open) => { if (!open && !pending) onClose() }}>
      <DialogPopup className="max-w-lg">
        {initial && <SlotFormBody key={JSON.stringify(initial)} initial={initial} title={title} totalSemesters={totalSemesters}
          pending={pending} error={error} onSave={onSave} onClose={onClose} />}
      </DialogPopup>
    </Dialog>
  )
}

function SlotFormBody({ initial, title, totalSemesters, pending, error, onSave, onClose }: {
  initial: SlotForm; title: string; totalSemesters: number; pending: boolean; error: string | null
  onSave: (payload: SlotPayload) => void; onClose: () => void
}) {
  const [form, setForm] = useState(initial)
  const set = (patch: Partial<SlotForm>) => setForm((current) => ({ ...current, ...patch }))
  const problem = slotFormProblem(form)
  const number = (id: string, label: string, field: 'theory_hours' | 'practice_hours' | 'credits') => (
    <div>
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} inputMode="numeric" value={form[field]} onChange={(event) => set({ [field]: event.target.value })} />
    </div>
  )
  return (
    <form className="flex min-h-0 flex-1 flex-col" onSubmit={(event) => { event.preventDefault(); if (!problem) onSave(slotPayload(form)) }}>
      <DialogHeader>
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription>El cambio aplica a la malla vigente para todos los estudiantes y queda en el registro de actividad.</DialogDescription>
      </DialogHeader>
      <DialogPanel className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="sm:col-span-2">
            <Label htmlFor="slot-name">Nombre</Label>
            <Input id="slot-name" value={form.name} onChange={(event) => set({ name: event.target.value })} placeholder="Ej: Bioética" />
          </div>
          <div>
            <Label htmlFor="slot-semester">Semestre</Label>
            <select id="slot-semester" className={selectClass} value={form.semester} onChange={(event) => set({ semester: event.target.value })}>
              {Array.from({ length: totalSemesters }, (_, i) => <option key={i + 1} value={String(i + 1)}>{i + 1}</option>)}
            </select>
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <Checkbox checked={form.is_elective} onCheckedChange={(on) => set({ is_elective: Boolean(on) })} />
          Es una electiva (puede ir sin sigla)
        </label>
        <div>
          <Label htmlFor="slot-code">Sigla</Label>
          <Input id="slot-code" value={form.code} onChange={(event) => set({ code: event.target.value })} placeholder="Ej: BIO 0300" />
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          {number('slot-ht', 'Horas teóricas (HT)', 'theory_hours')}
          {number('slot-hp', 'Horas prácticas (HP)', 'practice_hours')}
          {number('slot-cr', 'Créditos (CR)', 'credits')}
        </div>
        {problem && <p className="text-sm text-muted-foreground">{problem}</p>}
        {error && <Alert variant="error" role="alert"><AlertTitle>{error}</AlertTitle></Alert>}
      </DialogPanel>
      <DialogFooter>
        <Button type="button" variant="outline" disabled={pending} onClick={onClose}>Cancelar</Button>
        <Button type="submit" loading={pending} disabled={problem !== null}>Guardar</Button>
      </DialogFooter>
    </form>
  )
}
