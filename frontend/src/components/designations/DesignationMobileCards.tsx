import type { DesignationAdminItem } from '@/api/types'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { blockedReason, weeklyHoursOf } from '@/lib/designationListView'

import {
  ClassroomCell,
  RowActions,
  SchedulePills,
  StatusCell,
  SubjectCell,
  TeacherCell,
  type DesignationRowHandlers,
} from './DesignationListView'

function SkeletonCards() {
  return Array.from({ length: 3 }, (_, index) => (
    <Card key={index} aria-hidden="true" className="gap-3 p-4">
      <div className="flex items-center gap-3"><Skeleton className="size-7 rounded-full" /><Skeleton className="h-4 w-40" /></div>
      <Skeleton className="h-4 w-52" />
      <Skeleton className="h-5 w-36" />
      <Skeleton className="h-8 w-full" />
    </Card>
  ))
}

export function DesignationMobileCards({ items, loading, ...handlers }: { items: DesignationAdminItem[]; loading: boolean } & DesignationRowHandlers) {
  return (
    // ARIA table roles (one row per card) keep each designation a named row for assistive tech, like the desktop table.
    <div role="table" className="space-y-3" aria-label="Designaciones">
      {loading && <div role="status" className="sr-only">Cargando designaciones…</div>}
      {loading && <SkeletonCards />}
      {!loading && items.map((item) => {
        const reason = blockedReason(item)
        return (
          <Card key={item.id} role="row" className="p-4">
            <div role="cell" className="flex flex-col gap-3">
              <TeacherCell item={item} />
              <SubjectCell item={item} />
              <SchedulePills item={item} />
              <p className="text-sm text-muted-foreground">Aula: <ClassroomCell item={item} /></p>
              <p className="text-sm text-muted-foreground">
                Horas: <span className="font-medium tabular-nums text-foreground">{weeklyHoursOf(item)}</span> sem. ·{' '}
                <span className="font-medium tabular-nums text-foreground">{item.monthly_hours ?? '—'}</span> mes
              </p>
              <StatusCell item={item} />
              <RowActions item={item} labeledDelete {...handlers} />
              {reason && <p className="text-xs text-muted-foreground">{reason}</p>}
            </div>
          </Card>
        )
      })}
    </div>
  )
}
