// U-FE-01 · P-001 regulations list page (replace U-000 stub; exclusive write path, this single file).
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { api } from "@/api/client"
import { useApi } from "@/hooks/useApi"
import type { FilterOptions, Regulation, RegulationQuery } from "@/types/contract"
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

// Sentinel "All" value for the 4 selects: Radix Select forbids an empty SelectItem value, hence the placeholder sentinel.
const ALL = "__all__"
const PARAM_KEYS = ["q", "jurisdiction", "type", "legal_force", "topic", "date_from", "date_to"] as const
const EMPTY_FILTERS: FilterOptions = { jurisdictions: [], types: [], legal_forces: [], topics: [] }

type FormState = Record<(typeof PARAM_KEYS)[number], string>
type SortKey = "name" | "legislation_date" | null
type SortState = { key: SortKey; dir: "asc" | "desc" }

function readForm(sp: URLSearchParams): FormState {
  return PARAM_KEYS.reduce((acc, k) => {
    acc[k] = sp.get(k) ?? ""
    return acc
  }, {} as FormState)
}

// Clicking the name / legislation_date headers sorts client-side; null legislation_date sorts last.
function sortRows(rows: Regulation[], sort: SortState): Regulation[] {
  if (!sort.key) return rows
  const dir = sort.dir === "asc" ? 1 : -1
  return [...rows].sort((a, b) => {
    if (sort.key === "name") return a.name.localeCompare(b.name) * dir
    const av = a.legislation_date
    const bv = b.legislation_date
    if (av == null && bv == null) return 0
    if (av == null) return 1
    if (bv == null) return -1
    return av.localeCompare(bv) * dir
  })
}

function FilterSelect({ value, options, allLabel, onChange }: {
  value: string
  options: string[]
  allLabel: string
  onChange: (v: string) => void
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

export default function RegulationsPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  // The form is the sole edit state; the URL is the committed state (shareable/backable), synced via apply.
  const [form, setFormState] = useState<FormState>(() => readForm(searchParams))
  const formRef = useRef(form)
  const [dateError, setDateError] = useState<string | null>(null)
  const [sort, setSort] = useState<SortState>({ key: null, dir: "asc" })

  // Hold the latest form in a ref to avoid stale closures in the debounce/Select callbacks.
  const setForm = useCallback((patch: Partial<FormState>) => {
    formRef.current = { ...formRef.current, ...patch }
    setFormState(formRef.current)
  }, [])

  // When external URL changes (back/forward) occur, sync the form back to the controls.
  useEffect(() => { setForm(readForm(searchParams)) }, [searchParams, setForm])

  // Write the current form to the URL. date_from > date_to is invalid — block submit and warn.
  const apply = useCallback(() => {
    const v = formRef.current
    if (v.date_from && v.date_to && v.date_from > v.date_to) {
      setDateError("End date cannot be earlier than start date")
      return
    }
    setDateError(null)
    const next = PARAM_KEYS.reduce((acc, k) => {
      if (v[k]) acc[k] = v[k]
      return acc
    }, {} as Record<string, string>)
    setSearchParams(next)
  }, [setSearchParams])

  // q debounces 300ms and auto-submits; other controls use explicit apply / the Search button.
  const qTimer = useRef<ReturnType<typeof setTimeout>>()
  const onQChange = useCallback((val: string) => {
    setForm({ q: val })
    if (qTimer.current) clearTimeout(qTimer.current)
    qTimer.current = setTimeout(() => apply(), 300)
  }, [setForm, apply])
  useEffect(() => () => { if (qTimer.current) clearTimeout(qTimer.current) }, [])

  const reset = useCallback(() => {
    setForm(readForm(new URLSearchParams()))
    setDateError(null)
    setSearchParams({})
  }, [setForm, setSearchParams])

  const toggleSort = useCallback((key: Exclude<SortKey, null>) => {
    setSort((s) => {
      if (s.key !== key) return { key, dir: "asc" }
      if (s.dir === "asc") return { key, dir: "desc" }
      return { key: null, dir: "asc" }
    })
  }, [])

  // Committed state drives the query: a URL change refetches, naturally supporting back/forward and refresh.
  const query = useMemo<RegulationQuery>(() => readForm(searchParams) as RegulationQuery, [searchParams])
  const { data, loading, error, refetch } = useApi<Regulation[]>(
    () => api.regulations(query),
    [searchParams.toString()],
  )

  // Filter dictionary: on 503 when the DB is down, degrade to "All only" so search is never blocked.
  const { data: filterData, error: filterError } = useApi<FilterOptions>(() => api.filters(), [])
  const filterOptions = filterError ? EMPTY_FILTERS : (filterData ?? EMPTY_FILTERS)

  const rows = useMemo(() => sortRows(data ?? [], sort), [data, sort])
  const sortArrow = (key: Exclude<SortKey, null>) =>
    sort.key === key ? (sort.dir === "asc" ? " ▲" : " ▼") : ""
  const ariaSort = (key: Exclude<SortKey, null>) =>
    sort.key === key ? (sort.dir === "asc" ? "ascending" : "descending") : "none"

  const open = (id: string) => navigate(`/regulations/${id}`)
  const searchDisabled = !!error || !!dateError

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Regulations</h1>

      <Card>
        <CardContent className="space-y-3 p-4">
          <div className="flex flex-wrap items-center gap-3">
            <Input
              className="min-w-[200px] flex-1"
              placeholder="Search regulation name or description…"
              value={form.q}
              onChange={(e) => onQChange(e.target.value)}
              aria-label="Search keywords"
            />
            <FilterSelect value={form.jurisdiction} options={filterOptions.jurisdictions}
              allLabel="All jurisdictions" onChange={(v) => { setForm({ jurisdiction: v }); apply() }} />
            <FilterSelect value={form.type} options={filterOptions.types}
              allLabel="All types" onChange={(v) => { setForm({ type: v }); apply() }} />
            <FilterSelect value={form.legal_force} options={filterOptions.legal_forces}
              allLabel="All statuses" onChange={(v) => { setForm({ legal_force: v }); apply() }} />
            <FilterSelect value={form.topic} options={filterOptions.topics}
              allLabel="All topics" onChange={(v) => { setForm({ topic: v }); apply() }} />
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Input type="date" className="w-auto" value={form.date_from}
              onChange={(e) => setForm({ date_from: e.target.value })} aria-label="Start date" />
            <Input type="date" className="w-auto" value={form.date_to}
              onChange={(e) => setForm({ date_to: e.target.value })} aria-label="End date" />
            <Button onClick={apply} disabled={searchDisabled}>Search</Button>
            <Button variant="outline" onClick={reset}>Reset</Button>
            {dateError && <p className="text-xs text-destructive">{dateError}</p>}
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead><TableHead>Jurisdiction</TableHead><TableHead>Type</TableHead>
                <TableHead>Effective Date</TableHead><TableHead>Status</TableHead><TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell colSpan={6}><Skeleton className="h-6 w-full" /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : error ? (
        <ErrorState
          message="Cannot connect to the graph database. Please check the Neo4j service status"
          action={<Button onClick={refetch}>Retry</Button>}
        />
      ) : rows.length === 0 ? (
        <EmptyState
          message="No regulations match your search. Try different keywords or filters"
          action={<Button variant="outline" onClick={reset}>Clear filters</Button>}
        />
      ) : (
        <>
          <p className="text-sm text-muted-foreground">Total {rows.length} regulations</p>
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="cursor-pointer select-none" onClick={() => toggleSort("name")}
                    aria-sort={ariaSort("name")}>Name{sortArrow("name")}</TableHead>
                  <TableHead>Jurisdiction</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="cursor-pointer select-none" onClick={() => toggleSort("legislation_date")}
                    aria-sort={ariaSort("legislation_date")}>Effective Date{sortArrow("legislation_date")}</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow key={r.instrument_id}
                    className="cursor-pointer"
                    role="button" tabIndex={0}
                    aria-label={`View details for ${r.name}`}
                    onClick={() => open(r.instrument_id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(r.instrument_id) }
                    }}>
                    <TableCell className="max-w-[360px] truncate font-medium">{r.name}</TableCell>
                    <TableCell>{r.jurisdiction || "—"}</TableCell>
                    <TableCell>{r.type || "—"}</TableCell>
                    <TableCell>{r.legislation_date ?? "—"}</TableCell>
                    <TableCell>{r.legal_force ? <Badge variant="secondary">{statusLabel(r.legal_force)}</Badge> : "—"}</TableCell>
                    <TableCell>
                      <Button variant="outline" size="sm"
                        onClick={(e) => { e.stopPropagation(); open(r.instrument_id) }}>View details</Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )}
    </div>
  )
}
