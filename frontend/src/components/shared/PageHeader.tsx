import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

export interface PageHeaderProps {
  title: ReactNode
  /** Muted one-line description under the title. */
  description?: ReactNode
  /** Primary actions (buttons). Right-aligned on desktop, stacked below the title on mobile. */
  actions?: ReactNode
  /** Optional slot above the title for a breadcrumb or a back link/button. */
  breadcrumb?: ReactNode
  /** Heading level: `h2` under the app header (default); `h1` where the page owns the top heading. */
  as?: 'h1' | 'h2'
  className?: string
}

/**
 * Standard page header (S11): `text-2xl` title, muted description, actions on the right.
 * On mobile the actions stack below the title.
 *
 * @example
 * <PageHeader
 *   title="Usuarios"
 *   description="Administrá las cuentas de acceso a SIPAD."
 *   breadcrumb={<Button variant="ghost" size="sm" render={<Link to="/" />}>Volver</Button>}
 *   actions={<Button onClick={openCreate}>Nuevo usuario</Button>}
 * />
 */
export function PageHeader({ title, description, actions, breadcrumb, as: Heading = 'h2', className }: PageHeaderProps) {
  return (
    <header className={cn('mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between', className)}>
      <div className="min-w-0 space-y-1">
        {breadcrumb && <div className="mb-2 text-sm text-muted-foreground">{breadcrumb}</div>}
        {/* h2 by default: the app header already renders the route title as the page h1. */}
        <div className="flex items-center gap-3">
          <span aria-hidden="true" className="h-7 w-1.5 shrink-0 rounded-full bg-brand-strong shadow-sm shadow-brand-strong/40" />
          <Heading className="text-2xl font-semibold tracking-tight text-foreground">{title}</Heading>
        </div>
        {description && <p className="pl-[1.125rem] text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2 sm:justify-end">{actions}</div>}
    </header>
  )
}
