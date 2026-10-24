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
export function PageHeader({ title, description, actions, breadcrumb, className }: PageHeaderProps) {
  return (
    <header className={cn('mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between', className)}>
      <div className="min-w-0 space-y-1">
        {breadcrumb && <div className="mb-2 text-sm text-muted-foreground">{breadcrumb}</div>}
        {/* h2: the app header already renders the route title as the page h1. */}
        <h2 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h2>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2 sm:justify-end">{actions}</div>}
    </header>
  )
}
