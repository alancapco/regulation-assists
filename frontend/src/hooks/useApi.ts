import { useCallback, useEffect, useState } from "react"

export function useApi<T>(fetcher: () => Promise<T>, deps: unknown[]) {
  const [state, setState] = useState<{ data?: T; loading: boolean; error?: string }>(
    { loading: true })
  const reload = useCallback(() => {
    let alive = true
    setState({ loading: true })
    fetcher()
      .then(d => alive && setState({ data: d, loading: false }))
      .catch((e: Error) => alive && setState({ loading: false, error: e.message }))
    // Why: when switching filters quickly, an old response may arrive late; the alive flag stops it overriding newer results
    return () => { alive = false }
  }, deps)
  useEffect(() => reload(), [reload])
  return { ...state, refetch: reload }
}
