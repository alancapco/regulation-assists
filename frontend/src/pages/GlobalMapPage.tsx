import { useNavigate, useSearchParams } from "react-router-dom"
import { api } from "@/api/client"
import { useApi } from "@/hooks/useApi"
import type { FilterOptions, MapData } from "@/types/contract"
import D3GlobeMap from "@/components/D3GlobeMap"
import { EmptyState } from "@/components/EmptyState"
import { ErrorState } from "@/components/ErrorState"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"

const ALL = "__ALL__"

export default function GlobalMapPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const jurisdiction = searchParams.get("jurisdiction") ?? ""
  const topic = searchParams.get("topic") ?? ""

  const { data, loading, error, refetch } = useApi<MapData>(
    () => api.map(),
    []
  )
  const { data: filters } = useApi<FilterOptions>(() => api.filters(), [])

  const countries = data?.countries ?? []

  const setParam = (key: string, value: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (value) next.set(key, value)
      else next.delete(key)
      return next
    })
  }

  const resetAll = () => setSearchParams(new URLSearchParams())

  const onCountryClick = (jurisdictionName: string) => {
    // Navigate directly to regulations page filtered by jurisdiction
    navigate(`/regulations?jurisdiction=${encodeURIComponent(jurisdictionName)}`)
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Global Map</h1>

      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex min-w-[180px] flex-col gap-1">
            <label className="text-xs text-muted-foreground">Jurisdiction</label>
            <Select
              value={jurisdiction || ALL}
              onValueChange={(v) => setParam("jurisdiction", v === ALL ? "" : v)}
            >
              <SelectTrigger aria-label="Jurisdiction">
                <SelectValue placeholder="All" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All</SelectItem>
                {(filters?.jurisdictions ?? []).map((j) => (
                  <SelectItem key={j} value={j}>
                    {j}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex min-w-[180px] flex-col gap-1">
            <label className="text-xs text-muted-foreground">Topic</label>
            <Select value={topic || ALL} onValueChange={(v) => setParam("topic", v === ALL ? "" : v)}>
              <SelectTrigger aria-label="Topic">
                <SelectValue placeholder="All" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All</SelectItem>
                {(filters?.topics ?? []).map((t) => (
                  <SelectItem key={t} value={t}>
                    {t}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button variant="ghost" onClick={resetAll}>
            Reset View
          </Button>
        </div>
      </Card>

      {loading ? (
        <div className="flex h-[600px] flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
          <Skeleton className="h-40 w-40 rounded-full" />
          <span>Loading globe…</span>
        </div>
      ) : error ? (
        <ErrorState message={error} action={<Button onClick={refetch}>Retry</Button>} />
      ) : countries.length === 0 ? (
        <EmptyState
          message="No data available"
          action={<Button onClick={refetch}>Retry</Button>}
        />
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              {countries.length} jurisdictions · {data?.total_regulations ?? 0} regulations
            </p>
          </div>

          <Card className="overflow-hidden">
            <D3GlobeMap countries={countries} onCountryClick={onCountryClick} />
          </Card>
        </>
      )}
    </div>
  )
}
