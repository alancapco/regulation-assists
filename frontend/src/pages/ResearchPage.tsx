import { useMemo, useState } from "react"
import { api } from "@/api/client"
import { useApi } from "@/hooks/useApi"
import type { ResearchItem } from "@/types/contract"
import { ErrorState } from "@/components/ErrorState"
import { EmptyState } from "@/components/EmptyState"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

export default function ResearchPage() {
  const [activeTag, setActiveTag] = useState<string | null>(null)
  const { data, loading, error, refetch } = useApi<ResearchItem[]>(
    () => api.research(activeTag ?? undefined),
    [activeTag]
  )

  // Collect unique tags from the unfiltered data for the chip row
  const { data: allData } = useApi<ResearchItem[]>(() => api.research(), [])
  const allTags = useMemo(() => {
    const tags = new Set<string>()
    for (const item of allData ?? []) for (const t of item.tags) tags.add(t)
    return Array.from(tags).sort()
  }, [allData])

  const items = data ?? []

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Research & Analysis</h1>

      {/* Tag filter chips */}
      {allTags.length > 0 && (
        <div className="flex flex-wrap gap-2">
          <button onClick={() => setActiveTag(null)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              activeTag === null ? "bg-black text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}>
            All
          </button>
          {allTags.map((tag) => (
            <button key={tag} onClick={() => setActiveTag(tag === activeTag ? null : tag)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                activeTag === tag ? "bg-black text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}>
              {tag}
            </button>
          ))}
        </div>
      )}

      {loading ? (
        <div className="space-y-4">
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-36 rounded-xl" />)}
        </div>
      ) : error ? (
        <ErrorState message={error} action={<Button onClick={refetch}>Retry</Button>} />
      ) : items.length === 0 ? (
        <EmptyState
          message={activeTag ? `No research found for tag "${activeTag}"` : "No research items found"}
          action={<Button variant="outline" onClick={() => setActiveTag(null)}>Clear filter</Button>}
        />
      ) : (
        <>
          <p className="text-sm text-muted-foreground">{items.length} paper{items.length !== 1 ? "s" : ""}</p>
          <div className="space-y-4">
            {items.map((item) => <ResearchCard key={item.id} item={item} onTagClick={setActiveTag} />)}
          </div>
        </>
      )}
    </div>
  )
}

function ResearchCard({ item, onTagClick }: { item: ResearchItem; onTagClick: (tag: string) => void }) {
  return (
    <div className="rounded-xl border bg-white p-5 shadow-sm space-y-3">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1 min-w-0">
          <a href={item.url} target="_blank" rel="noopener noreferrer"
            className="text-base font-semibold hover:underline text-blue-700 leading-snug">
            {item.title}
          </a>
          <p className="text-sm text-muted-foreground">
            {item.authors.join(", ")} · {item.institution} · {item.date}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <div className="text-2xl font-semibold tabular-nums">{item.citations}</div>
          <div className="text-[10px] uppercase tracking-[0.12em] text-gray-500">citations</div>
        </div>
      </div>
      <p className="text-sm text-gray-700 line-clamp-2">{item.summary}</p>
      {item.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {item.tags.map((t) => (
            <button key={t} onClick={() => onTagClick(t)}
              className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-600 hover:bg-gray-200 transition-colors">
              {t}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
