import { useNavigate, useParams } from "react-router-dom"
import { ArrowLeft, ChevronRight, ExternalLink } from "lucide-react"
import { api } from "@/api/client"
import { useApi } from "@/hooks/useApi"
import type { BreakdownSummary, BreakdownDetail, ArticleBreakdown } from "@/types/contract"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/EmptyState"
import { ErrorState } from "@/components/ErrorState"

// ── List view ──────────────────────────────────────────────────────────────

function BreakdownsList() {
  const navigate = useNavigate()
  const { data, loading, error, refetch } = useApi<BreakdownSummary[]>(() => api.breakdowns(), [])

  if (loading) return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-32 rounded-xl" />)}
    </div>
  )
  if (error) return <ErrorState message={error} action={<Button onClick={refetch}>Retry</Button>} />
  if (!data?.length) return <EmptyState message="No breakdowns available yet" />

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-muted-foreground">
          Article-by-article structural analysis of key AI regulations — plain English explanations,
          key points, action items, and cross-jurisdiction comparisons.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data.map((b) => (
          <Card
            key={b.slug}
            className="cursor-pointer hover:shadow-md transition-shadow"
            onClick={() => navigate(`/breakdowns/${b.slug}`)}
          >
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground mb-1">
                    {b.country} · {b.region}
                  </div>
                  <CardTitle className="text-sm leading-snug">{b.title}</CardTitle>
                </div>
                <ChevronRight className="size-4 text-muted-foreground shrink-0 mt-0.5" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                <span className="text-2xl font-semibold tabular-nums">{b.article_count}</span>
                <span className="text-xs text-muted-foreground">articles</span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

// ── Article section ────────────────────────────────────────────────────────

function ArticleSection({ article }: { article: ArticleBreakdown }) {
  return (
    <div className="space-y-5">
      {article.chapter && (
        <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
          {article.chapter}
        </div>
      )}
      <div className="flex flex-wrap items-baseline gap-3">
        <h2 className="text-lg font-semibold">{article.article_number}</h2>
        <span className="text-base text-muted-foreground">{article.article_title}</span>
        {article.applies_from && (
          <Badge variant="outline" className="text-[10px]">
            From {article.applies_from}
          </Badge>
        )}
      </div>

      {article.applies_to.length > 0 && (
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground mb-1">
            Applies To
          </div>
          <ul className="space-y-0.5 text-sm text-muted-foreground">
            {article.applies_to.map((t, i) => (
              <li key={i} className="flex gap-2"><span className="text-muted-foreground/40">›</span>{t}</li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground mb-1">
          Plain English
        </div>
        <p className="text-sm leading-relaxed">{article.plain_english}</p>
      </div>

      {article.key_points.length > 0 && (
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground mb-1">
            Key Points
          </div>
          <ul className="space-y-1 text-sm">
            {article.key_points.map((pt, i) => (
              <li key={i} className="flex gap-2"><span className="text-muted-foreground">•</span>{pt}</li>
            ))}
          </ul>
        </div>
      )}

      {article.action_items.length > 0 && (
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground mb-1">
            What You Need To Do
          </div>
          <ol className="space-y-1 text-sm list-decimal list-inside">
            {article.action_items.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ol>
        </div>
      )}

      {article.cross_jurisdiction.length > 0 && (
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground mb-1">
            Cross-Jurisdiction Equivalents
          </div>
          <div className="space-y-1">
            {article.cross_jurisdiction.map((cj, i) => (
              <div key={i} className="text-sm flex gap-2">
                <span className="font-medium shrink-0">{cj.jurisdiction}:</span>
                <span className="text-muted-foreground">{cj.note}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Detail view ────────────────────────────────────────────────────────────

function BreakdownDetail() {
  const { slug } = useParams<{ slug: string }>()
  const navigate = useNavigate()
  const { data, loading, error, refetch } = useApi<BreakdownDetail>(
    () => api.breakdown(slug!),
    [slug]
  )

  if (loading) return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-64" />
      {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-48 rounded-xl" />)}
    </div>
  )
  if (error) return <ErrorState message={error} action={<Button onClick={refetch}>Retry</Button>} />
  if (!data) return null

  return (
    <div className="space-y-6">
      <nav className="flex items-center gap-2 text-sm text-muted-foreground">
        <button onClick={() => navigate("/breakdowns")}
          className="inline-flex items-center gap-1 hover:text-foreground">
          <ArrowLeft className="size-4" /> Breakdowns
        </button>
        <span>/</span>
        <span className="text-foreground">{data.title}</span>
      </nav>

      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{data.title}</h1>
        <Badge variant="outline">{data.country}</Badge>
        <Badge variant="secondary">{data.article_count} articles</Badge>
      </div>

      {/* Quick-jump index */}
      <Card>
        <CardHeader className="pb-2">
          <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            Article Index
          </div>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {data.articles.map((a, i) => (
            <a
              key={i}
              href={`#article-${i}`}
              className="text-xs font-medium border rounded px-2 py-0.5 hover:bg-muted transition-colors"
            >
              {a.article_number}
            </a>
          ))}
        </CardContent>
      </Card>

      {/* Articles */}
      {data.articles.map((article, i) => (
        <Card key={i} id={`article-${i}`}>
          <CardContent className="pt-6">
            <ArticleSection article={article} />
          </CardContent>
        </Card>
      ))}

      <div className="text-xs text-muted-foreground flex items-center gap-1">
        <ExternalLink className="size-3" />
        Plain-English breakdown — verify against official text before relying on compliance decisions.
      </div>
    </div>
  )
}

// ── Router: list vs detail based on :slug param ────────────────────────────

export default function BreakdownsPage() {
  const { slug } = useParams<{ slug?: string }>()
  return slug ? <BreakdownDetail /> : <BreakdownsList />
}
