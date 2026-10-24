import { useChatUnreadCount } from '@/api/hooks/useChat'
import type { ChatSide } from '@/api/hooks/useChat'
import { SidebarMenuBadge } from '@/components/ui/sidebar'

/** Unread messages on the "Mensajes" nav entry; polls every 30 s while the tab is visible. */
export function ChatNavBadge({ side }: { side: ChatSide }) {
  const { data: unread = 0 } = useChatUnreadCount(side)
  if (unread <= 0) return null
  return (
    <SidebarMenuBadge>
      <span aria-hidden="true">{unread > 9 ? '9+' : unread}</span>
      <span className="sr-only">{unread === 1 ? '1 mensaje sin leer' : `${unread} mensajes sin leer`}</span>
    </SidebarMenuBadge>
  )
}
