import { useNotifications, useMarkRead, useMarkAllRead } from '@/api/hooks/useNotifications'
import { AlertCircle, Bell, CheckCheck, Clock, Receipt } from 'lucide-react'
import { Button } from '@/components/ui/button'

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
      <div className="flex items-center justify-center py-24">
        <div className="w-8 h-8 border-2 border-[#003366]/30 border-t-[#003366] rounded-full animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div role="alert" className="bg-red-50 border border-red-200 rounded-lg p-8 text-center max-w-md mx-auto mt-12">
        <AlertCircle size={40} className="text-red-500 mx-auto mb-3" />
        <p className="text-red-700 font-medium">No se pudieron cargar tus notificaciones</p>
        <p className="text-red-600 text-sm mt-1">
          {getNotificationErrorMessage(error, 'Ocurrió un problema al consultar el servidor.')}
        </p>
        <Button
          type="button"
          variant="outline"
          className="mt-4"
          onClick={() => void refetch()}
          disabled={isFetching}
        >
          {isFetching ? 'Reintentando...' : 'Reintentar'}
        </Button>
      </div>
    )
  }

  const unreadCount = notifications?.filter((n) => !n.is_read).length ?? 0

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Header */}
      <div className="flex items-center justify-between animate-fade-in-up">
        <div>
          <h2 className="text-lg font-semibold" style={{ color: '#003366' }}>Notificaciones</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            {unreadCount > 0 ? `${unreadCount} sin leer` : 'Todas leídas'}
          </p>
        </div>
        {unreadCount > 0 && (
          <Button
            variant="outline"
            size="sm"
            className="gap-2 text-sm"
            onClick={() => {
              markAllRead.reset()
              markAllRead.mutate()
            }}
            disabled={markAllRead.isPending || markRead.isPending}
          >
            <CheckCheck size={14} />
            {markAllRead.isPending ? 'Marcando...' : 'Marcar todo como leído'}
          </Button>
        )}
      </div>

      {(markRead.error || markAllRead.error) && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {getNotificationErrorMessage(
            markRead.error ?? markAllRead.error,
            'No se pudo actualizar la notificación. Intentá de nuevo.',
          )}
        </div>
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
        <div className="py-16 text-center">
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
            style={{ backgroundColor: 'rgba(0,51,102,0.08)' }}
          >
            <Bell size={28} style={{ color: '#003366' }} />
          </div>
          <p className="text-gray-500 font-medium">No tenés notificaciones</p>
        </div>
      ) : (
        <div className="space-y-2">
          {notifications.map((notif) => {
            const isBillingNotification = notif.notification_type.endsWith('billing_published')
            return (
              <button
              key={notif.id}
              onClick={() => {
                if (!notif.is_read && !markRead.isPending && !markAllRead.isPending) {
                  markRead.reset()
                  markRead.mutate(notif.id)
                }
              }}
              disabled={markRead.isPending || markAllRead.isPending || notif.is_read}
              className={`w-full text-left card-3d-static p-4 flex items-start gap-3 transition-all ${
                !notif.is_read ? 'border-l-4 border-l-[#0066CC] bg-blue-50/30' : ''
              }`}
            >
              <div
                className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${
                  isBillingNotification ? 'bg-green-100' : 'bg-blue-100'
                }`}
              >
                {isBillingNotification ? (
                  <Receipt size={16} className="text-green-600" />
                ) : (
                  <Bell size={16} className="text-blue-600" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p
                    className={`text-sm ${
                      !notif.is_read ? 'font-semibold text-gray-800' : 'font-medium text-gray-600'
                    }`}
                  >
                    {notif.title}
                  </p>
                  {!notif.is_read && (
                    <span className="w-2 h-2 rounded-full bg-[#0066CC] flex-shrink-0" />
                  )}
                </div>
                <p className="text-xs text-gray-500 mt-0.5">{notif.message}</p>
                <p className="text-xs text-gray-400 mt-1 flex items-center gap-1">
                  <Clock size={10} />
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
            )
          })}
        </div>
      )}
    </div>
  )
}
