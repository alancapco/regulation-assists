import type {
  AppStatus, CalendarEvent, CalendarQuery, ErrorEnvelope, FilterOptions,
  GraphData, GraphQuery, LlmConfig, LlmTestResponse,
  MapData, GovernanceData, TopicItem, TypeItem, StatusItem, ResearchItem,
  UseCaseSummary, UseCaseDetail, TrackerParams, Regulation, RegulationQuery,
  BreakdownSummary, BreakdownDetail, ChatRequest, ChatResponse,
} from "@/types/contract"

const BASE = "/api"

export class ApiError extends Error {
  constructor(public code: string, message: string) {
    super(message)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" }, ...init,
  })
  if (!res.ok) {
    const env = await res.json().catch(() => null) as ErrorEnvelope | null
    throw new ApiError(env?.error?.code ?? "INTERNAL_ERROR",
                       env?.error?.message ?? "Server error, please try again later")
  }
  return res.json() as Promise<T>
}

// Empty strings are not sent → backend Depends defaults to "" → C3/C4/C5 "empty means no filter" semantics hold
const qs = (p: Record<string, string>) => {
  const u = new URLSearchParams()
  Object.entries(p).forEach(([k, v]) => { if (v) u.set(k, v) })
  const s = u.toString()
  return s ? "?" + s : ""
}

export const api = {
  status:      ()                      => request<AppStatus>("/status"),
  filters:     ()                      => request<FilterOptions>("/filters"),
  regulations: (p: RegulationQuery)   => request<Regulation[]>("/regulations" + qs(p)),
  regulation:  (id: string)           => request<Regulation>(`/regulations/${encodeURIComponent(id)}`),
  calendar:    (p: CalendarQuery)     => request<CalendarEvent[]>("/calendar" + qs(p)),
  graph:       (p: GraphQuery)        => request<GraphData>("/graph" + qs(p)),
  llmTest:     (c: LlmConfig)         => request<LlmTestResponse>("/llm/test",
                                          { method: "POST", body: JSON.stringify(c) }),
  chat:        (r: ChatRequest)       => request<ChatResponse>("/chat",
                                          { method: "POST", body: JSON.stringify(r) }),
  map:         ()                      => request<MapData>("/map"),
  governance:  ()                      => request<GovernanceData>("/governance"),
  topics:      ()                      => request<TopicItem[]>("/taxonomy/topics"),
  types:       ()                      => request<TypeItem[]>("/taxonomy/types"),
  statuses:    ()                      => request<StatusItem[]>("/taxonomy/statuses"),
  research:    (tag?: string)          => request<ResearchItem[]>(tag ? `/research?tag=${encodeURIComponent(tag)}` : "/research"),
  useCases:    ()                      => request<UseCaseSummary[]>("/use-cases"),
  useCase:     (slug: string)          => request<UseCaseDetail>(`/use-cases/${slug}`),
  tracker:     (p: TrackerParams)      => request<Regulation[]>("/regulations" + qs(p as Record<string, string>)),
  breakdowns:  ()                      => request<BreakdownSummary[]>("/breakdowns"),
  breakdown:   (slug: string)          => request<BreakdownDetail>(`/breakdowns/${encodeURIComponent(slug)}`),
}
