export type ThemePreference = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

export const THEME_STORAGE_KEY = 'sipad-theme'

const PREFERENCES: readonly ThemePreference[] = ['light', 'dark', 'system']

/** Reads the remembered choice; anything missing, invalid or unreadable means "system". */
export function readStoredPreference(storage: Pick<Storage, 'getItem'> | null): ThemePreference {
  try {
    const value = storage?.getItem(THEME_STORAGE_KEY)
    return PREFERENCES.find((preference) => preference === value) ?? 'system'
  } catch {
    return 'system'
  }
}

export function resolveTheme(preference: ThemePreference, systemPrefersDark: boolean): ResolvedTheme {
  if (preference === 'system') return systemPrefersDark ? 'dark' : 'light'
  return preference
}
