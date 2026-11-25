import { useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { api } from "@/api/client"
import { useApi } from "@/hooks/useApi"
import type { FilterOptions, GraphData, GraphNode } from "@/types/contract"
import D3ForceGraph from "@/components/D3ForceGraph"
import { EmptyState } from "@/components/EmptyState"
import { ErrorState } from "@/components/ErrorState"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"

// Radix Select rejects an empty value, so use a sentinel to represent "All".
const ALL = "__ALL__"

export default function GraphPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [hoverNode, setHoverNode] = useState<GraphNode | null>(null)

  const jurisdiction = searchParams.get("jurisdiction") ?? ""
  const topic = searchParams.get("topic") ?? ""

  // Filter changes go into deps → refetch; graph data carries no filter state, owned here.
  const { data, loading, error, refetch } = useApi<GraphData>(
    () => api.graph({ jurisdiction, topic }),
    [jurisdiction, topic]
  )
  const { data: filters } = useApi<FilterOptions>(() => api.filters(), [])

  const nodes = data?.nodes ?? []
  const links = data?.links ?? []
  // Contract has no truncated field; infer the hint from node count exceeding the cap.
  const truncated = nodes.length >= 100

  const setParam = (key: string, value: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (value) next.set(key, value)
      else next.delete(key)
      return next
    })
  }

  const resetAll = () => setSearchParams(new URLSearchParams())

  // Only Regulation nodes are clickable; their id has no prefix, so route straight to detail.
  const onNodeClick = (node: GraphNode) => {
    if (node.type === "regulation") navigate(`/regulations/${node.id}`)
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Knowledge Graph</h1>

      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex min-w-[180px] flex-col gap-1">
            <label className="text-xs text-muted-foreground">Jurisdiction</label>
            <Select value={jurisdiction || ALL}
              onValueChange={(v) => setParam("jurisdiction", v === ALL ? "" : v)}>
              <SelectTrigger aria-label="Jurisdiction"><SelectValue placeholder="All" /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All</SelectItem>
                {(filters?.jurisdictions ?? []).map((j) => (
                  <SelectItem key={j} value={j}>{j}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex min-w-[180px] flex-col gap-1">
            <label className="text-xs text-muted-foreground">Topic</label>
            <Select value={topic || ALL}
              onValueChange={(v) => setParam("topic", v === ALL ? "" : v)}>
              <SelectTrigger aria-label="Topic"><SelectValue placeholder="All" /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All</SelectItem>
                {(filters?.topics ?? []).map((t) => (
                  <SelectItem key={t} value={t}>{t}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button variant="ghost" onClick={resetAll}>Reset View</Button>
        </div>
      </Card>

      {loading ? (
        <div className="flex h-[480px] flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
          <Skeleton className="h-40 w-40 rounded-full" />
          <span>Rendering graph…</span>
        </div>
      ) : error ? (
        <ErrorState message={error} action={<Button onClick={refetch}>Retry</Button>} />
      ) : nodes.length === 0 ? (
        <EmptyState message="No nodes match the current filters"
          action={<Button onClick={resetAll}>Reset View</Button>} />
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">{nodes.length} nodes / {links.length} links</p>
            {truncated && (
              <p className="text-sm text-muted-foreground">Large dataset — use filters to narrow the view</p>
            )}
          </div>

          <Card className="relative overflow-hidden" style={{ minHeight: 520, height: 520 }}>
            {/* D3ForceGraph renders its own 4-type legend (shape+color+label) and handles click/hover/drag/zoom. */}
            <D3ForceGraph
              className="w-full h-full"
              nodes={nodes}
              links={links}
              onNodeClick={onNodeClick}
              onNodeHover={setHoverNode}
            />
            {hoverNode && (
              <div className="pointer-events-none absolute bottom-3 left-3 rounded-md bg-slate-900 px-2 py-1 text-xs text-white shadow">
                {hoverNode.label} · {hoverNode.type}
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
