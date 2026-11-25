import { useNavigate, useParams } from "react-router-dom"
import { api } from "@/api/client"
import { useApi } from "@/hooks/useApi"
import type { UseCaseSummary, UseCaseDetail } from "@/types/contract"
import { ErrorState } from "@/components/ErrorState"
import { EmptyState } from "@/components/EmptyState"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { ArrowLeft, ExternalLink } from "lucide-react"

export default function UseCasesPage() {
  const { slug } = useParams<{ slug?: string }>()
  return slug ? <UseCaseDetail slug={slug} /> : <UseCaseList />
}

function UseCaseList() {
  const navigate = useNavigate()
  const { data, loading, error, refetch } = useApi<UseCaseSummary[]>(() => api.useCases(), [])
  const items = data ?? []

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Industry Use Cases</h1>

      {loading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-44 rounded-xl" />)}
        </div>
      ) : error ? (
        <ErrorState message={error} action={<Button onClick={refetch}>Retry</Button>} />
      ) : items.length === 0 ? (
        <EmptyState message="No use cases found" />
      ) : (
        <>
          <p className="text-sm text-muted-foreground">{items.length} use case{items.length !== 1 ? "s" : ""}</p>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {items.map((uc) => (
              <button key={uc.slug}
                onClick={() => navigate(`/use-cases/${uc.slug}`)}
                className="rounded-xl border bg-white p-5 shadow-sm text-left hover:shadow-md transition-shadow flex flex-col gap-3">
                <h2 className="font-semibold leading-snug">{uc.title}</h2>
                <p className="text-sm text-muted-foreground line-clamp-3">{uc.introduction}</p>
                {uc.target_audience.length > 0 && (
                  <div className="mt-auto flex flex-wrap gap-1.5 pt-2">
                    {uc.target_audience.map((a) => (
                      <span key={a} className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-600">{a}</span>
                    ))}
                  </div>
                )}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function UseCaseDetail({ slug }: { slug: string }) {
  const navigate = useNavigate()
  const { data, loading, error, refetch } = useApi<UseCaseDetail>(
    () => api.useCase(slug),
    [slug]
  )

  const goBack = () => navigate("/use-cases")

  if (loading) return <DetailSkeleton />
  if (error) return <ErrorState message={error} action={<Button onClick={refetch}>Retry</Button>} />
  if (!data) return null

  const uc = data
  return (
    <div className="space-y-6 max-w-[900px]">
      <nav className="flex items-center gap-2 text-sm text-muted-foreground">
        <button onClick={goBack} className="inline-flex items-center gap-1 hover:text-foreground">
          <ArrowLeft className="size-4" /> Use Cases
        </button>
        <span>/</span>
        <span className="text-foreground">{uc.title}</span>
      </nav>

      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">{uc.title}</h1>
        {uc.target_audience.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {uc.target_audience.map((a) => (
              <span key={a} className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600">{a}</span>
            ))}
          </div>
        )}
      </div>

      <p className="text-sm text-gray-700 leading-relaxed">{uc.introduction}</p>

      {uc.stakes.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-base font-semibold">What's at Stake</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {uc.stakes.map((s) => (
              <div key={s.title} className="rounded-xl border bg-white p-4 shadow-sm">
                <div className="font-medium text-sm">{s.title}</div>
                <p className="mt-1 text-sm text-muted-foreground">{s.description}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        {uc.dos.length > 0 && (
          <section className="space-y-3">
            <h2 className="text-base font-semibold text-green-700">Do's</h2>
            <ul className="space-y-2">
              {uc.dos.map((d, i) => (
                <li key={i} className="flex gap-2 text-sm text-green-800 bg-green-50 rounded-lg px-3 py-2">
                  <span className="shrink-0 font-semibold">✓</span>
                  {d}
                </li>
              ))}
            </ul>
          </section>
        )}

        {uc.donts.length > 0 && (
          <section className="space-y-3">
            <h2 className="text-base font-semibold text-red-700">Don'ts</h2>
            <ul className="space-y-2">
              {uc.donts.map((d, i) => (
                <li key={i} className="flex gap-2 text-sm text-red-800 bg-red-50 rounded-lg px-3 py-2">
                  <span className="shrink-0 font-semibold">✗</span>
                  {d}
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>

      {uc.regulations.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-base font-semibold">Applicable Regulations</h2>
          <div className="space-y-2">
            {uc.regulations.map((r) => (
              <button key={r.instrument_id}
                onClick={() => navigate(`/regulations/${encodeURIComponent(r.instrument_id)}`)}
                className="w-full rounded-xl border bg-white p-4 shadow-sm text-left hover:shadow-md transition-shadow flex items-center justify-between gap-3">
                <div className="min-w-0 space-y-1">
                  <div className="font-medium text-sm truncate">{r.name}</div>
                  <div className="text-xs text-muted-foreground">{r.jurisdiction} · {r.type}</div>
                </div>
                <ExternalLink className="size-4 shrink-0 text-muted-foreground" />
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

function DetailSkeleton() {
  return (
    <div className="space-y-6 max-w-[900px]">
      <Skeleton className="h-4 w-48" />
      <Skeleton className="h-8 w-2/3" />
      <Skeleton className="h-20 w-full" />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-20 rounded-xl" />)}
      </div>
    </div>
  )
}
