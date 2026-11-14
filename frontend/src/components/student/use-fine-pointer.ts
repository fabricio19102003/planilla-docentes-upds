import { useSyncExternalStore } from 'react'

const QUERY = '(hover: hover) and (pointer: fine)'

function subscribe(onChange: () => void) {
  const media = window.matchMedia(QUERY)
  media.addEventListener('change', onChange)
  return () => media.removeEventListener('change', onChange)
}

/** True on devices with a hovering fine pointer (mouse, trackpad). Touch screens get no hover-only effects. */
export function useFinePointer(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(QUERY).matches,
    () => false,
  )
}
