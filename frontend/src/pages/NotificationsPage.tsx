import { useNotifications, useMarkRead, useMarkAllRead } from '@/api/hooks/useNotifications'
import { Bell, CheckCheck, Clock, Receipt } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function NotificationsPage() {
  const { data: notifications, isLoading } = useNotifications()
  const markRead = useMarkRead()
  const markAllRead = useMarkAllRead()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-8 h-8 border-2 border-[#003366]/30 border-t-[#003366] rounded-full animate-spin" />
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
            onClick={() => markAllRead.mutate()}
            disabled={markAllRead.isPending}
          >
            <CheckCheck size={14} />
            Marcar todo como leído
          </Button>
        )}
      </div>

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
          {notifications.map((notif) => (
            <button
              key={notif.id}
              onClick={() => {
                if (!notif.is_read) markRead.mutate(notif.id)
              }}
              className={`w-full text-left card-3d-static p-4 flex items-start gap-3 transition-all ${
                !notif.is_read ? 'border-l-4 border-l-[#0066CC] bg-blue-50/30' : ''
              }`}
            >
              <div
                className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${
                  notif.notification_type === 'billing_published' ? 'bg-green-100' : 'bg-blue-100'
                }`}
              >
                {notif.notification_type === 'billing_published' ? (
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
          ))}
        </div>
      )}
    </div>
  )
}
