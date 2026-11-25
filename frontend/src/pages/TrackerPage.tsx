import { useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { api } from "@/api/client"
import { useApi } from "@/hooks/useApi"
import type { FilterOptions, Regulation, TrackerParams, TypeItem, StatusItem } from "@/types/contract"
import { statusLabel } from "@/lib/statusLabel"
import { EmptyState } from "@/components/EmptyState"
import { ErrorState } from "@/components/ErrorState"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

const ALL = "__all__"

export default function TrackerPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const q = searchParams.get("q") ?? ""
  const jurisdiction = searchParams.get("jurisdiction") ?? ""
  const type = searchParams.get("type") ?? ""
  const legal_force = searchParams.get("legal_force") ?? ""
  const topic = searchParams.get("topic") ?? ""

  const [localQ, setLocalQ] = useState(q)

  const params: TrackerParams = { q, jurisdiction, type, legal_force, topic }

  const { data, loading, error, refetch } = useApi<Regulation[]>(
    () => api.tracker(params),
    [searchParams.toString()]
  )
  const { data: filters } = useApi<FilterOptions>(() => api.filters(), [])
  const { data: typeItems } = useApi<TypeItem[]>(() => api.types(), [])
  const { data: statusItems } = useApi<StatusItem[]>(() => api.statuses(), [])

  const rows = data ?? []
  const typeOptions = typeItems?.map((t) => t.type) ?? filters?.types ?? []
  const statusOptions = statusItems?.map((s) => s.status) ?? filters?.legal_forces ?? []

  const setParam = (key: string, value: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (value) next.set(key, value)
      else next.delete(key)
      return next
    })
  }

  const applySearch = () => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (localQ) next.set("q", localQ)
      else next.delete("q")
      return next
    })
  }

  const reset = () => {
    setLocalQ("")
    setSearchParams({})
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Regulation Tracker</h1>

      <Card>
        <CardContent className="p-4 space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <Input
              className="min-w-[200px] flex-1"
              placeholder="Search regulations…"
              value={localQ}
              onChange={(e) => setLocalQ(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") applySearch() }}
              aria-label="Search keywords"
            />
            <FilterSelect value={jurisdiction} options={filters?.jurisdictions ?? []}
              allLabel="All jurisdictions" onChange={(v) => setParam("jurisdiction", v)} />
            <FilterSelect value={type} options={typeOptions}
              allLabel="All types" onChange={(v) => setParam("type", v)} />
            <FilterSelect value={legal_force} options={statusOptions}
              allLabel="All statuses" onChange={(v) => setParam("legal_force", v)} />
            <FilterSelect value={topic} options={filters?.topics ?? []}
              allLabel="All topics" onChange={(v) => setParam("topic", v)} />
          </div>
          <div className="flex gap-2">
            <Button onClick={applySearch}>Search</Button>
            <Button variant="outline" onClick={reset}>Reset</Button>
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead><TableHead>Jurisdiction</TableHead>
                <TableHead>Year</TableHead><TableHead>Type</TableHead>
                <TableHead>Status</TableHead><TableHead>Topics</TableHead><TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}><TableCell colSpan={7}><Skeleton className="h-6 w-full" /></TableCell></TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : error ? (
        <ErrorState message={error} action={<Button onClick={refetch}>Retry</Button>} />
      ) : rows.length === 0 ? (
        <EmptyState message="No regulations match your filters"
          action={<Button variant="outline" onClick={reset}>Clear filters</Button>} />
      ) : (
        <>
          <p className="text-sm text-muted-foreground">Total {rows.length} regulations</p>
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Jurisdiction</TableHead>
                  <TableHead>Year</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Topics</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => {
                  const year = r.legislation_date ? r.legislation_date.slice(0, 4) : "—"
                  const shownTopics = r.topics.slice(0, 2)
                  const extraTopics = r.topics.length - 2
                  return (
                    <TableRow key={r.instrument_id} className="cursor-pointer"
                      role="button" tabIndex={0}
                      aria-label={`View details for ${r.name}`}
                      onClick={() => navigate(`/regulations/${r.instrument_id}`)}
                      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); navigate(`/regulations/${r.instrument_id}`) } }}>
                      <TableCell className="max-w-[280px] truncate font-medium">{r.name}</TableCell>
                      <TableCell className="whitespace-nowrap">{r.jurisdiction || "—"}</TableCell>
                      <TableCell className="tabular-nums">{year}</TableCell>
                      <TableCell>{r.type ? <Badge variant="outline">{r.type}</Badge> : "—"}</TableCell>
                      <TableCell>{r.legal_force ? <Badge variant="secondary">{statusLabel(r.legal_force)}</Badge> : "—"}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {shownTopics.map((t) => (
                            <span key={t} className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">{t}</span>
                          ))}
                          {extraTopics > 0 && (
                            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">+{extraTopics}</span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Button variant="outline" size="sm"
                          onClick={(e) => { e.stopPropagation(); navigate(`/regulations/${r.instrument_id}`) }}>
                          View
                        </Button>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        </>
      )}
    </div>
  )
}

function FilterSelect({ value, options, allLabel, onChange }: {
  value: string; options: string[]; allLabel: string; onChange: (v: string) => void
}) {
  return (
    <Select value={value || ALL} onValueChange={(v) => onChange(v === ALL ? "" : v)}>
      <SelectTrigger className="min-w-[160px]"><SelectValue placeholder={allLabel} /></SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>{allLabel}</SelectItem>
        {options.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}
      </SelectContent>
    </Select>
  )
}
