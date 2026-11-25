import { useState } from "react"
import { api } from "@/api/client"
import { useApi } from "@/hooks/useApi"
import type { GovernanceArea, GovernanceData } from "@/types/contract"
import { ErrorState } from "@/components/ErrorState"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

type Priority = "All" | "Critical" | "High" | "Medium"
const ROLE_FILTERS = ["All", "Board", "Legal+Compliance", "Engineering+DevOps", "HR"] as const
type RoleFilter = (typeof ROLE_FILTERS)[number]

const PRIORITY_BADGE: Record<GovernanceArea["priority"], string> = {
  Critical: "bg-black text-white",
  High: "border border-gray-400 text-gray-700",
  Medium: "bg-gray-100 text-gray-600",
}

export default function GovernancePage() {
  const [roleFilter, setRoleFilter] = useState<RoleFilter>("All")
  const [priorityFilter, setPriorityFilter] = useState<Priority>("All")
  const { data, loading, error, refetch } = useApi<GovernanceData>(() => api.governance(), [])

  const areas = data?.areas ?? []
  const filtered = areas.filter((a) => {
    if (priorityFilter !== "All" && a.priority !== priorityFilter) return false
    if (roleFilter !== "All") {
      const roleLower = roleFilter.toLowerCase()
      return a.roles.some((r) => r.toLowerCase().includes(roleLower.split("+")[0]))
    }
    return true
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">AI Governance Framework</h1>
        <p className="text-sm text-muted-foreground">12 areas mapped to regulations</p>
      </div>

      {/* Role filter chips */}
      <div className="flex flex-wrap gap-2">
        {ROLE_FILTERS.map((r) => (
          <button key={r} onClick={() => setRoleFilter(r)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              roleFilter === r ? "bg-black text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}>
            {r}
          </button>
        ))}
      </div>

      {/* Priority filter */}
      <div className="flex flex-wrap gap-2">
        {(["All", "Critical", "High", "Medium"] as Priority[]).map((p) => (
          <button key={p} onClick={() => setPriorityFilter(p)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              priorityFilter === p
                ? "bg-black text-white"
                : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
            }`}>
            {p}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-56 rounded-xl" />)}
        </div>
      ) : error ? (
        <ErrorState message={error} action={<Button onClick={refetch}>Retry</Button>} />
      ) : (
        <>
          <p className="text-sm text-muted-foreground">{filtered.length} area{filtered.length !== 1 ? "s" : ""}</p>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {filtered.map((a) => <AreaCard key={a.id} area={a} />)}
          </div>
        </>
      )}
    </div>
  )
}

function AreaCard({ area }: { area: GovernanceArea }) {
  const shownElements = area.key_elements.slice(0, 3)
  const remaining = area.key_elements.length - 3
  return (
    <div className="rounded-xl border bg-white p-5 shadow-sm flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${PRIORITY_BADGE[area.priority]}`}>
          {area.priority}
        </span>
      </div>
      <h2 className="font-semibold leading-snug">{area.title}</h2>
      <p className="text-sm text-muted-foreground">{area.description}</p>
      {area.roles.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {area.roles.map((r) => (
            <span key={r} className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">{r}</span>
          ))}
        </div>
      )}
      {shownElements.length > 0 && (
        <ul className="space-y-1 text-sm text-gray-700">
          {shownElements.map((el) => <li key={el} className="flex gap-1.5"><span className="mt-0.5 shrink-0 text-gray-400">·</span>{el}</li>)}
          {remaining > 0 && <li className="text-xs text-muted-foreground">+{remaining} more</li>}
        </ul>
      )}
      <div className="mt-auto pt-2 border-t border-gray-100 text-xs text-muted-foreground tabular-nums">
        {area.regulation_count} regulation{area.regulation_count !== 1 ? "s" : ""}
      </div>
    </div>
  )
}
