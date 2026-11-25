import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { api } from "@/api/client"
import { useApi } from "@/hooks/useApi"
import type { TypeItem } from "@/types/contract"
import { ErrorState } from "@/components/ErrorState"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

type BindingFilter = "all" | "binding" | "non-binding" | "proposal"

const LIFECYCLE_STEPS = ["Draft", "Proposed", "Adopted", "In Force"]

export default function TypesPage() {
  const navigate = useNavigate()
  const [filter, setFilter] = useState<BindingFilter>("all")
  const { data, loading, error, refetch } = useApi<TypeItem[]>(() => api.types(), [])

  const items = data ?? []
  const filtered = items.filter((t) => {
    if (filter === "binding") return t.binding
    if (filter === "non-binding") return !t.binding && !t.type.toLowerCase().includes("proposal") && !t.type.toLowerCase().includes("draft")
    if (filter === "proposal") return t.type.toLowerCase().includes("proposal") || t.type.toLowerCase().includes("draft")
    return true
  })

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Regulation Types</h1>

      {/* Lifecycle flow */}
      <div className="flex items-center gap-1 overflow-x-auto rounded-xl border bg-white px-6 py-4 shadow-sm">
        {LIFECYCLE_STEPS.map((step, i) => (
          <div key={step} className="flex items-center gap-1 shrink-0">
            {i > 0 && <span className="text-gray-400 mx-1">→</span>}
            <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700">{step}</span>
          </div>
        ))}
      </div>

      {/* Binding filter tabs */}
      <div className="flex gap-2">
        {([
          { key: "all", label: "All" },
          { key: "binding", label: "Binding" },
          { key: "non-binding", label: "Non-binding" },
          { key: "proposal", label: "Proposals/Drafts" },
        ] as { key: BindingFilter; label: string }[]).map(({ key, label }) => (
          <button key={key} onClick={() => setFilter(key)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              filter === key ? "bg-black text-white" : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
            }`}>
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-36 rounded-xl" />)}
        </div>
      ) : error ? (
        <ErrorState message={error} action={<Button onClick={refetch}>Retry</Button>} />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filtered.map((t) => (
            <div key={t.type} className="rounded-xl border bg-white p-5 shadow-sm flex flex-col gap-3">
              <div className="flex items-start justify-between gap-2">
                <h2 className="font-semibold leading-snug">{t.type}</h2>
                <span className={`shrink-0 rounded px-2 py-0.5 text-xs font-medium ${
                  t.binding ? "bg-black text-white" : "border border-gray-300 text-gray-600"
                }`}>
                  {t.binding ? "Binding" : "Non-binding"}
                </span>
              </div>
              <p className="text-sm text-muted-foreground">{t.description}</p>
              <div className="mt-auto flex items-center justify-between pt-2 border-t border-gray-100">
                <span className="text-xs text-muted-foreground tabular-nums">{t.count} regulations</span>
                <button onClick={() => navigate(`/regulations/tracker?type=${encodeURIComponent(t.type)}`)}
                  className="text-xs text-blue-600 hover:underline">View in Tracker →</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
