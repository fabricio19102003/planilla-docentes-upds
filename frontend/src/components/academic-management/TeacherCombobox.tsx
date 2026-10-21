import { useState } from 'react'
import { Check, ChevronsUpDown } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { cn } from '@/lib/utils'

export interface TeacherOption {
  ci: string
  full_name: string
}

/** Searchable teacher picker; the server filters the list, so cmdk filtering is off. */
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
  const [selectedLabel, setSelectedLabel] = useState('')
  const selected = teachers.find((teacher) => teacher.ci === value)
  const label = selected ? `${selected.full_name} · ${selected.ci}` : value ? selectedLabel || value : 'Seleccione un docente'
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-invalid={invalid}
          aria-describedby={describedBy}
          className={cn('mt-1 w-full justify-between font-normal', !value && 'text-muted-foreground')}
        >
          <span className="truncate">{label}</span>
          <ChevronsUpDown className="opacity-50" aria-hidden="true" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-(--radix-popover-trigger-width) min-w-80 p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput aria-label="Buscar docente" placeholder="Buscar por nombre o CI…" value={search} onValueChange={onSearchChange} maxLength={120} />
          <CommandList>
            {loading && <p role="status" className="p-3 text-sm text-slate-600">Buscando docentes…</p>}
            {!loading && <CommandEmpty>{emptyMessage}</CommandEmpty>}
            <CommandGroup>
              {teachers.map((teacher) => (
                <CommandItem
                  key={teacher.ci}
                  value={teacher.ci}
                  onSelect={() => {
                    onChange(teacher.ci, teacher)
                    setSelectedLabel(`${teacher.full_name} · ${teacher.ci}`)
                    setOpen(false)
                  }}
                >
                  <Check className={cn('size-4', value === teacher.ci ? 'opacity-100' : 'opacity-0')} aria-hidden="true" />
                  <span className="truncate">{teacher.full_name}</span>
                  <span className="ml-auto text-xs text-slate-500">{teacher.ci}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
          {pageCount && pageCount > 1 && onPageChange && page ? (
            <div className="flex items-center justify-between border-t p-2 text-xs text-slate-500">
              <Button type="button" size="sm" variant="ghost" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>Anterior</Button>
              <span>Página {page} de {pageCount}</span>
              <Button type="button" size="sm" variant="ghost" disabled={page >= pageCount} onClick={() => onPageChange(page + 1)}>Siguiente</Button>
            </div>
          ) : null}
        </Command>
      </PopoverContent>
    </Popover>
  )
}
