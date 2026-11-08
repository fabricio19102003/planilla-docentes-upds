import { Fragment, useEffect, useId, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  Activity,
  AlertTriangle,
  Bell,
  BookOpen,
  BookUser,
  Calendar,
  CalendarCheck,
  Check,
  ChevronDown,
  ChevronsUpDown,
  ClipboardCheck,
  ClipboardList,
  Database,
  DoorOpen,
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
  Search,
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
import { useChatUnreadCount } from '@/api/hooks/useChat'
import { ChatNavBadge } from '@/components/chat/ChatNavBadge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import {
  Command,
  CommandCollection,
  CommandDialog,
  CommandDialogPopup,
  CommandDialogPrimitive,
  CommandEmpty,
  CommandGroup,
  CommandGroupLabel,
  CommandInput,
  CommandItem,
  CommandList,
  CommandPanel,
} from '@/components/ui/command'
import {
  Menu,
  MenuGroup,
  MenuGroupLabel,
  MenuItem,
  MenuLinkItem,
  MenuPopup,
  MenuSeparator,
  MenuTrigger,
} from '@/components/ui/menu'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
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
  getSearchSections,
  isSearchShortcut,
  showGroupPendingDot,
  splitAdminGroups,
  syncOpenGroup,
  toggleOpenGroup,
  type SearchItem,
  type SearchSection,
} from '@/lib/adminSidebar'
import { cn } from '@/lib/utils'
import {
  adminNav,
  adminQuickAccess,
  getDocenteNavItems,
  isPathActive,
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
  classroom: DoorOpen,
}

const activeItemClass =
  'data-[active=true]:bg-sidebar-primary data-[active=true]:text-sidebar-primary-foreground data-[active=true]:shadow-md data-[active=true]:shadow-black/20 data-[active=true]:hover:bg-sidebar-primary data-[active=true]:hover:text-sidebar-primary-foreground'

const adminGroups = splitAdminGroups(adminNav)
const searchSections = getSearchSections(adminNav)

/** Icon rail: labels are hidden and every entry turns into an icon button. */
function useIconMode() {
  const { state, isMobile } = useSidebar()
  return state === 'collapsed' && !isMobile
}

function useAdminChatUnread() {
  return useChatUnreadCount('admin').data ?? 0
}

function unreadText(unread: number) {
  return unread === 1 ? '1 mensaje sin leer' : `${unread} mensajes sin leer`
}

function ChatUnreadPill({ className }: { className?: string }) {
  const unread = useAdminChatUnread()
  if (unread <= 0) return null
  return (
    <span
      className={cn(
        'flex h-5 min-w-5 items-center justify-center rounded-full bg-destructive px-1.5 text-[11px] font-semibold tabular-nums text-white',
        className,
      )}
    >
      <span aria-hidden="true">{unread > 9 ? '9+' : unread}</span>
      <span className="sr-only">{unreadText(unread)}</span>
    </span>
  )
}

function UnreadDot({ label, className }: { label: string; className?: string }) {
  return (
    <>
      <span aria-hidden="true" className={cn('size-2 shrink-0 rounded-full bg-destructive', className)} />
      <span className="sr-only">{label}</span>
    </>
  )
}

function NavItemLink({ item, className }: { item: NavItemDef; className?: string }) {
  const { pathname } = useLocation()
  const { isMobile, setOpenMobile } = useSidebar()
  const Icon = navIcons[item.icon]

  return (
    <SidebarMenuItem className={item.separatorBefore ? 'mt-1 border-t border-dashed border-sidebar-border pt-1' : undefined}>
      <SidebarMenuButton
        isActive={isPathActive(pathname, item)}
        tooltip={item.label}
        className={cn(activeItemClass, className)}
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

function SearchButton({ onOpen }: { onOpen: () => void }) {
  return (
    <div className="px-3 pb-2 group-data-[collapsible=icon]:px-2">
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton
            type="button"
            tooltip="Buscar sección (Ctrl K)"
            aria-label="Buscar sección (Ctrl+K)"
            onClick={onOpen}
            className="bg-sidebar-accent text-sidebar-foreground/80 ring-1 ring-inset ring-sidebar-border"
          >
            <Search />
            <span className="flex-1 truncate group-data-[collapsible=icon]:hidden">Buscar sección…</span>
            <kbd className="rounded-sm border border-sidebar-border px-1.5 font-sans text-[11px] group-data-[collapsible=icon]:hidden">
              Ctrl K
            </kbd>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </div>
  )
}

function QuickAccess({ iconMode }: { iconMode: boolean }) {
  const { pathname } = useLocation()
  const { isMobile, setOpenMobile } = useSidebar()
  const unread = useAdminChatUnread()
  const closeMobile = () => {
    if (isMobile) setOpenMobile(false)
  }

  if (iconMode) {
    return (
      <SidebarMenu className="px-2">
        {adminQuickAccess.map((item) => {
          const Icon = navIcons[item.icon]
          return (
            <SidebarMenuItem key={item.to}>
              <SidebarMenuButton
                isActive={isPathActive(pathname, item)}
                tooltip={item.label}
                className={activeItemClass}
                render={<NavLink to={item.to} end={item.exact} />}
              >
                <Icon />
                <span>{item.label}</span>
              </SidebarMenuButton>
              {item.to === CHAT_ADMIN_PATH && unread > 0 && (
                <span className="pointer-events-none absolute right-0.5 top-0.5 flex">
                  <UnreadDot label={unreadText(unread)} className="ring-2 ring-sidebar" />
                </span>
              )}
            </SidebarMenuItem>
          )
        })}
      </SidebarMenu>
    )
  }

  return (
    <div className="grid grid-cols-2 gap-1.5 px-3">
      {adminQuickAccess.map((item) => {
        const Icon = navIcons[item.icon]
        const active = isPathActive(pathname, item)
        return (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.exact}
            onClick={closeMobile}
            className={cn(
              'relative flex flex-col gap-1.5 rounded-lg bg-sidebar-accent/70 p-2.5 text-xs leading-tight text-sidebar-foreground outline-hidden ring-sidebar-ring hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-2',
              active &&
                'bg-sidebar-primary text-sidebar-primary-foreground shadow-md shadow-black/20 hover:bg-sidebar-primary hover:text-sidebar-primary-foreground',
            )}
          >
            <Icon className="size-[18px]" />
            <span>{item.label}</span>
            {item.to === CHAT_ADMIN_PATH && <ChatUnreadPill className="absolute right-2 top-2" />}
          </NavLink>
        )
      })}
    </div>
  )
}

function GroupAccordion({
  group,
  open,
  quiet,
  className,
  onToggle,
}: {
  group: NavGroupDef
  open: boolean
  quiet?: boolean
  className?: string
  onToggle: () => void
}) {
  const panelId = useId()
  const { pathname } = useLocation()
  const unread = useAdminChatUnread()
  const Icon = navIcons[group.icon]
  const holdsCurrentPage = group.children.some((child) => isPathActive(pathname, child))
  const pending = showGroupPendingDot(group, unread, open)

  return (
    <div className={className}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={onToggle}
        className={cn(
          'flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm outline-hidden ring-sidebar-ring hover:bg-sidebar-accent focus-visible:ring-2',
          quiet
            ? 'font-medium text-sidebar-foreground hover:text-sidebar-accent-foreground'
            : 'font-semibold text-sidebar-accent-foreground',
        )}
      >
        <span
          className={cn(
            'grid size-[26px] shrink-0 place-items-center rounded-lg',
            open ? 'bg-sidebar-primary text-sidebar-primary-foreground' : 'bg-sidebar-accent',
            holdsCurrentPage && !open && 'ring-1 ring-sidebar-ring',
          )}
        >
          <Icon className="size-4" />
        </span>
        <span className="flex-1 truncate">{group.label}</span>
        {holdsCurrentPage && !open && <span className="sr-only">(contiene la página actual)</span>}
        {pending ? (
          <UnreadDot label={`(${unreadText(unread)})`} />
        ) : (
          <span className="text-[11px] font-medium text-sidebar-foreground/80">{group.children.length}</span>
        )}
        <ChevronDown
          aria-hidden="true"
          className={cn(
            'size-3.5 shrink-0 text-sidebar-foreground/80 transition-transform duration-150 motion-reduce:transition-none',
            open && 'rotate-180',
          )}
        />
      </button>
      <div
        id={panelId}
        className={cn(
          'grid transition-[grid-template-rows] duration-200 motion-reduce:transition-none',
          open ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]',
        )}
      >
        <div className="min-h-0 overflow-hidden" inert={!open}>
          <SidebarMenu className="mb-1.5 ml-[22px] mt-0.5 gap-0.5 border-l border-sidebar-border pl-3">
            {group.children.map((child) => (
              <NavItemLink key={child.to} item={child} className="text-[13.5px]" />
            ))}
          </SidebarMenu>
        </div>
      </div>
    </div>
  )
}

/** Icon rail: the whole group is one button that opens its pages in a popup menu. */
function GroupMenu({ group, className }: { group: NavGroupDef; className?: string }) {
  const { pathname } = useLocation()
  const unread = useAdminChatUnread()
  const Icon = navIcons[group.icon]
  const holdsCurrentPage = group.children.some((child) => isPathActive(pathname, child))
  const pending = showGroupPendingDot(group, unread, false)

  return (
    <SidebarMenu className={className}>
      <SidebarMenuItem>
        <Menu>
          <MenuTrigger
            render={
              <SidebarMenuButton
                type="button"
                isActive={holdsCurrentPage}
                tooltip={group.label}
                aria-label={`${group.label}: ${group.children.length} páginas`}
                className={activeItemClass}
              />
            }
          >
            <Icon />
          </MenuTrigger>
          <MenuPopup side="right" align="start" sideOffset={8} className="min-w-56">
            <MenuGroup>
              <MenuGroupLabel>{group.label}</MenuGroupLabel>
              {group.children.map((child) => {
                const ChildIcon = navIcons[child.icon]
                const active = isPathActive(pathname, child)
                return (
                  <Fragment key={child.to}>
                    {child.separatorBefore && <MenuSeparator />}
                    <MenuLinkItem render={<NavLink to={child.to} end={child.exact} />} className={active ? 'font-medium' : undefined}>
                      <ChildIcon />
                      <span>{child.label}</span>
                      <span className="ml-auto flex items-center gap-2">
                        {child.to === CHAT_ADMIN_PATH && <ChatUnreadPill />}
                        {active && <Check aria-hidden="true" className="size-4" />}
                      </span>
                    </MenuLinkItem>
                  </Fragment>
                )
              })}
            </MenuGroup>
          </MenuPopup>
        </Menu>
        {pending && (
          <span className="pointer-events-none absolute right-0.5 top-0.5 flex">
            <UnreadDot label={unreadText(unread)} className="ring-2 ring-sidebar" />
          </span>
        )}
      </SidebarMenuItem>
    </SidebarMenu>
  )
}

function AdminGroup({
  group,
  iconMode,
  open,
  quiet,
  className,
  onToggle,
}: {
  group: NavGroupDef
  iconMode: boolean
  open: boolean
  quiet?: boolean
  className?: string
  onToggle: () => void
}) {
  return iconMode ? (
    <GroupMenu group={group} className={className} />
  ) : (
    <GroupAccordion group={group} open={open} quiet={quiet} className={className} onToggle={onToggle} />
  )
}

function SidebarCaption({ id, children }: { id: string; children: string }) {
  return (
    <p
      id={id}
      className="mx-5 mb-1 mt-3 text-[11px] font-medium uppercase tracking-wider text-sidebar-foreground/80 group-data-[collapsible=icon]:hidden"
    >
      {children}
    </p>
  )
}

/** Search + quick access + accordion groups + footer group. Owns the single-open accordion state. */
function AdminSidebarBody({ onOpenSearch }: { onOpenSearch: () => void }) {
  const { pathname } = useLocation()
  const iconMode = useIconMode()
  const [openGroup, setOpenGroup] = useState<string | null>(() => syncOpenGroup(null, pathname, adminNav))
  const [seenPathname, setSeenPathname] = useState(pathname)

  // Navigating into another group opens it; the user may still close everything afterwards.
  if (seenPathname !== pathname) {
    setSeenPathname(pathname)
    setOpenGroup(syncOpenGroup(openGroup, pathname, adminNav))
  }

  const groupProps = (group: NavGroupDef) => ({
    group,
    iconMode,
    open: openGroup === group.label,
    onToggle: () => setOpenGroup((current) => toggleOpenGroup(current, group.label)),
  })

  return (
    <>
      <SearchButton onOpen={onOpenSearch} />
      <SidebarContent className="gap-0 bg-sidebar-glow pb-3">
        <nav aria-labelledby="sidebar-quick-access">
          <SidebarCaption id="sidebar-quick-access">Accesos rápidos</SidebarCaption>
          <QuickAccess iconMode={iconMode} />
        </nav>
        <div aria-hidden="true" className="mx-3 my-2 hidden h-px bg-sidebar-border group-data-[collapsible=icon]:block" />
        <nav aria-labelledby="sidebar-sections" className="flex flex-col gap-0.5 group-data-[collapsible=icon]:gap-1">
          <SidebarCaption id="sidebar-sections">Secciones</SidebarCaption>
          {adminGroups.main.map((group) => (
            <AdminGroup key={group.label} {...groupProps(group)} className="px-2" />
          ))}
        </nav>
      </SidebarContent>
      <SidebarFooter className="border-t border-sidebar-border">
        <nav aria-label="Sistema">
          {adminGroups.footer.map((group) => (
            <AdminGroup key={group.label} {...groupProps(group)} quiet />
          ))}
        </nav>
        <UserMenu />
      </SidebarFooter>
    </>
  )
}

function AdminSearchDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const navigate = useNavigate()
  const { isMobile, setOpenMobile } = useSidebar()

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      const { key, ctrlKey, metaKey, altKey, shiftKey } = event
      if (!isSearchShortcut({ key, ctrlKey, metaKey, altKey, shiftKey, target })) return
      event.preventDefault()
      onOpenChange(true)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onOpenChange])

  const go = (item: SearchItem) => {
    onOpenChange(false)
    if (isMobile) setOpenMobile(false)
    navigate(item.to)
  }

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandDialogPopup>
        <CommandDialogPrimitive.Title className="sr-only">Buscar sección</CommandDialogPrimitive.Title>
        <Command items={searchSections}>
          <CommandInput placeholder="Buscar sección…" aria-label="Buscar sección" />
          <CommandPanel>
            <CommandEmpty>No hay secciones que coincidan.</CommandEmpty>
            <CommandList>
              {(section: SearchSection) => (
                <CommandGroup key={section.value} items={section.items}>
                  <CommandGroupLabel>{section.value}</CommandGroupLabel>
                  <CommandCollection>
                    {(item: SearchItem) => {
                      const Icon = navIcons[item.icon]
                      return (
                        <CommandItem key={item.value} value={item} onClick={() => go(item)}>
                          <Icon className="mr-2 size-4 opacity-70" />
                          {item.label}
                        </CommandItem>
                      )
                    }}
                  </CommandCollection>
                </CommandGroup>
              )}
            </CommandList>
          </CommandPanel>
        </Command>
      </CommandDialogPopup>
    </CommandDialog>
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
              <AvatarFallback className="bg-sidebar-primary text-sidebar-primary-foreground text-xs ring-2 ring-sidebar-border">{initials}</AvatarFallback>
            </Avatar>
            <div className="grid min-w-0 flex-1 text-left leading-tight">
              <span className="truncate text-sm font-medium">{user?.full_name ?? ''}</span>
              <span className="truncate text-xs text-sidebar-foreground/85">{isAdmin ? 'Administrador' : 'Docente'}</span>
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
  const [searchOpen, setSearchOpen] = useState(false)

  return (
    <>
      <Sidebar collapsible="icon">
        {/* The 3rem collapsed rail leaves room for p-2 plus the 2rem badge, the same box as the menu icons. */}
        <SidebarHeader className="px-4 py-3 group-data-[collapsible=icon]:px-2">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-sidebar-primary text-sm font-black text-sidebar-primary-foreground shadow-md shadow-black/25 ring-1 ring-sidebar-border">
              S
            </div>
            <div className="grid min-w-0 leading-tight group-data-[collapsible=icon]:hidden">
              <span className="truncate text-sm font-bold tracking-wide text-sidebar-accent-foreground">UPDS</span>
              <span className="truncate text-[10px] font-medium uppercase tracking-[0.18em] text-sidebar-foreground/85">
                Sistema de Pago
              </span>
            </div>
          </div>
        </SidebarHeader>

        {isAdmin ? (
          <AdminSidebarBody onOpenSearch={() => setSearchOpen(true)} />
        ) : (
          <>
            <SidebarContent className="bg-sidebar-glow">
              <DocenteSidebarNav />
            </SidebarContent>
            <SidebarFooter>
              <UserMenu />
            </SidebarFooter>
          </>
        )}
        <SidebarRail />
      </Sidebar>
      {isAdmin && <AdminSearchDialog open={searchOpen} onOpenChange={setSearchOpen} />}
    </>
  )
}
