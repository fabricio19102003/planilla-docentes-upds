import { Plus } from 'lucide-react'
import type { ReactNode } from 'react'

import { TONE_SOLID } from '@/components/shared/tones'
import { Button } from '@/components/ui/button'
import { semesterTone } from '@/lib/academicTones'
import type { SemesterTotals } from '@/lib/curriculumSummary'
import { cn } from '@/lib/utils'

/** One board column: semester badge, totals and the subject cards. */
export function SemesterColumn({ totals, onAdd, children }: { totals: SemesterTotals; onAdd?: () => void; children: ReactNode }) {
  const tone = semesterTone(totals.semester)
  return (
    <section aria-label={`Semestre ${totals.semester}`} className="flex w-[85vw] shrink-0 snap-start flex-col gap-3 rounded-2xl border bg-muted/40 p-3 sm:w-72">
      <header className="flex items-center gap-3">
        <span aria-hidden="true" className={cn('flex size-9 shrink-0 items-center justify-center rounded-xl text-base font-semibold', TONE_SOLID[tone])}>{totals.semester}</span>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-foreground">Semestre {totals.semester}</h3>
          <p className="text-xs tabular-nums text-muted-foreground">{totals.subjects} materias · {totals.hours} h · {totals.credits} cr</p>
        </div>
      </header>
      <ul className="flex flex-col gap-2">{children}</ul>
      {totals.subjects === 0 && !onAdd && <p className="rounded-lg border border-dashed px-3 py-4 text-center text-xs text-muted-foreground">Sin materias</p>}
      {onAdd && (
        <Button size="sm" variant="outline" className="w-full" onClick={onAdd}><Plus aria-hidden="true" />Agregar materia</Button>
      )}
    </section>
  )
}
