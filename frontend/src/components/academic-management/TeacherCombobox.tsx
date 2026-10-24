import { useState } from 'react'
import { ChevronsUpDown } from 'lucide-react'

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
import { cn } from '@/lib/utils'

export interface TeacherOption {
  ci: string
  full_name: string
}

/** Searchable teacher picker; the server filters the list, so client-side filtering is off. */
export function TeacherCombobox({
  id,
  teachers,
  value,
  onChange,
  search,
  onSearchChange,
  loading = false,
  emptyMessage = 'No se encontraron docentes.',
  page,
  pageCount,
  onPageChange,
  invalid = false,
  describedBy,
}: {
  id: string
  teachers: TeacherOption[]
  value: string
  onChange: (ci: string, teacher: TeacherOption | undefined) => void
  search: string
  onSearchChange: (value: string) => void
  loading?: boolean
  emptyMessage?: string
  page?: number
  pageCount?: number
  onPageChange?: (page: number) => void
  invalid?: boolean
  describedBy?: string
}) {
  const [open, setOpen] = useState(false)
  const [picked, setPicked] = useState<TeacherOption | null>(null)
  const selected = teachers.find((teacher) => teacher.ci === value)
    ?? (value && picked?.ci === value ? picked : null)
  const label = selected ? `${selected.full_name} · ${selected.ci}` : value || 'Seleccione un docente'
  return (
    <Combobox
      items={teachers}
      filter={null}
      open={open}
      onOpenChange={setOpen}
      value={selected}
      onValueChange={(teacher) => {
        if (!teacher) return
        onChange(teacher.ci, teacher)
        setPicked(teacher)
        setOpen(false)
      }}
      inputValue={search}
      onInputValueChange={(next, details) => {
        if (details.reason === 'input-change' || details.reason === 'input-clear') onSearchChange(next)
      }}
      itemToStringLabel={(teacher) => `${teacher.full_name} · ${teacher.ci}`}
      isItemEqualToValue={(item, current) => item.ci === current.ci}
    >
      <ComboboxTrigger
        render={
          <Button
            id={id}
            type="button"
            variant="outline"
            aria-invalid={invalid}
            aria-describedby={describedBy}
            className={cn('mt-1 w-full justify-between font-normal', !value && 'text-muted-foreground')}
          />
        }
      >
        <span className="truncate">{label}</span>
        <ChevronsUpDown className="opacity-50" aria-hidden="true" />
      </ComboboxTrigger>
      <ComboboxPopup className="w-(--anchor-width) min-w-80">
        <div className="border-b p-2">
          <ComboboxInput
            aria-label="Buscar docente"
            placeholder="Buscar por nombre o CI…"
            maxLength={120}
            showTrigger={false}
          />
        </div>
        {loading && <p role="status" className="p-3 text-sm text-slate-600">Buscando docentes…</p>}
        {!loading && <ComboboxEmpty>{emptyMessage}</ComboboxEmpty>}
        <ComboboxList>
          {(teacher: TeacherOption) => (
            <ComboboxItem key={teacher.ci} value={teacher}>
              <span className="flex items-center gap-2">
                <span className="truncate">{teacher.full_name}</span>
                <span className="ml-auto text-xs text-slate-500">{teacher.ci}</span>
              </span>
            </ComboboxItem>
          )}
        </ComboboxList>
        {pageCount && pageCount > 1 && onPageChange && page ? (
          <div className="flex items-center justify-between border-t p-2 text-xs text-slate-500">
            <Button type="button" size="sm" variant="ghost" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>Anterior</Button>
            <span>Página {page} de {pageCount}</span>
            <Button type="button" size="sm" variant="ghost" disabled={page >= pageCount} onClick={() => onPageChange(page + 1)}>Siguiente</Button>
          </div>
        ) : null}
      </ComboboxPopup>
    </Combobox>
  )
}
