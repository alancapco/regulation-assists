import { useState } from "react"
import { api } from "@/api/client"
import { useApi } from "@/hooks/useApi"
import type { StatusItem } from "@/types/contract"
import { statusLabel } from "@/lib/statusLabel"
import { ErrorState } from "@/components/ErrorState"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

const LIFECYCLE_STEPS = ["Draft", "Proposed", "Under Review", "Adopted", "Awaiting Entry", "In Force"]
const PHASES = ["All", "Pre-Legislative", "Legislative Process", "Post-Legislative", "Active", "Final"] as const
type Phase = (typeof PHASES)[number]

const PHASE_COLORS: Record<string, string> = {
  "Pre-Legislative": "bg-yellow-100 text-yellow-800",
  "Legislative Process": "bg-blue-100 text-blue-800",
  "Post-Legislative": "bg-purple-100 text-purple-800",
  "Active": "bg-green-100 text-green-800",
  "Final": "bg-gray-200 text-gray-700",
}

export default function StatusesPage() {
  const [phase, setPhase] = useState<Phase>("All")
  const { data, loading, error, refetch } = useApi<StatusItem[]>(() => api.statuses(), [])

  const items = data ?? []
  const filtered = items.filter((s) => phase === "All" || s.phase === phase)

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Regulation Lifecycle</h1>

      {/* Lifecycle flow header */}
      <div className="flex items-center gap-1 overflow-x-auto rounded-xl border bg-white px-6 py-4 shadow-sm">
        {LIFECYCLE_STEPS.map((step, i) => (
          <div key={step} className="flex items-center gap-1 shrink-0">
            {i > 0 && <span className="text-gray-400 mx-1">→</span>}
            <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700">{step}</span>
          </div>
        ))}
      </div>

      {/* Phase filter tabs */}
      <div className="flex flex-wrap gap-2">
        {PHASES.map((p) => (
          <button key={p} onClick={() => setPhase(p)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              phase === p ? "bg-black text-white" : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
            }`}>
            {p}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-32 rounded-xl" />)}
        </div>
      ) : error ? (
        <ErrorState message={error} action={<Button onClick={refetch}>Retry</Button>} />
      ) : filtered.length === 0 ? (
        <p className="text-sm text-muted-foreground">No statuses for this phase.</p>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">{filtered.length} status{filtered.length !== 1 ? "es" : ""}</p>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filtered.map((s) => (
              <div key={s.status} className="rounded-xl border bg-white p-5 shadow-sm flex flex-col gap-3">
                <div className="flex items-start justify-between gap-2">
                  <h2 className="font-semibold leading-snug">{statusLabel(s.status)}</h2>
                  <span className={`shrink-0 rounded px-2 py-0.5 text-xs font-medium ${PHASE_COLORS[s.phase] ?? "bg-gray-100 text-gray-600"}`}>
                    {s.phase}
                  </span>
                </div>
                <p className="text-sm text-muted-foreground">{s.description}</p>
                <div className="mt-auto pt-2 border-t border-gray-100 text-xs text-muted-foreground tabular-nums">
                  {s.count} regulation{s.count !== 1 ? "s" : ""}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
