import type { ReactNode } from 'react'

import { Card, CardAction, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table } from '@/components/ui/table'
import { cn } from '@/lib/utils'

export interface TableCardProps {
  /** Optional card header title. */
  title?: ReactNode
  description?: ReactNode
  /** Toolbar slot (search, filters, buttons) shown on the right of the header. */
  toolbar?: ReactNode
  /** Footer slot, for example pagination. */
  footer?: ReactNode
  /** Classes for the inner `<table>`. */
  tableClassName?: string
  className?: string
  /** `TableHeader` / `TableBody` / `TableRow` content from `@/components/ui/table`. */
  children: ReactNode
}

/**
 * A Card holding a coss Table (S11): the table scrolls horizontally on mobile.
 * Right-align numeric cells with `className="text-right tabular-nums"`.
 *
 * @example
 * <TableCard title="Usuarios" toolbar={<Input placeholder="Buscar" />}>
 *   <TableHeader><TableRow><TableHead>Nombre</TableHead></TableRow></TableHeader>
 *   <TableBody>...</TableBody>
 * </TableCard>
 */
export function TableCard({ title, description, toolbar, footer, tableClassName, className, children }: TableCardProps) {
  const hasHeader = title != null || description != null || toolbar != null

  return (
    <Card className={cn('gap-0 overflow-hidden', className)}>
      {hasHeader && (
        <CardHeader className="border-b pb-4">
          {title != null && <CardTitle className="text-base">{title}</CardTitle>}
          {description != null && <CardDescription>{description}</CardDescription>}
          {toolbar != null && <CardAction className="flex flex-wrap items-center gap-2">{toolbar}</CardAction>}
        </CardHeader>
      )}
      <Table className={tableClassName}>{children}</Table>
      {footer != null && <div className="border-t px-4 py-3">{footer}</div>}
    </Card>
  )
}
