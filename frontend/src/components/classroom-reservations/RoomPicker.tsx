import { Building2, Check, FlaskConical, Search, Users } from 'lucide-react'
import { useMemo, useState } from 'react'

import type { ClassroomDayRoom } from '@/api/hooks/useClassroomReservations'
import { EmptyState } from '@/components/shared/EmptyState'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { Input } from '@/components/ui/input'
import { SegmentedControl, SegmentedControlItem } from '@/components/ui/segmented-control'
import { Skeleton } from '@/components/ui/skeleton'
import {
  freeTimeLabel,
  groupRooms,
  occupancyBar,
  roomLocation,
  type RoomKind,
} from '@/lib/classroomReservationDay'
import { toMinutes, type BusyRange } from '@/lib/classroomReservations'
import { cn } from '@/lib/utils'

const KIND_OPTIONS: { value: RoomKind; label: string }[] = [
  { value: 'all', label: 'Todos' },
  { value: 'classroom', label: 'Aulas' },
  { value: 'laboratory', label: 'Laboratorios' },
]

const BAR_TONE = {
  class: 'bg-destructive/70',
  reservation: 'bg-warning',
  mine: 'bg-primary',
} as const

interface RoomPickerProps {
  rooms: ClassroomDayRoom[] | undefined
  dayStart: string
  dayEnd: string
  selectedId: number | null
  loading: boolean
  error: string | null
  onSelect: (id: number) => void
}

function OccupancyBar({ busy, dayStart, dayEnd }: { busy: BusyRange[]; dayStart: string; dayEnd: string }) {
  return (
    <div className="relative h-2 w-full overflow-hidden rounded-full bg-success/15" aria-hidden="true">
      {occupancyBar(busy, dayStart, dayEnd).map((segment, index) => (
        <i
          key={index}
          className={cn('absolute inset-y-0', BAR_TONE[segment.kind === 'reservation' && segment.mine ? 'mine' : segment.kind])}
          style={{ left: `${segment.left}%`, width: `${segment.width}%` }}
        />
      ))}
    </div>
  )
}

function RoomCard({ entry, dayStart, dayEnd, selected, onSelect }: {
  entry: ClassroomDayRoom
  dayStart: string
  dayEnd: string
  selected: boolean
  onSelect: () => void
}) {
  const { classroom } = entry
  const location = roomLocation(classroom)
  const total = (toMinutes(dayEnd) ?? 0) - (toMinutes(dayStart) ?? 0)
  const isLab = classroom.classroom_type === 'laboratory'
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
      className={cn(
        'relative flex min-w-0 flex-col gap-1.5 rounded-lg border bg-card p-3 text-left outline-none transition-colors hover:border-primary/45 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1',
        selected && 'border-primary bg-primary/5 ring-1 ring-primary',
      )}
    >
      <span className="flex flex-wrap items-center gap-x-2 gap-y-1 pr-6">
        <span className="text-sm font-semibold">{classroom.name}</span>
        {isLab && (
          <span className="inline-flex items-center gap-1 rounded-full bg-tone-violet/12 px-2 text-xs font-semibold text-tone-violet-foreground">
            <FlaskConical className="size-3" aria-hidden="true" />Laboratorio
          </span>
        )}
      </span>
      <span className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
        {location && <span className="inline-flex items-center gap-1"><Building2 className="size-3.5" aria-hidden="true" />{location}</span>}
        <span className="inline-flex items-center gap-1"><Users className="size-3.5" aria-hidden="true" />{classroom.capacity ?? '—'}<span className="sr-only"> personas de capacidad</span></span>
      </span>
      <OccupancyBar busy={entry.busy} dayStart={dayStart} dayEnd={dayEnd} />
      <span className={cn('text-xs font-semibold', entry.free_minutes > 0 ? 'text-success-foreground' : 'text-warning-foreground')}>
        {freeTimeLabel(entry.free_minutes, total)}
      </span>
      {selected && (
        <span className="absolute right-2.5 top-2.5 grid size-5 place-items-center rounded-full bg-primary text-primary-foreground" aria-hidden="true">
          <Check className="size-3" />
        </span>
      )}
    </button>
  )
}

export function RoomPicker({ rooms, dayStart, dayEnd, selectedId, loading, error, onSelect }: RoomPickerProps) {
  const [query, setQuery] = useState('')
  const [kind, setKind] = useState<RoomKind>('all')
  const entries = useMemo(() => rooms ?? [], [rooms])
  const groups = useMemo(() => {
    const byId = new Map(entries.map((entry) => [entry.classroom.id, entry]))
    return groupRooms(entries.map((entry) => entry.classroom), { query, kind })
      .map((group) => ({ ...group, entries: group.rooms.map((room) => byId.get(room.id) as ClassroomDayRoom) }))
  }, [entries, query, kind])

  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 z-10 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
        <Input
          type="search"
          aria-label="Buscar aula o laboratorio"
          placeholder="Buscar aula o laboratorio…"
          inputClassName="pl-9"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>
      <SegmentedControl aria-label="Tipo de espacio" className="max-w-full">
        {KIND_OPTIONS.map((option) => (
          <SegmentedControlItem
            key={option.value}
            aria-pressed={kind === option.value}
            data-pressed={kind === option.value ? '' : undefined}
            onClick={() => setKind(option.value)}
          >
            {option.label}
          </SegmentedControlItem>
        ))}
      </SegmentedControl>

      <div className="max-h-[32rem] space-y-4 overflow-y-auto pr-1 xl:max-h-[46rem]">
        {loading && <Skeleton className="h-48 w-full rounded-lg" />}
        {error && <Alert variant="error" role="alert"><AlertTitle>{error}</AlertTitle></Alert>}
        {!loading && !error && groups.length === 0 && (
          <EmptyState title="Sin resultados" description="Ningún aula o laboratorio coincide con la búsqueda." />
        )}
        {groups.map((group) => (
          <section key={group.key} aria-label={group.title} className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{group.title}</h3>
            <div className="grid gap-2 sm:grid-cols-2">
              {group.entries.map((entry) => (
                <RoomCard
                  key={entry.classroom.id}
                  entry={entry}
                  dayStart={dayStart}
                  dayEnd={dayEnd}
                  selected={entry.classroom.id === selectedId}
                  onSelect={() => onSelect(entry.classroom.id)}
                />
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}
