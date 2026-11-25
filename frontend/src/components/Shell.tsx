import { NavLink, Outlet, useLocation } from "react-router-dom"
import { Scale, ListChecks, Calendar, Network, Globe, Shield, Tags, FileText, Activity, BookOpen, Briefcase, Settings, FileSearch } from "lucide-react"
import { StatusBar } from "@/components/StatusBar"
import ChatCopilot from "@/components/ChatCopilot"
import { cn } from "@/lib/utils"

const NAV_GROUPS = [
  {
    label: "Explore",
    items: [
      { to: "/regulations", label: "Regulations", icon: Scale },
      { to: "/regulations/tracker", label: "Tracker", icon: ListChecks },
      { to: "/calendar", label: "Calendar", icon: Calendar },
      { to: "/graph", label: "Knowledge Graph", icon: Network },
      { to: "/map", label: "Global Map", icon: Globe },
    ]
  },
  {
    label: "Analyze",
    items: [
      { to: "/governance", label: "Governance", icon: Shield },
      { to: "/topics", label: "Topics", icon: Tags },
      { to: "/types", label: "Types", icon: FileText },
      { to: "/statuses", label: "Lifecycle", icon: Activity },
      { to: "/research", label: "Research", icon: BookOpen },
      { to: "/breakdowns", label: "Breakdowns", icon: FileSearch },
    ]
  },
  {
    label: "Use Cases",
    items: [
      { to: "/use-cases", label: "Industries", icon: Briefcase },
    ]
  },
  {
    label: "System",
    items: [
      { to: "/settings", label: "Settings", icon: Settings },
    ]
  },
]

const TITLE_BY_PATH: Record<string, string> = {
  "/regulations": "Regulations",
  "/regulations/tracker": "Regulation Tracker",
  "/calendar": "Calendar",
  "/graph": "Knowledge Graph",
  "/map": "Global Regulatory Map",
  "/governance": "AI Governance Framework",
  "/topics": "Regulatory Topics",
  "/types": "Regulation Types",
  "/statuses": "Regulation Lifecycle",
  "/research": "Research & Analysis",
  "/breakdowns": "Article Breakdowns",
  "/use-cases": "Industry Use Cases",
  "/settings": "Settings",
}

export function Shell() {
  const { pathname } = useLocation()
  const title = TITLE_BY_PATH[pathname] ?? "Capco Regulation Assistant"

  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-30 w-60 bg-black text-white flex flex-col overflow-y-auto">
        <div className="px-5 py-4 border-b border-white/10">
          <div className="text-base font-bold tracking-tight">Capco</div>
          <div className="text-[11px] uppercase tracking-[0.14em] text-gray-400">Regulation Assistant</div>
        </div>
        <nav className="flex flex-col pb-4">
          {NAV_GROUPS.map((group) => (
            <div key={group.label}>
              <div className="px-5 pt-4 pb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-gray-500">{group.label}</div>
              {group.items.map((l) => {
                const Icon = l.icon
                return (
                  <NavLink key={l.to} to={l.to}
                    className={({ isActive }) => cn(
                      "px-5 py-2.5 text-sm flex items-center gap-3 border-l-2",
                      isActive
                        ? "bg-gray-800 border-white font-semibold text-white"
                        : "border-transparent text-gray-300 hover:bg-gray-800 hover:text-white")}>
                    <Icon className="size-4" />
                    {l.label}
                  </NavLink>
                )
              })}
            </div>
          ))}
        </nav>
      </aside>

      <div className="pl-60 flex min-h-screen flex-col">
        <header className="sticky top-0 z-20 h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6">
          <h1 className="text-base font-semibold tracking-tight">{title}</h1>
          <StatusBar />
        </header>
        <main className="flex-1 bg-gray-50">
          <div className="mx-auto w-full max-w-[1440px] px-6 lg:px-8 py-7">
            <Outlet />
          </div>
        </main>
      </div>

      <ChatCopilot />
    </div>
  )
}
