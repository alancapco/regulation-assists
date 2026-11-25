import { useCallback, useState } from "react"
import type { LlmConfig } from "@/types/contract"

const KEY = "regulation-corpus:llm-config"

// api_key is only Base64-encoded (not encrypted); the UI must surface this risk
function decode(raw: string | null): LlmConfig {
  const empty: LlmConfig = { base_url: "", api_key: "", model: "" }
  if (!raw) return empty
  try {
    const c = JSON.parse(raw) as LlmConfig
    return { base_url: c.base_url ?? "", api_key: c.api_key ? atob(c.api_key) : "",
             model: c.model ?? "" }
  } catch {
    return empty
  }
}

export function useLlmConfig() {
  const [config, setConfig] = useState<LlmConfig>(() => decode(
    typeof localStorage !== "undefined" ? localStorage.getItem(KEY) : null))

  const save = useCallback((c: LlmConfig) => {
    const stored: LlmConfig = { ...c, api_key: c.api_key ? btoa(c.api_key) : "" }
    localStorage.setItem(KEY, JSON.stringify(stored))
    setConfig(c)
  }, [])

  return { config, save }
}
