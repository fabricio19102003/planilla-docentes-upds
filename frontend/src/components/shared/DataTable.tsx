import React from 'react'
import {
  Table,
  TableHeader,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { ChevronLeft, ChevronRight } from 'lucide-react'

export interface Column<T> {
  key: keyof T | string
  header: string
  render?: (item: T) => React.ReactNode
}

interface DataTableProps<T> {
  columns: Column<T>[]
  data: T[]
  page?: number
  totalPages?: number
  onPageChange?: (page: number) => void
  emptyMessage?: string
}

export function DataTable<T>({
  columns,
  data,
  page = 1,
  totalPages = 1,
  onPageChange,
  emptyMessage = 'No hay datos para mostrar',
}: DataTableProps<T>) {
  const getCellValue = (item: T, key: keyof T | string): React.ReactNode => {
    const value = (item as Record<string, unknown>)[key as string]
    if (value === null || value === undefined) return '—'
    if (typeof value === 'boolean') return value ? 'Sí' : 'No'
    return String(value)
  }

  return (
    <div className="overflow-hidden rounded-lg border border-gray-200 shadow-sm">
      <Table>
        <TableHeader>
          <TableRow className="border-0">
            {columns.map((col) => (
              <TableHead
                key={String(col.key)}
                className="text-white font-semibold text-xs uppercase tracking-wider h-10 px-4"
                style={{ backgroundColor: '#003366' }}
              >
                {col.header}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.length === 0 ? (
            <TableRow>
              <TableCell
                colSpan={columns.length}
                className="text-center py-12 text-gray-400"
              >
                {emptyMessage}
              </TableCell>
            </TableRow>
          ) : (
            data.map((item, rowIndex) => (
              <TableRow
                key={rowIndex}
                className={[
                  'transition-colors hover:bg-blue-50 cursor-default',
                  rowIndex % 2 === 1 ? 'bg-gray-50' : 'bg-white',
                ].join(' ')}
              >
                {columns.map((col) => (
                  <TableCell key={String(col.key)} className="px-4 py-3 text-sm">
                    {col.render ? col.render(item) : getCellValue(item, col.key)}
                  </TableCell>
                ))}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      {totalPages > 1 && onPageChange && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 bg-white">
          <p className="text-xs text-gray-500">
            Página {page} de {totalPages}
          </p>
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon-sm"
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
            >
              <ChevronLeft size={14} />
            </Button>
            <Button
              variant="outline"
              size="icon-sm"
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
            >
              <ChevronRight size={14} />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
