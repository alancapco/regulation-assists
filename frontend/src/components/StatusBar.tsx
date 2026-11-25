import { useCallback, useEffect, useState } from "react"
import { api } from "@/api/client"
import type { AppStatus } from "@/types/contract"

export function StatusBar() {
  const [status, setStatus] = useState<AppStatus | null>(null)
  const refresh = useCallback(() => {
    // F-008: fetch once on mount and on window focus — no polling; any disconnect/failure shows red.
    api.status().then(setStatus).catch(() => setStatus(null))
  }, [])

  useEffect(() => {
    refresh()
    window.addEventListener("focus", refresh)
    return () => window.removeEventListener("focus", refresh)
  }, [refresh])

  const ok = status?.connected === true
  return (
    <div role="status" aria-live="polite"
         className="flex items-center gap-2 text-sm text-muted-foreground">
      <span aria-hidden="true">{ok ? "🟢" : "🔴"}</span>
      <span>Neo4j: {ok ? "Connected" : "Disconnected"}</span>
      {status && (
        <span>Loaded {status.regulation_count}/{status.total_count} regulations</span>
      )}
    </div>
  )
}
