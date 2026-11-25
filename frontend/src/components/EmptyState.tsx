import type { ReactNode } from "react"

export function EmptyState({ message, action }: { message: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed p-10 text-center">
      <p className="text-sm text-muted-foreground">{message}</p>
      {action}
    </div>
  )
}
