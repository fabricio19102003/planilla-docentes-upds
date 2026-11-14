import { useEffect, useState } from 'react'

/** The current time, refreshed every minute so "Hoy" and "En 34 min" do not go stale while the page stays open. */
export function useNow(): Date {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 60_000)
    return () => window.clearInterval(timer)
  }, [])
  return now
}
