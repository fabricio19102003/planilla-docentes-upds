import { useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  Activity,
  AlertTriangle,
  Bell,
  BookOpen,
  BookUser,
  Calendar,
  CalendarCheck,
  ChevronDown,
  ChevronsUpDown,
  ClipboardCheck,
  ClipboardList,
  Database,
  FileSignature,
  FileSpreadsheet,
  FileText,
  GraduationCap,
  History,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  MessagesSquare,
  Receipt,
  School,
  Settings,
  Shield,
  ShieldCheck,
  Upload,
  User,
  Users,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { useAuth } from '@/context/AuthContext'
import { useMyProfile } from '@/api/hooks/useAuth'
import { ChatNavBadge } from '@/components/chat/ChatNavBadge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Collapsible, CollapsiblePanel, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Menu, MenuGroup, MenuGroupLabel, MenuItem, MenuPopup, MenuSeparator, MenuTrigger } from '@/components/ui/menu'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from '@/components/ui/sidebar'
import { CHAT_ADMIN_PATH, CHAT_PORTAL_PATH } from '@/lib/chat'
import {
  adminNav,
  getActiveGroupLabel,
  getDocenteNavItems,
  isNavGroup,
  isPathActive,
  type AdminNavEntry,
  type NavGroupDef,
  type NavIconName,
  type NavItemDef,
} from '@/lib/navigation'

const navIcons: Record<NavIconName, LucideIcon> = {
  dashboard: LayoutDashboard,
  calendarCheck: CalendarCheck,
  upload: Upload,
  attendance: ClipboardCheck,
  audit: ShieldCheck,
  observations: AlertTriangle,
  planilla: FileSpreadsheet,
  reports: FileText,
  academic: GraduationCap,
  teachers: Users,
  contracts: FileSignature,
  designations: ClipboardList,
  school: School,
  schedule: Calendar,
  requests: MessageSquare,
  settings: Settings,
  users: Shield,
  activity: Activity,
  backup: Database,
  billing: Receipt,
  history: History,
  letter: FileText,
  notifications: Bell,
  profile: User,
  messages: MessagesSquare,
  students: BookUser,
  curriculum: BookOpen,
}

function NavItemLink({ item }: { item: NavItemDef }) {
  const { pathname } = useLocation()
  const { isMobile, setOpenMobile } = useSidebar()
  const Icon = navIcons[item.icon]

  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        isActive={isPathActive(pathname, item)}
        tooltip={item.label}
        render={
          <NavLink
            to={item.to}
            end={item.exact}
            onClick={() => {
              if (isMobile) setOpenMobile(false)
            }}
          />
        }
      >
        <Icon />
        <span>{item.label}</span>
      </SidebarMenuButton>
      {item.badge != null && item.badge > 0 && (
        <SidebarMenuBadge>{item.badge > 9 ? '9+' : item.badge}</SidebarMenuBadge>
      )}
      {item.to === CHAT_ADMIN_PATH && <ChatNavBadge side="admin" />}
      {item.to === CHAT_PORTAL_PATH && <ChatNavBadge side="docente" />}
    </SidebarMenuItem>
  )
}

function NavGroup({
  group,
  open,
  onOpenChange,
}: {
  group: NavGroupDef
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { state, isMobile } = useSidebar()
  const GroupIcon = navIcons[group.icon]
  // In icon mode the labels are hidden, so every item stays reachable as an icon.
  const iconMode = state === 'collapsed' && !isMobile

  return (
    <Collapsible open={open || iconMode} onOpenChange={onOpenChange}>
      <SidebarGroup className="py-1">
        <SidebarGroupLabel
          render={<CollapsibleTrigger />}
          className="cursor-pointer gap-2 hover:text-sidebar-foreground"
        >
          <GroupIcon className="size-3.5" />
          <span className="flex-1 text-left">{group.label}</span>
          <ChevronDown className="size-3.5 transition-transform in-data-panel-open:rotate-180" />
        </SidebarGroupLabel>
        <CollapsiblePanel>
          <SidebarMenu className="pt-1">
            {group.children.map((child) => (
              <NavItemLink key={child.to} item={child} />
            ))}
          </SidebarMenu>
        </CollapsiblePanel>
      </SidebarGroup>
    </Collapsible>
  )
}

function SidebarNav({ navItems }: { navItems: AdminNavEntry[] }) {
  const { pathname } = useLocation()
  const activeGroupLabel = getActiveGroupLabel(pathname, navItems)
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(
    () => new Set(activeGroupLabel ? [activeGroupLabel] : []),
  )
  const [seenPathname, setSeenPathname] = useState(pathname)

  // Opening another group's route expands it; manual toggles stay untouched otherwise.
  if (seenPathname !== pathname) {
    setSeenPathname(pathname)
    if (activeGroupLabel && !expandedGroups.has(activeGroupLabel)) {
      setExpandedGroups(new Set(expandedGroups).add(activeGroupLabel))
    }
  }

  const setGroupOpen = (label: string, open: boolean) => {
    setExpandedGroups((current) => {
      const next = new Set(current)
      if (open) next.add(label)
      else next.delete(label)
      return next
    })
  }

  const topLevel = navItems.filter((entry): entry is NavItemDef => !isNavGroup(entry))

  return (
    <nav aria-label="Secciones">
      {topLevel.length > 0 && (
        <SidebarGroup className="py-1">
          <SidebarMenu>
            {topLevel.map((item) => (
              <NavItemLink key={item.to} item={item} />
            ))}
          </SidebarMenu>
        </SidebarGroup>
      )}
      {navItems.filter(isNavGroup).map((group) => (
        <NavGroup
          key={group.label}
          group={group}
          open={expandedGroups.has(group.label)}
          onOpenChange={(open) => setGroupOpen(group.label, open)}
        />
      ))}
    </nav>
  )
}

// Only mounted for docentes: /portal/profile is not available to admins.
function DocenteSidebarNav() {
  const { data: profile } = useMyProfile()

  return (
    <nav aria-label="Secciones">
      <SidebarGroup className="py-1">
        <SidebarMenu>
          {getDocenteNavItems(profile?.has_retention).map((item) => (
            <NavItemLink key={item.to} item={item} />
          ))}
        </SidebarMenu>
      </SidebarGroup>
    </nav>
  )
}

function UserMenu() {
  const { user, isAdmin, logout } = useAuth()
  const { isMobile, setOpenMobile } = useSidebar()
  const [failedAvatarUrl, setFailedAvatarUrl] = useState<string | null>(null)
  const avatarUrl = user?.avatar_url ?? null
  const showAvatarImage = Boolean(avatarUrl) && failedAvatarUrl !== avatarUrl
  const initials = user?.full_name
    ? user.full_name
        .split(' ')
        .slice(0, 2)
        .map((part) => part[0])
        .join('')
        .toUpperCase()
    : 'U'

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <Menu>
          <MenuTrigger
            render={<SidebarMenuButton size="lg" tooltip={user?.full_name ?? 'Usuario'} aria-label="Abrir menú de usuario" />}
          >
            <Avatar className="size-8">
              {showAvatarImage && (
                <AvatarImage
                  src={avatarUrl ?? undefined}
                  alt={`Foto de perfil de ${user?.full_name ?? 'usuario'}`}
                  onError={() => setFailedAvatarUrl(avatarUrl)}
                />
              )}
              <AvatarFallback className="bg-primary text-primary-foreground text-xs">{initials}</AvatarFallback>
            </Avatar>
            <div className="grid min-w-0 flex-1 text-left leading-tight">
              <span className="truncate text-sm font-medium">{user?.full_name ?? ''}</span>
              <span className="truncate text-xs text-muted-foreground">{isAdmin ? 'Administrador' : 'Docente'}</span>
            </div>
            <ChevronsUpDown className="ml-auto size-4 opacity-60" />
          </MenuTrigger>
          <MenuPopup side={isMobile ? 'top' : 'right'} align="end" sideOffset={8} className="min-w-56">
            <MenuGroup>
              <MenuGroupLabel className="flex flex-col gap-0.5 py-2">
                <span className="truncate text-sm font-medium text-foreground">{user?.full_name}</span>
                <span className="truncate text-xs font-normal text-muted-foreground">CI: {user?.ci}</span>
              </MenuGroupLabel>
            </MenuGroup>
            <MenuSeparator />
            <MenuItem
              variant="destructive"
              onClick={() => {
                if (isMobile) setOpenMobile(false)
                logout()
              }}
            >
              <LogOut />
              Cerrar Sesión
            </MenuItem>
          </MenuPopup>
        </Menu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}

export function AppSidebar() {
  const { isAdmin } = useAuth()

  return (
    <Sidebar collapsible="icon">
      {/* The 3rem collapsed rail leaves room for p-2 plus the 2rem badge, the same box as the menu icons. */}
      <SidebarHeader className="px-4 py-3 group-data-[collapsible=icon]:px-2">
        <div className="flex items-center gap-2.5 overflow-hidden">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-sm font-black text-primary-foreground shadow-xs">
            S
          </div>
          <div className="grid min-w-0 leading-tight group-data-[collapsible=icon]:hidden">
            <span className="truncate text-sm font-bold tracking-wide text-sidebar-foreground">UPDS</span>
            <span className="truncate text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
              Sistema de Pago
            </span>
          </div>
        </div>
      </SidebarHeader>

      <SidebarContent>{isAdmin ? <SidebarNav navItems={adminNav} /> : <DocenteSidebarNav />}</SidebarContent>

      <SidebarFooter>
        <UserMenu />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
