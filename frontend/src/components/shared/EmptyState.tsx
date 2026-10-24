import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'

import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty'
import { cn } from '@/lib/utils'

export interface EmptyStateProps {
  icon?: LucideIcon
  title: ReactNode
  description?: ReactNode
  /** Optional call to action, for example a Button. */
  action?: ReactNode
  className?: string
}

/**
 * Empty result placeholder built on coss Empty.
 *
 * @example
 * <EmptyState icon={Inbox} title="Sin solicitudes" description="No hay solicitudes pendientes." />
 */
export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <Empty className={cn('py-12 md:py-16', className)}>
      <EmptyHeader>
        {Icon && (
          <EmptyMedia variant="icon">
            <Icon aria-hidden="true" />
          </EmptyMedia>
        )}
        <EmptyTitle className="text-lg">{title}</EmptyTitle>
        {description && <EmptyDescription>{description}</EmptyDescription>}
      </EmptyHeader>
      {action && <EmptyContent>{action}</EmptyContent>}
    </Empty>
  )
}
