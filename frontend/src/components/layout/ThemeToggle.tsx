import { Monitor, Moon, Sun, type LucideIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Menu, MenuPopup, MenuRadioGroup, MenuRadioItem, MenuTrigger } from '@/components/ui/menu'
import { useTheme } from '@/context/ThemeContext'
import type { ThemePreference } from '@/lib/theme'
import { cn } from '@/lib/utils'

const OPTIONS: { value: ThemePreference; label: string; Icon: LucideIcon }[] = [
  { value: 'light', label: 'Claro', Icon: Sun },
  { value: 'dark', label: 'Oscuro', Icon: Moon },
  { value: 'system', label: 'Sistema', Icon: Monitor },
]

const VARIANT_CLASS = {
  default: '',
  // Sits on the dark brand band, like the "Salir" button.
  brand: 'border-brand-foreground/30 bg-brand-foreground/10 text-brand-foreground hover:bg-brand-foreground/20 hover:text-brand-foreground',
} as const

export function ThemeToggle({ variant = 'default', className }: { variant?: keyof typeof VARIANT_CLASS; className?: string }) {
  const { preference, setPreference } = useTheme()
  const current = OPTIONS.find((option) => option.value === preference) ?? OPTIONS[2]
  const CurrentIcon = current.Icon

  return (
    <Menu>
      <MenuTrigger
        render={
          <Button
            type="button"
            variant={variant === 'brand' ? 'outline' : 'ghost'}
            size="icon"
            aria-label={`Tema: ${current.label}`}
            title={`Tema: ${current.label}`}
            className={cn(VARIANT_CLASS[variant], className)}
          />
        }
      >
        <CurrentIcon aria-hidden="true" />
      </MenuTrigger>
      <MenuPopup align="end" className="min-w-40">
        <MenuRadioGroup
          aria-label="Tema de la interfaz"
          value={preference}
          onValueChange={(next) => setPreference(next as ThemePreference)}
        >
          {OPTIONS.map(({ value, label, Icon }) => (
            <MenuRadioItem key={value} value={value} aria-label={`Tema: ${label}`}>
              <span className="flex items-center gap-2"><Icon aria-hidden="true" />{label}</span>
            </MenuRadioItem>
          ))}
        </MenuRadioGroup>
      </MenuPopup>
    </Menu>
  )
}
