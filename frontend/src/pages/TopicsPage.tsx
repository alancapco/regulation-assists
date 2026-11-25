import { useNavigate } from "react-router-dom"
import { api } from "@/api/client"
import { useApi } from "@/hooks/useApi"
import type { TopicItem } from "@/types/contract"
import { ErrorState } from "@/components/ErrorState"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

export default function TopicsPage() {
  const navigate = useNavigate()
  const { data, loading, error, refetch } = useApi<TopicItem[]>(() => api.topics(), [])

  const sorted = [...(data ?? [])].sort((a, b) => b.count - a.count)

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Regulatory Topics</h1>

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-32 rounded-xl" />)}
        </div>
      ) : error ? (
        <ErrorState message={error} action={<Button onClick={refetch}>Retry</Button>} />
      ) : sorted.length === 0 ? (
        <p className="text-sm text-muted-foreground">No topics found.</p>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">{sorted.length} topics</p>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {sorted.map((t) => (
              <button key={t.id}
                onClick={() => navigate(`/regulations?topic=${encodeURIComponent(t.id)}`)}
                className="rounded-xl border bg-white p-5 shadow-sm text-left hover:shadow-md transition-shadow flex flex-col gap-2">
                <div className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-500">{t.label}</div>
                <p className="text-sm text-muted-foreground line-clamp-2">{t.description}</p>
                <div className="mt-auto pt-2">
                  <span className="inline-block rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600 tabular-nums">
                    {t.count} regulations
                  </span>
                </div>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
