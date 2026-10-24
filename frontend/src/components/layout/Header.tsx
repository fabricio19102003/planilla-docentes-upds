import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Bell, BookOpen, Layers, Search, Users } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { useUnreadCount } from '@/api/hooks/useNotifications'
import { getTitleFromPath } from '@/lib/navigation'
import { api } from '@/api/client'
import { Button } from '@/components/ui/button'
import {
  Autocomplete,
  AutocompleteCollection,
  AutocompleteEmpty,
  AutocompleteGroup,
  AutocompleteGroupLabel,
  AutocompleteInput,
  AutocompleteItem,
  AutocompleteList,
  AutocompletePopup,
} from '@/components/ui/autocomplete'
import { SidebarTrigger } from '@/components/ui/sidebar'

interface SearchResults {
  teachers: { ci: string; full_name: string; email: string | null }[]
  subjects: { subject: string; semester: string }[]
  groups: { group_code: string }[]
}

interface SearchItem {
  id: string
  kind: 'teacher' | 'subject' | 'group'
  label: string
  meta?: string
  ci?: string
}

interface SearchGroup {
  value: string
  items: SearchItem[]
}

function toSearchGroups(results: SearchResults | null): SearchGroup[] {
  if (!results) return []
  const groups: SearchGroup[] = [
    {
      value: 'Docentes',
      items: (results.teachers ?? []).map((t) => ({
        id: `teacher-${t.ci}`,
        kind: 'teacher',
        label: t.full_name,
        meta: `CI: ${t.ci}`,
        ci: t.ci,
      })),
    },
    {
      value: 'Materias',
      items: (results.subjects ?? []).map((s) => ({
        id: `subject-${s.subject}-${s.semester}`,
        kind: 'subject',
        label: s.subject,
        meta: s.semester,
      })),
    },
    {
      value: 'Grupos',
      items: (results.groups ?? []).map((g) => ({ id: `group-${g.group_code}`, kind: 'group', label: g.group_code })),
    },
  ]
  return groups.filter((group) => group.items.length > 0)
}

const SEARCH_ICONS = { teacher: Users, subject: BookOpen, group: Layers } as const

export function Header() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { isAdmin, isDocente } = useAuth()
  const title = getTitleFromPath(pathname)
  const { data: unreadCount = 0 } = useUnreadCount(isDocente)

  // Global search state
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResults | null>(null)
  const [searchOpen, setSearchOpen] = useState(false)
  const searchGroups = toSearchGroups(searchResults)

  // Debounced search
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- Clear stale search results immediately when the query is too short.
    if (searchQuery.length < 2) { setSearchResults(null); return }
    const timer = setTimeout(async () => {
      try {
        const res = await api.get<SearchResults>(`/search?q=${encodeURIComponent(searchQuery)}`)
        setSearchResults(res.data)
      } catch {
        setSearchResults(null)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  const openItem = (item: SearchItem) => {
    if (item.kind === 'teacher' && item.ci) navigate(`/teachers/${item.ci}`)
    setSearchOpen(false)
    setSearchQuery('')
    setSearchResults(null)
  }

  return (
    <header className="sticky top-0 z-30 flex min-h-14 flex-wrap items-center gap-2 border-b bg-background/85 px-3 py-2 backdrop-blur supports-[backdrop-filter]:bg-background/70 sm:px-4 md:flex-nowrap md:px-6">
      <div className="flex min-w-0 items-center gap-2">
        <SidebarTrigger
          aria-label="Abrir menú de navegación"
          className="size-9 flex-shrink-0 md:hidden"
        />
        <SidebarTrigger
          aria-label="Mostrar u ocultar el menú lateral"
          className="hidden flex-shrink-0 md:inline-flex"
        />
        <h1 className="truncate text-base font-semibold text-foreground sm:text-lg md:text-xl">
          {title}
        </h1>
      </div>

      {/* Global search — admin only */}
      {isAdmin && (
        <div className="order-last relative w-full flex-1 md:order-none md:mx-4 md:max-w-md">
          <Autocomplete
            items={searchGroups}
            filter={null}
            value={searchQuery}
            onValueChange={(next, details) => {
              if (details.reason === 'item-press') return
              setSearchQuery(next)
              setSearchOpen(true)
            }}
            open={searchOpen && searchResults !== null}
            onOpenChange={setSearchOpen}
            itemToStringValue={(item: SearchItem | SearchGroup) => ('label' in item ? item.label : item.value)}
          >
            <AutocompleteInput
              aria-label="Buscar docente, materia o grupo"
              placeholder="Buscar docente, materia o grupo..."
              startAddon={<Search aria-hidden="true" />}
            />
            <AutocompletePopup>
              <AutocompleteEmpty>Sin resultados para &ldquo;{searchQuery}&rdquo;</AutocompleteEmpty>
              <AutocompleteList>
                {(group: SearchGroup) => (
                  <AutocompleteGroup key={group.value} items={group.items}>
                    <AutocompleteGroupLabel>{group.value}</AutocompleteGroupLabel>
                    <AutocompleteCollection>
                      {(item: SearchItem) => {
                        const Icon = SEARCH_ICONS[item.kind]
                        return (
                          <AutocompleteItem key={item.id} value={item} onClick={() => openItem(item)}>
                            <Icon size={14} className="mr-2 flex-shrink-0 text-muted-foreground" aria-hidden="true" />
                            <span className="truncate">{item.label}</span>
                            {item.meta && (
                              <span className="ml-auto flex-shrink-0 pl-3 text-xs text-muted-foreground">{item.meta}</span>
                            )}
                          </AutocompleteItem>
                        )
                      }}
                    </AutocompleteCollection>
                  </AutocompleteGroup>
                )}
              </AutocompleteList>
            </AutocompletePopup>
          </Autocomplete>
        </div>
      )}

      {/* Notification bell — docentes only */}
      <div className="ml-auto flex items-center gap-2">
        {isDocente && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => navigate('/portal/notifications')}
            className="relative"
            aria-label={unreadCount > 0 ? `Notificaciones, ${unreadCount} sin leer` : 'Notificaciones'}
          >
            <Bell />
            {unreadCount > 0 && (
              <span className="absolute -right-1 -top-1 flex size-4 items-center justify-center rounded-full bg-destructive text-[10px] font-bold text-white">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </Button>
        )}
      </div>
    </header>
  )
}
