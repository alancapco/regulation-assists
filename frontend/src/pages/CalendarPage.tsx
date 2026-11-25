import { useMemo, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { api } from "@/api/client"
import { useApi } from "@/hooks/useApi"
import type { CalendarEvent, FilterOptions } from "@/types/contract"
import { EmptyState } from "@/components/EmptyState"
import { ErrorState } from "@/components/ErrorState"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"

const ALL = "__ALL__" // Radix Select rejects an empty value, so a sentinel represents "All".

// Convert local date to ISO using local components (not toISOString) to avoid a one-day UTC shift.
function toISO(d: Date) {
  const m = String(d.getMonth() + 1).padStart(2, "0")
  const day = String(d.getDate()).padStart(2, "0")
  return `${d.getFullYear()}-${m}-${day}`
}

export default function CalendarPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [view, setView] = useState<"timeline" | "list">("timeline")

  const jurisdiction = searchParams.get("jurisdiction") ?? ""
  const dateFrom = searchParams.get("date_from") ?? ""
  const dateTo = searchParams.get("date_to") ?? ""

  // Query params go into deps → refetch only on URL change; view is outside deps so switching tabs won't refetch.
  const { data, loading, error, refetch } = useApi<CalendarEvent[]>(
    () => api.calendar({ jurisdiction, date_from: dateFrom, date_to: dateTo }),
    [jurisdiction, dateFrom, dateTo]
  )
  const { data: filters } = useApi<FilterOptions>(() => api.filters(), [])

  const events = data ?? []

  const groups = useMemo(() => {
    // Client-side fallback sort: guarantee timeline groups are strictly ascending by date, independent of server order.
    const sorted = [...events].sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0))
    const map = new Map<string, CalendarEvent[]>()
    for (const e of sorted) {
      const month = e.date.slice(0, 7)
      const arr = map.get(month)
      if (arr) arr.push(e)
      else map.set(month, [e])
    }
    return Array.from(map, ([month, items]) => ({ month, items }))
  }, [events])

  const setParam = (key: string, value: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (value) next.set(key, value)
      else next.delete(key)
      return next
    })
  }

  // "Next 12 Months": compute the ISO range from the click day and write it to the URL so it survives refresh.
  const applyNext12Months = () => {
    const from = new Date()
    const to = new Date()
    to.setFullYear(to.getFullYear() + 1)
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set("date_from", toISO(from))
      next.set("date_to", toISO(to))
      return next
    })
  }

  const resetDates = () =>
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete("date_from")
      next.delete("date_to")
      return next
    })

  const resetAll = () => setSearchParams(new URLSearchParams())

  const openRegulation = (instrumentId: string) => navigate(`/regulations/${instrumentId}`)

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Regulation Calendar</h1>

      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Start Date</label>
            <Input type="date" value={dateFrom} aria-label="Start Date"
              onChange={(e) => setParam("date_from", e.target.value)} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">End Date</label>
            <Input type="date" value={dateTo} aria-label="End Date"
              onChange={(e) => setParam("date_to", e.target.value)} />
          </div>
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
          <Button variant="outline" onClick={applyNext12Months}>Next 12 Months</Button>
          <Button variant="ghost" onClick={resetAll}>Reset</Button>
        </div>
      </Card>

      {loading ? (
        <div className="grid gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : error ? (
        <ErrorState message={error} action={<Button onClick={refetch}>Retry</Button>} />
      ) : events.length === 0 ? (
        <EmptyState message="No milestone events in this range"
          action={<Button onClick={resetDates}>Reset Dates</Button>} />
      ) : (
        <>
          <div className="flex items-center justify-between gap-4">
            <p className="text-sm text-muted-foreground">Total {events.length} events</p>
            <Tabs value={view} onValueChange={(v) => setView(v as "timeline" | "list")}>
              <TabsList>
                <TabsTrigger value="timeline">Timeline</TabsTrigger>
                <TabsTrigger value="list">List</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          {view === "timeline" ? (
            <div className="space-y-6">
              {groups.map(({ month, items }) => (
                <section key={month}>
                  <h2 className="mb-3 text-sm font-semibold text-muted-foreground">{month}</h2>
                  <div className="space-y-3">
                    {items.map((e) => (
                      <div key={e.id} className="relative border-l border-muted pl-6">
                        <span className="absolute -left-[5px] top-2 h-2.5 w-2.5 rounded-full bg-primary" />
                        <Card className="p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0 space-y-1">
                              <p className="font-medium">{e.title}</p>
                              <button onClick={() => openRegulation(e.instrument_id)}
                                className="block truncate text-sm text-primary hover:underline">
                                {e.regulation_name}
                              </button>
                              <p className="text-xs text-muted-foreground">
                                {e.date} · {e.jurisdiction || "—"}
                              </p>
                            </div>
                            {e.source_url && (
                              <Button asChild variant="outline" size="sm" className="shrink-0">
                                <a href={e.source_url} target="_blank" rel="noopener noreferrer"
                                  aria-label="Open source in a new tab">View source</a>
                              </Button>
                            )}
                          </div>
                        </Card>
                      </div>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[120px]">Date</TableHead>
                  <TableHead>Event</TableHead>
                  <TableHead>Regulation</TableHead>
                  <TableHead className="w-[140px]">Jurisdiction</TableHead>
                  <TableHead className="w-[100px]">Source</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {events.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell className="whitespace-nowrap">{e.date}</TableCell>
                    <TableCell>{e.title}</TableCell>
                    <TableCell>
                      <button onClick={() => openRegulation(e.instrument_id)}
                        className="text-left text-primary hover:underline">{e.regulation_name}</button>
                    </TableCell>
                    <TableCell>{e.jurisdiction || "—"}</TableCell>
                    <TableCell>
                      {e.source_url ? (
                        <a href={e.source_url} target="_blank" rel="noopener noreferrer"
                          className="text-primary hover:underline" aria-label="Open source in a new tab">View source</a>
                      ) : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </>
      )}
    </div>
  )
}
