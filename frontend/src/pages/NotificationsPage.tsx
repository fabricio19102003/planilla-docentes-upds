import { useNotifications, useMarkRead, useMarkAllRead } from '@/api/hooks/useNotifications'
import { AlertCircle, Bell, CheckCheck, Clock, Receipt } from 'lucide-react'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { TONE_CHIP } from '@/components/shared/tones'
import { cn } from '@/lib/utils'

function getNotificationErrorMessage(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

export function NotificationsPage() {
  const { data: notifications, isLoading, error, refetch, isFetching } = useNotifications()
  const markRead = useMarkRead()
  const markAllRead = useMarkAllRead()

  if (isLoading) {
    return (
      <div className="max-w-2xl">
        <PageHeader title="Notificaciones" description="Avisos sobre tus pagos y solicitudes." />
        <div role="status" aria-busy="true" className="space-y-2">
          <span className="sr-only">Cargando notificaciones</span>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-20 w-full rounded-2xl" />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-2xl">
        <PageHeader title="Notificaciones" description="Avisos sobre tus pagos y solicitudes." />
        <Alert variant="error">
          <AlertCircle aria-hidden="true" />
          <AlertTitle>No se pudieron cargar tus notificaciones</AlertTitle>
          <AlertDescription>
            {getNotificationErrorMessage(error, 'Ocurrió un problema al consultar el servidor.')}
          </AlertDescription>
          <AlertAction>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void refetch()}
              disabled={isFetching}
            >
              {isFetching ? 'Reintentando...' : 'Reintentar'}
            </Button>
          </AlertAction>
        </Alert>
      </div>
    )
  }

  const unreadCount = notifications?.filter((n) => !n.is_read).length ?? 0

  return (
    <div className="max-w-2xl space-y-4 sm:space-y-6">
      <PageHeader
        title="Notificaciones"
        description={unreadCount > 0 ? `${unreadCount} sin leer` : 'Todas leídas'}
        actions={
          unreadCount > 0 && (
            <Button
              variant="outline"
              size="sm"
              className="w-full gap-2 text-sm sm:w-auto"
              onClick={() => {
                markAllRead.reset()
                markAllRead.mutate()
              }}
              disabled={markAllRead.isPending || markRead.isPending}
            >
              <CheckCheck size={14} aria-hidden="true" />
              {markAllRead.isPending ? 'Marcando...' : 'Marcar todo como leído'}
            </Button>
          )
        }
      />

      {(markRead.error || markAllRead.error) && (
        <Alert variant="error">
          <AlertCircle aria-hidden="true" />
          <AlertDescription className="text-destructive-foreground">
            {getNotificationErrorMessage(
              markRead.error ?? markAllRead.error,
              'No se pudo actualizar la notificación. Intentá de nuevo.',
            )}
          </AlertDescription>
        </Alert>
      )}
      <p className="sr-only" aria-live="polite">
        {markAllRead.isPending
          ? 'Marcando todas las notificaciones como leídas.'
          : markRead.isPending
            ? 'Marcando la notificación como leída.'
            : ''}
      </p>

      {/* Notifications list */}
      {!notifications?.length ? (
        <Card>
          <EmptyState icon={Bell} title="No tenés notificaciones" />
        </Card>
      ) : (
        <div className="space-y-2">
          {notifications.map((notif) => {
            const isBillingNotification = notif.notification_type.endsWith('billing_published')
            return (
              <Card
                key={notif.id}
                className={cn(!notif.is_read && 'border-l-4 border-l-primary bg-primary/4')}
              >
                <button
                  type="button"
                  onClick={() => {
                    if (!notif.is_read && !markRead.isPending && !markAllRead.isPending) {
                      markRead.reset()
                      markRead.mutate(notif.id)
                    }
                  }}
                  disabled={markRead.isPending || markAllRead.isPending || notif.is_read}
                  className="flex w-full items-start gap-3 rounded-[inherit] p-4 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring enabled:hover:bg-accent/50 disabled:cursor-default"
                >
                  <div
                    className={cn(
                      'flex size-9 shrink-0 items-center justify-center rounded-lg',
                      TONE_CHIP[isBillingNotification ? 'success' : 'primary'],
                    )}
                  >
                    {isBillingNotification ? (
                      <Receipt size={16} aria-hidden="true" />
                    ) : (
                      <Bell size={16} aria-hidden="true" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p
                        className={cn(
                          'text-sm',
                          !notif.is_read ? 'font-semibold text-foreground' : 'font-medium text-muted-foreground',
                        )}
                      >
                        {notif.title}
                      </p>
                      {!notif.is_read && <StatusBadge tone="info">Sin leer</StatusBadge>}
                    </div>
                    <p className="mt-0.5 text-xs text-muted-foreground">{notif.message}</p>
                    <p className="mt-1 flex items-center gap-1 text-xs tabular-nums text-muted-foreground">
                      <Clock size={10} aria-hidden="true" />
                      {new Date(notif.created_at).toLocaleDateString('es-BO', {
                        day: '2-digit',
                        month: 'short',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </p>
                  </div>
                </button>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
