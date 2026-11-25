import { useState } from "react"
import { toast } from "sonner"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Toaster } from "@/components/ui/sonner"
import { api } from "@/api/client"
import { useLlmConfig } from "@/hooks/useLlmConfig"
import type { LlmConfig } from "@/types/contract"

// Only accept http/https absolute URLs: new URL resolves the protocol, but ftp:// etc. need a regex guard.
function isValidHttpUrl(value: string): boolean {
  try {
    return /^https?:\/\//.test(new URL(value).href)
  } catch {
    return false
  }
}

export default function SettingsPage() {
  // useLlmConfig already reads and Base64-decodes from localStorage on mount, so values are prefilled here.
  const { config, save } = useLlmConfig()
  const [form, setForm] = useState<LlmConfig>(config)
  const [showKey, setShowKey] = useState(false)
  const [urlError, setUrlError] = useState<string | null>(null)
  const [testError, setTestError] = useState<string | null>(null)
  const [testing, setTesting] = useState(false)

  const setField = (k: keyof LlmConfig, v: string) =>
    setForm(f => ({ ...f, [k]: v }))

  const handleSave = () => {
    if (!isValidHttpUrl(form.base_url)) {
      setUrlError("Please enter a valid URL")
      return
    }
    setUrlError(null)
    // save re-encodes api_key as Base64 before writing to localStorage.
    save(form)
    toast.success("Configuration saved")
  }

  const handleTest = async () => {
    // The disabled button already blocks double-clicks; this guards against race-driven duplicate requests.
    if (testing) return
    setTesting(true)
    setTestError(null)
    try {
      const res = await api.llmTest(form)
      if (!res.ok) {
        setTestError(`LLM API call failed: ${res.error ?? "Unknown error"}`)
      } else {
        toast.success("Connection successful")
      }
    } catch (e) {
      setTestError(`LLM API call failed: ${(e as Error).message}`)
    } finally {
      setTesting(false)
    }
  }

  return (
    <>
      {/* No global Toaster is mounted and this card can only edit this file, so mount one locally to render toasts. */}
      <Toaster />
      <div className="mx-auto max-w-[640px]">
        <Card>
          <CardHeader>
            <CardTitle>LLM Configuration</CardTitle>
            <CardDescription>Configure the LLM endpoint used for regulation Q&A</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="base_url" className="text-sm font-medium">Base URL</label>
              <Input
                id="base_url"
                value={form.base_url}
                onChange={e => setField("base_url", e.target.value)}
                placeholder="https://api.openai.com/v1"
              />
              {urlError && <p className="text-sm text-destructive">{urlError}</p>}
            </div>

            <div className="space-y-1.5">
              <label htmlFor="api_key" className="text-sm font-medium">API Key</label>
              <div className="flex items-center gap-2">
                <Input
                  id="api_key"
                  type={showKey ? "text" : "password"}
                  value={form.api_key}
                  onChange={e => setField("api_key", e.target.value)}
                  placeholder="sk-..."
                  className="flex-1"
                />
                <div className="flex shrink-0 items-center gap-2 whitespace-nowrap">
                  <span className="text-xs text-muted-foreground">Show</span>
                  <Switch checked={showKey} onCheckedChange={setShowKey} aria-label="Show API Key" />
                </div>
              </div>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="model" className="text-sm font-medium">Model</label>
              <Input
                id="model"
                value={form.model}
                onChange={e => setField("model", e.target.value)}
                placeholder="gpt-4o"
              />
            </div>

            {testError && (
              <div className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {testError}
              </div>
            )}

            <div className="flex gap-2">
              <Button variant="outline" onClick={handleTest} disabled={testing}>
                {testing ? "Testing…" : "Test Connection"}
              </Button>
              <Button onClick={handleSave}>Save</Button>
            </div>

            <p className="text-xs text-muted-foreground">
              Do not use in production — the API key is only Base64-encoded, not encrypted.
            </p>
          </CardContent>
        </Card>
      </div>
    </>
  )
}
