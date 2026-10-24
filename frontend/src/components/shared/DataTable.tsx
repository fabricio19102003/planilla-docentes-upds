import React from 'react'
import { ChevronLeft, ChevronRight, Inbox } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'

import { EmptyState } from './EmptyState'

export interface Column<T> {
  key: keyof T | string
  header: string
  render?: (item: T) => React.ReactNode
  /** Numeric columns should use `right`; they also get tabular-nums. */
  align?: 'left' | 'right' | 'center'
  className?: string
}

interface DataTableProps<T> {
  columns: Column<T>[]
  data: T[]
  page?: number
  totalPages?: number
  onPageChange?: (page: number) => void
  emptyMessage?: string
  /** Shows skeleton rows instead of the data. */
  loading?: boolean
}

const ALIGN_CLASS = { left: 'text-left', right: 'text-right tabular-nums', center: 'text-center' } as const
const SKELETON_ROWS = 5

export function DataTable<T>({
  columns,
  data,
  page = 1,
  totalPages = 1,
  onPageChange,
  emptyMessage = 'No hay datos para mostrar',
  loading = false,
}: DataTableProps<T>) {
  const getCellValue = (item: T, key: keyof T | string): React.ReactNode => {
    const value = (item as Record<string, unknown>)[key as string]
    if (value === null || value === undefined) return '—'
    if (typeof value === 'boolean') return value ? 'Sí' : 'No'
    return String(value)
  }

  return (
    <Card className="gap-0 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="bg-muted/40 hover:bg-muted/40">
            {columns.map((col) => (
              <TableHead
                key={String(col.key)}
                className={cn('h-10 px-4 text-xs font-medium uppercase tracking-wider', ALIGN_CLASS[col.align ?? 'left'], col.className)}
              >
                {col.header}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {loading ? (
            Array.from({ length: SKELETON_ROWS }, (_, rowIndex) => (
              <TableRow key={rowIndex}>
                {columns.map((col) => (
                  <TableCell key={String(col.key)} className="px-4 py-3">
                    <Skeleton className="h-4 w-full max-w-32" />
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : data.length === 0 ? (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={columns.length} className="p-0 whitespace-normal">
                <EmptyState icon={Inbox} title={emptyMessage} />
              </TableCell>
            </TableRow>
          ) : (
            data.map((item, rowIndex) => (
              <TableRow key={rowIndex} className="transition-colors">
                {columns.map((col) => (
                  <TableCell key={String(col.key)} className={cn('px-4 py-3 text-sm', ALIGN_CLASS[col.align ?? 'left'], col.className)}>
                    {col.render ? col.render(item) : getCellValue(item, col.key)}
                  </TableCell>
                ))}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      {totalPages > 1 && onPageChange && (
        <div className="flex items-center justify-between border-t bg-muted/40 px-4 py-3">
          <p className="text-xs font-medium text-muted-foreground tabular-nums">
            Página {page} de {totalPages}
          </p>
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon-sm"
              aria-label="Página anterior"
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
            >
              <ChevronLeft />
            </Button>
            <Button
              variant="outline"
              size="icon-sm"
              aria-label="Página siguiente"
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
            >
              <ChevronRight />
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}
