import { useRef, useState } from "react"
import { MessageCircle, X, Send } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { api } from "@/api/client"
import type { Citation } from "@/types/contract"

type Role = "user" | "assistant"
interface Message {
  role: Role
  content: string
  citations?: Citation[]
  strategy?: string
}

export default function ChatCopilot() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [sending, setSending] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  const scrollToBottom = () => {
    requestAnimationFrame(() => {
      if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight
    })
  }

  const send = async () => {
    const text = input.trim()
    if (!text || sending) return

    const userMsg: Message = { role: "user", content: text }
    const history = messages.map((m) => ({ role: m.role, content: m.content }))
    
    setMessages((prev) => [...prev, userMsg])
    setInput("")
    setSending(true)
    scrollToBottom()

    try {
      const response = await api.chat({
        query: text,
        history,
      })

      const assistantMsg: Message = {
        role: "assistant",
        content: response.answer,
        citations: response.citations,
        strategy: response.strategy,
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch (e) {
      const errorMsg: Message = {
        role: "assistant",
        content: `Error: ${(e as Error).message}`,
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      setSending(false)
      scrollToBottom()
    }
  }

  return (
    <>
      {/* Floating button */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-full bg-black px-4 py-3 text-sm font-medium text-white shadow-lg hover:bg-gray-800 transition-colors"
          aria-label="Open chat assistant"
        >
          <MessageCircle className="size-4" />
          Chat
        </button>
      )}

      {/* Backdrop overlay */}
      {open && (
        <div
          className="fixed inset-0 bg-black/20 z-40 transition-opacity"
          onClick={() => setOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Right-side panel */}
      <div
        className={`fixed inset-y-0 right-0 z-50 w-[480px] bg-white shadow-2xl flex flex-col transition-transform duration-300 ease-in-out ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between bg-black px-5 py-4 border-b border-white/10">
          <div className="flex items-center gap-2 text-white">
            <MessageCircle className="size-5" />
            <span className="text-base font-semibold">Capco AI Assistant</span>
          </div>
          <button
            onClick={() => setOpen(false)}
            aria-label="Close chat"
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X className="size-5" />
          </button>
        </div>

        {/* Message list */}
        <div ref={listRef} className="flex-1 flex flex-col gap-3 overflow-y-auto p-5">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center px-6">
              <MessageCircle className="size-12 text-gray-300 mb-3" />
              <p className="text-sm font-medium text-gray-900 mb-1">
                Ask anything about AI regulations
              </p>
              <p className="text-xs text-gray-500">
                I'm context-aware and can help you understand the current page
              </p>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className="flex flex-col gap-2">
              <div className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm leading-relaxed ${
                    m.role === "user"
                      ? "bg-gray-200 text-gray-900"
                      : "border bg-white text-gray-900"
                  }`}
                >
                  {m.content}
                </div>
              </div>
              {/* Citations */}
              {m.role === "assistant" && m.citations && m.citations.length > 0 && (
                <div className="ml-2 space-y-1.5">
                  <div className="text-xs font-medium text-muted-foreground">Sources:</div>
                  {m.citations.map((cite, idx) => (
                    <button
                      key={idx}
                      onClick={() => {
                        navigate(`/regulations/${cite.instrument_id}`)
                        setOpen(false)
                      }}
                      className="block w-full text-left rounded border bg-gray-50 px-3 py-2 text-xs hover:bg-gray-100 transition-colors"
                    >
                      <div className="font-medium text-primary hover:underline">
                        {cite.name}
                      </div>
                      <div className="mt-0.5 text-muted-foreground line-clamp-2">
                        {cite.snippet}
                      </div>
                    </button>
                  ))}
                  {/* Strategy badge */}
                  {m.strategy && (
                    <div className="pt-1">
                      <span className="inline-block rounded-full bg-gray-100 px-2 py-0.5 text-xs text-muted-foreground">
                        {m.strategy}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
          {sending && (
            <div className="flex justify-start">
              <div className="border bg-white rounded-xl px-4 py-2.5 text-sm text-muted-foreground">
                Thinking…
              </div>
            </div>
          )}
        </div>

        {/* Input row */}
        <div className="flex items-center gap-2 border-t p-4 bg-gray-50">
          <input
            className="flex-1 rounded-lg border bg-white px-4 py-2.5 text-sm outline-none focus:border-black focus:ring-1 focus:ring-black"
            placeholder="Ask a question…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault()
                send()
              }
            }}
            disabled={sending}
            aria-label="Chat input"
          />
          <button
            onClick={send}
            disabled={sending || !input.trim()}
            className="flex size-10 items-center justify-center rounded-lg bg-black text-white transition-colors hover:bg-gray-800 disabled:opacity-40"
            aria-label="Send message"
          >
            <Send className="size-4" />
          </button>
        </div>
      </div>
    </>
  )
}
