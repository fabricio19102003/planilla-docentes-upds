import { useState } from 'react'
import { ChevronsUpDown, X } from 'lucide-react'

import { useAcademicCollection } from '@/api/hooks/useAcademicManagement'
import { Button } from '@/components/ui/button'
import {
  Combobox,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
  ComboboxPopup,
  ComboboxTrigger,
} from '@/components/ui/combobox'
import { activeClassrooms } from '@/lib/designationRoomImport'
import { cn } from '@/lib/utils'

/** Searchable picker of active classrooms; the clear button leaves the designation with no classroom. */
export function ClassroomCombobox({ id, value, current, onChange }: {
  id: string
  value: number | null
  /** The room already stored, shown while the catalog loads or when it was deactivated since. */
  current?: { id: number; name: string } | null
  onChange: (classroomId: number | null) => void
}) {
  const [open, setOpen] = useState(false)
  const catalog = useAcademicCollection('classrooms')
  const rooms = activeClassrooms([...(catalog.data ?? [])])
  const selected = rooms.find((room) => room.id === value) ?? null
  const stored = value !== null && current && current.id === value ? current.name : null
  const label = selected ? selected.name : stored
  return (
    <div className="mt-1 flex items-center gap-1">
      <Combobox
        items={rooms}
        open={open}
        onOpenChange={setOpen}
        value={selected}
        onValueChange={(room) => { if (room) { onChange(room.id); setOpen(false) } }}
        itemToStringLabel={(room) => `${room.name} ${room.code}`}
        isItemEqualToValue={(item, other) => item.id === other.id}
      >
        <ComboboxTrigger
          render={<Button id={id} type="button" variant="outline" className={cn('min-w-0 flex-1 justify-between font-normal', !label && 'text-muted-foreground')} />}
        >
          <span className="truncate">{label ?? 'Sin aula'}</span>
          <ChevronsUpDown className="opacity-50" aria-hidden="true" />
        </ComboboxTrigger>
        <ComboboxPopup className="w-(--anchor-width) min-w-72">
          <div className="border-b p-2">
            <ComboboxInput aria-label="Buscar aula" placeholder="Buscar por nombre o código…" maxLength={60} showTrigger={false} />
          </div>
          {catalog.isLoading && <p role="status" className="p-3 text-sm text-muted-foreground">Cargando aulas…</p>}
          {!catalog.isLoading && <ComboboxEmpty>No se encontraron aulas activas.</ComboboxEmpty>}
          <ComboboxList>
            {(room: (typeof rooms)[number]) => (
              <ComboboxItem key={room.id} value={room}>
                <span className="flex items-center gap-2">
                  <span className="truncate">{room.name}</span>
                  <span className="ml-auto text-xs text-muted-foreground">{room.code}</span>
                </span>
              </ComboboxItem>
            )}
          </ComboboxList>
        </ComboboxPopup>
      </Combobox>
      {value !== null && (
        <Button type="button" size="icon" variant="ghost" aria-label="Quitar aula" onClick={() => onChange(null)}>
          <X aria-hidden="true" />
        </Button>
      )}
    </div>
  )
}
