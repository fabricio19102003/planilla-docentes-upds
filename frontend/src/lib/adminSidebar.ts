import {
  getActiveGroupLabel,
  isNavGroup,
  type AdminNavEntry,
  type NavGroupDef,
  type NavItemDef,
} from './navigation.ts'

/** Groups rendered in the sidebar footer, above the user menu. They share the single-open accordion. */
export const FOOTER_GROUP_LABELS = ['Sistema']

const SEARCH_HOME_SECTION = 'Inicio'
const ADMIN_CHAT_PATH = '/chat'

export interface SearchItem extends NavItemDef {
  /** Path used as the stable item value. */
  value: string
  section: string
}

export interface SearchSection {
  value: string
  items: SearchItem[]
}

export function splitAdminGroups(entries: AdminNavEntry[]): {
  topLevel: NavItemDef[]
  main: NavGroupDef[]
  footer: NavGroupDef[]
} {
  const groups = entries.filter(isNavGroup)
  return {
    topLevel: entries.filter((entry): entry is NavItemDef => !isNavGroup(entry)),
    main: groups.filter((group) => !FOOTER_GROUP_LABELS.includes(group.label)),
    footer: groups.filter((group) => FOOTER_GROUP_LABELS.includes(group.label)),
  }
}

/** Single-open accordion: opening a group closes the others; toggling the open one closes all. */
export function toggleOpenGroup(openGroup: string | null, label: string): string | null {
  return openGroup === label ? null : label
}

/** The group of the current route opens; routes outside any group leave the accordion as it is. */
export function syncOpenGroup(openGroup: string | null, pathname: string, entries: AdminNavEntry[]): string | null {
  return getActiveGroupLabel(pathname, entries) ?? openGroup
}

/** Every admin page once, grouped by section, shaped for the grouped command list. */
export function getSearchSections(entries: AdminNavEntry[]): SearchSection[] {
  const toItem = (item: NavItemDef, section: string): SearchItem => ({ ...item, value: item.to, section })
  const topLevel = entries.filter((entry): entry is NavItemDef => !isNavGroup(entry))
  const sections: SearchSection[] = []
  if (topLevel.length > 0) {
    sections.push({ value: SEARCH_HOME_SECTION, items: topLevel.map((item) => toItem(item, SEARCH_HOME_SECTION)) })
  }
  for (const group of entries.filter(isNavGroup)) {
    sections.push({ value: group.label, items: group.children.map((item) => toItem(item, group.label)) })
  }
  return sections
}

/** A closed group that holds the inbox flags unread messages with a dot. */
export function showGroupPendingDot(group: NavGroupDef, unreadCount: number, isOpen: boolean): boolean {
  return unreadCount > 0 && !isOpen && group.children.some((child) => child.to === ADMIN_CHAT_PATH)
}

export interface SearchShortcutEvent {
  key: string
  ctrlKey: boolean
  metaKey: boolean
  altKey: boolean
  shiftKey: boolean
  target: { tagName?: string; isContentEditable?: boolean } | null
}

const EDITABLE_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT'])

/** Ctrl+K / Cmd+K, ignored while the user is typing in a field. */
export function isSearchShortcut(event: SearchShortcutEvent): boolean {
  if (event.key.toLowerCase() !== 'k' || event.altKey || event.shiftKey) return false
  if (!event.ctrlKey && !event.metaKey) return false
  const target = event.target
  if (target && (target.isContentEditable || EDITABLE_TAGS.has(target.tagName?.toUpperCase() ?? ''))) return false
  return true
}
