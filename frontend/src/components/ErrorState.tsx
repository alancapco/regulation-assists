import type { ReactNode } from "react"

export function ErrorState({ message, action }: { message: string; action?: ReactNode }) {
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-lg border border-destructive/50 bg-destructive/10 p-6">
      <p className="text-sm text-destructive">{message}</p>
      {action}
    </div>
  )
}
