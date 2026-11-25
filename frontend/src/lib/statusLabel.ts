// Raw status values from /api/taxonomy/statuses are camelCase with no spaces.
// All display paths must go through this map — never render the raw value directly.
const STATUS_LABELS: Record<string, string> = {
  InForce:          "In Force",
  PartiallyInForce: "In Force (Amended)",
  Draft:            "Draft",
  Proposed:         "Proposed",
  UnderReview:      "Under Review",
  Stalled:          "Stalled",
  Withdrawn:        "Withdrawn",
  Adopted:          "Adopted",
  AwaitingEntry:    "Awaiting Entry",
  Repealed:         "Repealed",
  Superseded:       "Superseded",
  "":               "Unknown",
}

export function statusLabel(raw: string | null | undefined): string {
  if (raw == null) return "Unknown"
  return STATUS_LABELS[raw] ?? raw
}
