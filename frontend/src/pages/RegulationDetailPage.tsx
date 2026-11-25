// U-FE-02: P-002 regulation detail page — replace this stub only, never touch shared files.
import { useState, type KeyboardEvent } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { ArrowLeft, ExternalLink } from "lucide-react"

import { api, ApiError } from "@/api/client"
import { useApi } from "@/hooks/useApi"
import type { Regulation } from "@/types/contract"
import { statusLabel } from "@/lib/statusLabel"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { EmptyState } from "@/components/EmptyState"
import { ErrorState } from "@/components/ErrorState"

// rel_type is a server-computed enum; we only map it to a display label, never parse the URL.
const REL_LABEL: Record<string, string> = {
  SOURCED_FROM: "Sourced from",
  HAS_OFFICIAL_TEXT: "Official text",
  PUBLISHED_AT: "Published",
}

const DASH = "—"

export default function RegulationDetailPage() {
  const { instrument_id = "" } = useParams()
  const navigate = useNavigate()
  const [tab, setTab] = useState("overview")

  const { data, loading, error, refetch } = useApi<Regulation>(async () => {
    try {
      return await api.regulation(instrument_id)
    } catch (e) {
      // 404 uses a dedicated "not found" state, not the generic error state.
      if (e instanceof ApiError && e.code === "NOT_FOUND") throw new Error("NOT_FOUND")
      throw e
    }
  }, [instrument_id])

  // Direct visit (no history) falls back to the list, avoiding navigate(-1) leaving the app.
  const goBack = () => (window.history.length > 1 ? navigate(-1) : navigate("/regulations"))
  const goList = () => navigate("/regulations")

  if (loading) return <DetailSkeleton />
  if (error === "NOT_FOUND") {
    return <EmptyState message="Regulation not found" action={<Button onClick={goList}>Back to list</Button>} />
  }
  if (error) {
    return <ErrorState message={error} action={<Button onClick={refetch}>Retry</Button>} />
  }
  if (!data) return null

  const r = data
  // Null dates sort last, then ascending by date; contract has no raw date text field, so none shown.
  const milestones = [...r.milestones].sort((a, b) => {
    if (a.date == null && b.date == null) return 0
    if (a.date == null) return 1
    if (b.date == null) return -1
    return a.date < b.date ? -1 : a.date > b.date ? 1 : 0
  })

  return (
    <div className="space-y-6">
      {/* Breadcrumb: "Regulations" returns to the source list. */}
      <nav className="flex items-center gap-2 text-sm text-muted-foreground">
        <button onClick={goBack}
          className="inline-flex items-center gap-1 hover:text-foreground">
          <ArrowLeft className="size-4" /> Regulations
        </button>
        <span>/</span>
        <span className="text-foreground">{r.name}</span>
      </nav>

      {/* H1 + status Badge */}
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{r.name}</h1>
        {r.legal_force ? (
          <Badge variant="secondary">{statusLabel(r.legal_force)}</Badge>
        ) : (
          <Badge variant="outline">{DASH}</Badge>
        )}
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-4">
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
            <div className="space-y-6 xl:col-span-2">
              {/* Résumé section */}
              {r.resume && (
                <Card>
                  <CardHeader><CardTitle>Executive Summary</CardTitle></CardHeader>
                  <CardContent className="text-sm">
                    <p className="whitespace-pre-line leading-relaxed">{r.resume}</p>
                  </CardContent>
                </Card>
              )}

              {/* Plain English - regulations.ai detailed explanation */}
              {r.plain_english && (
                <Card>
                  <CardHeader><CardTitle>Plain English</CardTitle></CardHeader>
                  <CardContent className="text-sm">
                    <p className="whitespace-pre-line leading-relaxed">{r.plain_english}</p>
                  </CardContent>
                </Card>
              )}

              {/* Overview */}
              {r.overview && (
                <Card>
                  <CardHeader><CardTitle>Overview</CardTitle></CardHeader>
                  <CardContent className="text-sm">
                    <p className="whitespace-pre-line leading-relaxed">{r.overview}</p>
                  </CardContent>
                </Card>
              )}

              {/* Definitions */}
              {r.definitions && (
                <Card>
                  <CardHeader><CardTitle>Definitions</CardTitle></CardHeader>
                  <CardContent className="text-sm">
                    <p className="whitespace-pre-line leading-relaxed">{r.definitions}</p>
                  </CardContent>
                </Card>
              )}

              {/* Governance Framework */}
              {r.governance_framework && (
                <Card>
                  <CardHeader><CardTitle>Governance and Institutional Framework</CardTitle></CardHeader>
                  <CardContent className="text-sm">
                    <p className="whitespace-pre-line leading-relaxed">{r.governance_framework}</p>
                  </CardContent>
                </Card>
              )}

              {/* Key Focus Areas */}
              {r.key_focus_areas && (
                <Card>
                  <CardHeader><CardTitle>Key Focus Areas</CardTitle></CardHeader>
                  <CardContent className="text-sm">
                    <p className="whitespace-pre-line leading-relaxed">{r.key_focus_areas}</p>
                  </CardContent>
                </Card>
              )}

              {/* Implementation Framework */}
              {r.implementation_framework && (
                <Card>
                  <CardHeader><CardTitle>Implementation Framework</CardTitle></CardHeader>
                  <CardContent className="text-sm">
                    <p className="whitespace-pre-line leading-relaxed">{r.implementation_framework}</p>
                  </CardContent>
                </Card>
              )}

              {/* NEW RICH CONTENT SECTIONS */}

              {/* Summary */}
              {r.summary && (
                <Card>
                  <CardHeader><CardTitle>Summary</CardTitle></CardHeader>
                  <CardContent className="text-sm">
                    <p className="whitespace-pre-line leading-relaxed">{r.summary}</p>
                  </CardContent>
                </Card>
              )}

              {/* Monitoring & Evaluation */}
              {r.monitoring_evaluation && (
                <Card>
                  <CardHeader><CardTitle>Monitoring & Evaluation</CardTitle></CardHeader>
                  <CardContent className="text-sm">
                    <p className="whitespace-pre-line leading-relaxed">{r.monitoring_evaluation}</p>
                  </CardContent>
                </Card>
              )}

              {/* Penalties & Liability */}
              {r.penalties_liability && (
                <Card>
                  <CardHeader><CardTitle>Penalties, Liability & Appeals</CardTitle></CardHeader>
                  <CardContent className="text-sm">
                    <p className="whitespace-pre-line leading-relaxed">{r.penalties_liability}</p>
                  </CardContent>
                </Card>
              )}

              {/* Relationship to Other Instruments */}
              {r.relationship_to_other && (
                <Card>
                  <CardHeader><CardTitle>Relationship to Other Instruments</CardTitle></CardHeader>
                  <CardContent className="text-sm">
                    <p className="whitespace-pre-line leading-relaxed">{r.relationship_to_other}</p>
                  </CardContent>
                </Card>
              )}

              {/* International Alignment */}
              {r.international_alignment && (
                <Card>
                  <CardHeader><CardTitle>International Alignment</CardTitle></CardHeader>
                  <CardContent className="text-sm">
                    <p className="whitespace-pre-line leading-relaxed">{r.international_alignment}</p>
                  </CardContent>
                </Card>
              )}

              {/* Implementation Timeline */}
              {r.implementation_timeline && (
                <Card>
                  <CardHeader><CardTitle>Implementation Timeline</CardTitle></CardHeader>
                  <CardContent className="text-sm">
                    <p className="whitespace-pre-line leading-relaxed">{r.implementation_timeline}</p>
                  </CardContent>
                </Card>
              )}

              {/* Requirements Tables */}
              {(r.requirements_must_do && r.requirements_must_do.length > 0) && (
                <Card>
                  <CardHeader><CardTitle>Requirements for a Company</CardTitle></CardHeader>
                  <CardContent className="space-y-6">
                    {/* Must Do */}
                    {r.requirements_must_do && r.requirements_must_do.length > 0 && (
                      <div>
                        <h4 className="mb-3 font-semibold text-sm">Must Do ({r.requirements_must_do.length})</h4>
                        <div className="space-y-3">
                          {r.requirements_must_do.map((req, idx) => (
                            <div key={idx} className="border-l-4 border-red-500 pl-4 py-2">
                              <p className="text-sm font-medium">{req.requirement}</p>
                              {req.applies_to && <p className="text-xs text-muted-foreground mt-1">Applies to: {req.applies_to}</p>}
                              {req.deadline && <p className="text-xs text-muted-foreground mt-1">Deadline: {req.deadline}</p>}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Should Do */}
                    {r.requirements_should_do && r.requirements_should_do.length > 0 && (
                      <div>
                        <h4 className="mb-3 font-semibold text-sm">Should Do ({r.requirements_should_do.length})</h4>
                        <div className="space-y-3">
                          {r.requirements_should_do.map((req, idx) => (
                            <div key={idx} className="border-l-4 border-yellow-500 pl-4 py-2">
                              <p className="text-sm font-medium">{req.requirement}</p>
                              {req.applies_to && <p className="text-xs text-muted-foreground mt-1">Applies to: {req.applies_to}</p>}
                              {req.deadline && <p className="text-xs text-muted-foreground mt-1">Deadline: {req.deadline}</p>}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Must Not Do */}
                    {r.requirements_must_not_do && r.requirements_must_not_do.length > 0 && (
                      <div>
                        <h4 className="mb-3 font-semibold text-sm">Must Not Do ({r.requirements_must_not_do.length})</h4>
                        <div className="space-y-3">
                          {r.requirements_must_not_do.map((req, idx) => (
                            <div key={idx} className="border-l-4 border-red-700 pl-4 py-2">
                              <p className="text-sm font-medium">{req.requirement}</p>
                              {req.applies_to && <p className="text-xs text-muted-foreground mt-1">Applies to: {req.applies_to}</p>}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Should Not Do */}
                    {r.requirements_should_not_do && r.requirements_should_not_do.length > 0 && (
                      <div>
                        <h4 className="mb-3 font-semibold text-sm">Should Not Do ({r.requirements_should_not_do.length})</h4>
                        <div className="space-y-3">
                          {r.requirements_should_not_do.map((req, idx) => (
                            <div key={idx} className="border-l-4 border-orange-500 pl-4 py-2">
                              <p className="text-sm font-medium">{req.requirement}</p>
                              {req.applies_to && <p className="text-xs text-muted-foreground mt-1">Applies to: {req.applies_to}</p>}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* Obligations Table */}
              {r.obligations && r.obligations.length > 0 && (
                <Card>
                  <CardHeader><CardTitle>Who Must Do What</CardTitle></CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {r.obligations.map((obl, idx) => (
                        <div key={idx} className="border-l-4 border-blue-500 pl-4 py-2">
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <p className="text-sm font-semibold">{obl.who}</p>
                              <p className="text-sm mt-1">{obl.requirement}</p>
                              {obl.deadline && <p className="text-xs text-muted-foreground mt-1">Deadline: {obl.deadline}</p>}
                              {obl.source && <p className="text-xs text-muted-foreground mt-1">Source: {obl.source}</p>}
                            </div>
                            {obl.severity && (
                              <Badge variant={obl.severity === 'Critical' ? 'destructive' : 'secondary'} className="ml-2">
                                {obl.severity}
                              </Badge>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Basic information */}
              <Card>
                <CardHeader><CardTitle>Basic Information</CardTitle></CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <Field label="Jurisdiction" value={r.jurisdiction} />
                  <Field label="Type" value={r.type} />
                  <Field label="Effective Date" value={r.legislation_date} />
                  <div>
                    <div className="text-muted-foreground">Description</div>
                    <p className="mt-1 whitespace-pre-line">{r.description || "No description available"}</p>
                  </div>
                </CardContent>
              </Card>

              {/* Official sources: show all links */}
              <Card>
                <CardHeader><CardTitle>Official Sources</CardTitle></CardHeader>
                <CardContent className="space-y-3 text-sm">
                  {r.official_sources.length === 0 ? (
                    <p className="text-muted-foreground">Official sources: not provided</p>
                  ) : (
                    <ul className="space-y-2">
                      {r.official_sources.map((s) => (
                        <li key={s.url}>
                          <a href={s.url} target="_blank" rel="noopener noreferrer"
                            aria-label={`Open ${s.domain} in a new tab`}
                            className="inline-flex items-center gap-1.5 text-primary hover:underline">
                            <ExternalLink className="size-4" />{s.domain}
                            <span className="text-xs text-muted-foreground">
                              {REL_LABEL[s.rel_type] ?? s.rel_type}
                            </span>
                          </a>
                        </li>
                      ))}
                    </ul>
                  )}
                  <a href={r.record_url} target="_blank" rel="noopener noreferrer"
                    aria-label="Open the regulations.ai record in a new tab"
                    className="inline-flex items-center gap-1.5 text-primary hover:underline">
                    <ExternalLink className="size-4" />View record on regulations.ai
                  </a>
                </CardContent>
              </Card>

              {/* Topic tags: clickable → pre-filter the list page by topic. */}
              <Card>
                <CardHeader><CardTitle>Topic Tags</CardTitle></CardHeader>
                <CardContent>
                  {r.topics.length === 0 ? (
                    <span className="text-sm text-muted-foreground">{DASH}</span>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {r.topics.map((t) => (
                        <Badge key={t} variant="outline" role="button" tabIndex={0}
                          className="cursor-pointer hover:bg-accent"
                          onClick={() => navigate(`/regulations?topic=${encodeURIComponent(t)}`)}
                          onKeyDown={(e: KeyboardEvent<HTMLDivElement>) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault()
                              navigate(`/regulations?topic=${encodeURIComponent(t)}`)
                            }
                          }}>
                          {t}
                        </Badge>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Right-side metadata card (standalone column on desktop ≥1280). */}
            <div className="xl:col-span-1">
              <Card>
                <CardHeader><CardTitle>Metadata</CardTitle></CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <div>
                    <div className="text-muted-foreground">Regulation ID</div>
                    <p className="mt-1 break-all font-mono text-xs">{r.instrument_id}</p>
                  </div>
                  <Field label="Status" value={statusLabel(r.legal_force)} />
                  <Field label="Official Sources" value={String(r.official_sources.length)} />
                  <Field label="Timeline Entries" value={String(r.milestones.length)} />
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* Timeline: show milestone notes using Accordion for expandable details */}
        <TabsContent value="timeline" className="mt-4">
          <Card>
            <CardHeader><CardTitle>Implementation Timeline</CardTitle></CardHeader>
            <CardContent>
              {milestones.length === 0 ? (
                <p className="text-sm text-muted-foreground">No timeline entries</p>
              ) : (
                <Accordion type="single" collapsible className="space-y-4">
                  {milestones.map((m, i) => (
                    <AccordionItem key={i} value={`milestone-${i}`} className="border rounded-lg px-4">
                      <AccordionTrigger className="hover:no-underline">
                        <div className="flex items-start gap-3 text-left">
                          <span className="mt-1.5 size-2.5 shrink-0 rounded-full bg-primary" />
                          <div>
                            <div className="text-sm font-medium">{m.title}</div>
                            <div className="text-xs text-muted-foreground">{m.date ?? DASH}</div>
                          </div>
                        </div>
                      </AccordionTrigger>
                      {m.notes && (
                        <AccordionContent className="pl-7 pb-4 text-sm text-muted-foreground whitespace-pre-line">
                          {m.notes}
                        </AccordionContent>
                      )}
                    </AccordionItem>
                  ))}
                </Accordion>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

function Field({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <div className="text-muted-foreground">{label}</div>
      <div className="mt-1">{value ? value : DASH}</div>
    </div>
  )
}

function DetailSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-4 w-48" />
      <Skeleton className="h-8 w-2/3" />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          {[0, 1, 2].map((i) => (
            <Card key={i}>
              <CardHeader><Skeleton className="h-5 w-24" /></CardHeader>
              <CardContent className="space-y-3">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-5/6" />
                <Skeleton className="h-4 w-2/3" />
              </CardContent>
            </Card>
          ))}
        </div>
        <Card>
          <CardHeader><Skeleton className="h-5 w-20" /></CardHeader>
          <CardContent className="space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
