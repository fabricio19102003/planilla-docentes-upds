import { ArrowDown, ArrowUp, Pencil, Trash2 } from 'lucide-react'

import { StatusBadge } from '@/components/shared/StatusBadge'
import { TONE_CHIP, TONE_DOT, type Tone } from '@/components/shared/tones'
import { Button } from '@/components/ui/button'
import type { CurriculumSlot } from '@/lib/academicRecordsState'
import { hoursSplit } from '@/lib/curriculumSummary'
import { cn } from '@/lib/utils'

export interface SubjectCardActions {
  canMoveUp: boolean
  canMoveDown: boolean
  pending: boolean
  onMove: (direction: 'up' | 'down') => void
  onEdit: () => void
  onRemove: () => void
}

/** Compact subject card: semester accent, name, code, theory/practice bar and credits chip. */
export function SubjectCard({ subject, tone, actions }: { subject: CurriculumSlot; tone: Tone; actions?: SubjectCardActions }) {
  const split = hoursSplit(subject.theory_hours, subject.practice_hours)
  return (
    <li className="group relative overflow-hidden rounded-lg border bg-card p-3 pl-4 text-sm shadow-xs/5">
      <span aria-hidden="true" className={cn('absolute inset-y-0 left-0 w-1', TONE_DOT[tone])} />
      <p className="line-clamp-2 font-medium leading-snug text-foreground">{subject.name}</p>
      <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
        {subject.is_elective && <StatusBadge tone="violet">Electiva</StatusBadge>}
        {subject.code && <span className="font-mono">{subject.code}</span>}
      </div>
      <div className="mt-2.5 space-y-1">
        <div
          role="img"
          aria-label={`Horas teóricas ${subject.theory_hours}, horas prácticas ${subject.practice_hours}`}
          className="flex h-1.5 w-full overflow-hidden rounded-full bg-muted"
        >
          <span className="h-full bg-primary" style={{ width: `${split.theory}%` }} />
          <span className="h-full bg-success" style={{ width: `${split.practice}%` }} />
        </div>
        <div className="flex items-center justify-between gap-2 text-xs tabular-nums text-muted-foreground">
          <p>
            <span title="Horas teóricas"><span aria-hidden="true">T {subject.theory_hours}</span><span className="sr-only">HT {subject.theory_hours}</span></span>
            {' · '}
            <span title="Horas prácticas"><span aria-hidden="true">P {subject.practice_hours}</span><span className="sr-only">HP {subject.practice_hours}</span></span>
          </p>
          <span className={cn('rounded-full px-2 py-0.5 font-medium', TONE_CHIP[tone])}>
            {subject.credits}<span aria-hidden="true"> cr</span><span className="sr-only"> créditos</span>
          </span>
        </div>
      </div>
      {actions && (
        <div className="mt-2 flex justify-end gap-0.5 border-t pt-2 transition-opacity sm:opacity-0 sm:group-hover:opacity-100 sm:focus-within:opacity-100">
          <Button size="icon-sm" variant="ghost" aria-label={`Subir ${subject.name}`} disabled={!actions.canMoveUp || actions.pending}
            onClick={() => actions.onMove('up')}><ArrowUp aria-hidden="true" /></Button>
          <Button size="icon-sm" variant="ghost" aria-label={`Bajar ${subject.name}`} disabled={!actions.canMoveDown || actions.pending}
            onClick={() => actions.onMove('down')}><ArrowDown aria-hidden="true" /></Button>
          <Button size="icon-sm" variant="ghost" aria-label={`Editar ${subject.name}`} onClick={actions.onEdit}><Pencil aria-hidden="true" /></Button>
          <Button size="icon-sm" variant="ghost" aria-label={`Quitar ${subject.name}`} onClick={actions.onRemove}><Trash2 aria-hidden="true" /></Button>
        </div>
      )}
    </li>
  )
}
