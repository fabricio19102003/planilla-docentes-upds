import { Pencil, Square, Trash2 } from 'lucide-react'

import type { DesignationAdminItem } from '@/api/types'
import { PersonAvatar } from '@/components/shared/PersonAvatar'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { TableCard } from '@/components/shared/TableCard'
import { TONE_CHIP, type Tone } from '@/components/shared/tones'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tooltip, TooltipPopup, TooltipTrigger } from '@/components/ui/tooltip'
import { semesterTone, shiftFromGroupCode, shiftLabel, shiftTone } from '@/lib/academicTones'
import { formatSlots } from '@/lib/designationAdminState'
import { roomLabel, type DesignationRoomItem } from '@/lib/designationRoomImport'
import { contractText, displayName, semesterChipLabel, weeklyHoursOf } from '@/lib/designationListView'
import { cn } from '@/lib/utils'

export interface DesignationRowHandlers {
  onEdit: (item: DesignationAdminItem) => void
  onFinalize: (item: DesignationAdminItem) => void
  onDelete: (item: DesignationAdminItem) => void
}

function Chip({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  return <Badge variant="outline" size="sm" className={cn('border-transparent', TONE_CHIP[tone])}>{children}</Badge>
}

export function TeacherCell({ item }: { item: DesignationAdminItem }) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <PersonAvatar name={displayName(item.teacher_name)} colorKey={item.teacher_ci} size="sm" />
      <div className="min-w-0">
        <p className="truncate font-medium text-foreground">{displayName(item.teacher_name)}</p>
        <p className="text-xs text-muted-foreground">CI {item.teacher_ci}</p>
      </div>
    </div>
  )
}

export function SubjectCell({ item }: { item: DesignationAdminItem }) {
  const practice = item.designation_type === 'practice'
  const shift = shiftFromGroupCode(item.group_code)
  return (
    <div className="min-w-0 space-y-1.5">
      <p className="font-medium text-foreground">{item.subject}</p>
      <div className="flex flex-wrap items-center gap-1">
        <Chip tone={semesterTone(item.semester)}>{semesterChipLabel(item.semester)}</Chip>
        <Chip tone={shiftTone(shift)}>{shift ? `${item.group_code} · ${shiftLabel(shift)}` : `Grupo ${item.group_code}`}</Chip>
        <Chip tone={practice ? 'cyan' : 'violet'}>{practice ? 'Práctica' : 'Teoría'}</Chip>
      </div>
    </div>
  )
}

export function SchedulePills({ item }: { item: DesignationAdminItem }) {
  const text = formatSlots(item.schedule_json)
  if (!item.schedule_json?.length) return <span className="text-xs text-muted-foreground">{text}</span>
  return (
    <div className="flex flex-wrap gap-1">
      {text.split(' · ').map((slot) => (
        <span key={slot} className="whitespace-nowrap rounded-md bg-muted px-1.5 py-0.5 text-xs tabular-nums text-foreground">{slot}</span>
      ))}
    </div>
  )
}

export function ClassroomCell({ item }: { item: DesignationRoomItem }) {
  const room = item.classroom
  return room
    ? <span className="text-sm font-medium text-foreground">{roomLabel(room)}</span>
    : <span className="text-sm text-muted-foreground">{roomLabel(null)}</span>
}

export function StatusCell({ item }: { item: DesignationAdminItem }) {
  const active = item.status === 'active'
  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-center gap-1">
        <StatusBadge tone={active ? 'success' : 'neutral'}>{active ? 'Vigente' : 'Finalizada'}</StatusBadge>
        {item.has_contract && <StatusBadge tone="info">Contrato emitido</StatusBadge>}
      </div>
      <p className="text-xs text-muted-foreground">{contractText(item)}</p>
    </div>
  )
}

export function RowActions({ item, onEdit, onFinalize, onDelete, labeledDelete = false }: { item: DesignationAdminItem; labeledDelete?: boolean } & DesignationRowHandlers) {
  const deleteLabel = `Eliminar ${item.subject} ${item.group_code}`
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Button size="sm" variant="outline" onClick={() => onEdit(item)}><Pencil aria-hidden="true" />Editar</Button>
      <Button size="sm" variant="outline" disabled={!item.actions.finalize.allowed} title={item.actions.finalize.reason ?? undefined} onClick={() => onFinalize(item)}>
        <Square aria-hidden="true" />Finalizar
      </Button>
      {labeledDelete ? (
        <Button size="sm" variant="destructive-outline" aria-label={deleteLabel} onClick={() => onDelete(item)}>
          <Trash2 aria-hidden="true" />Eliminar
        </Button>
      ) : (
        <Tooltip>
          <TooltipTrigger
            render={(
              <Button size="icon-sm" variant="ghost" className="text-destructive-foreground" aria-label={deleteLabel} onClick={() => onDelete(item)}>
                <Trash2 aria-hidden="true" />
              </Button>
            )}
          />
          <TooltipPopup>Eliminar (solo si se cargó por error)</TooltipPopup>
        </Tooltip>
      )}
    </div>
  )
}

function SkeletonRows() {
  return Array.from({ length: 5 }, (_, index) => (
    <TableRow key={index} aria-hidden="true">
      <TableCell className="px-4 py-3"><div className="flex items-center gap-3"><Skeleton className="size-7 rounded-full" /><div className="space-y-1.5"><Skeleton className="h-4 w-32" /><Skeleton className="h-3 w-16" /></div></div></TableCell>
      <TableCell className="px-4 py-3"><div className="space-y-1.5"><Skeleton className="h-4 w-44" /><Skeleton className="h-4 w-36" /></div></TableCell>
      <TableCell className="px-4 py-3"><Skeleton className="h-5 w-28" /></TableCell>
      <TableCell className="px-4 py-3"><Skeleton className="h-4 w-16" /></TableCell>
      <TableCell className="px-4 py-3"><Skeleton className="ml-auto h-4 w-12" /></TableCell>
      <TableCell className="px-4 py-3"><div className="space-y-1.5"><Skeleton className="h-5 w-20" /><Skeleton className="h-3 w-32" /></div></TableCell>
      <TableCell className="px-4 py-3"><Skeleton className="ml-auto h-7 w-40" /></TableCell>
    </TableRow>
  ))
}

export function DesignationTable({ items, loading, ...handlers }: { items: DesignationAdminItem[]; loading: boolean } & DesignationRowHandlers) {
  return (
    <TableCard tableClassName="min-w-[980px]">
      <TableHeader>
        <TableRow className="bg-muted/40 hover:bg-muted/40">
          <TableHead className="px-4">Docente</TableHead>
          <TableHead className="px-4">Materia</TableHead>
          <TableHead className="px-4">Horario</TableHead>
          <TableHead className="px-4">Aula</TableHead>
          <TableHead className="px-4 text-right">Horas<br />sem. / mes</TableHead>
          <TableHead className="px-4">Estado y contrato</TableHead>
          <TableHead className="px-4 text-right">Acciones</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {loading && <TableRow><TableCell colSpan={7} role="status" className="sr-only">Cargando designaciones…</TableCell></TableRow>}
        {loading && <SkeletonRows />}
        {!loading && items.map((item) => (
          <TableRow key={item.id}>
            <TableCell className="px-4 py-3"><TeacherCell item={item} /></TableCell>
            <TableCell className="min-w-56 px-4 py-3 whitespace-normal"><SubjectCell item={item} /></TableCell>
            <TableCell className="px-4 py-3 whitespace-normal"><div className="max-w-44"><SchedulePills item={item} /></div></TableCell>
            <TableCell className="px-4 py-3"><ClassroomCell item={item} /></TableCell>
            <TableCell className="px-4 py-3 text-right tabular-nums">{weeklyHoursOf(item)} / {item.monthly_hours ?? '—'}</TableCell>
            <TableCell className="px-4 py-3"><StatusCell item={item} /></TableCell>
            <TableCell className="px-4 py-3"><div className="flex justify-end"><RowActions item={item} {...handlers} /></div></TableCell>
          </TableRow>
        ))}
      </TableBody>
    </TableCard>
  )
}
