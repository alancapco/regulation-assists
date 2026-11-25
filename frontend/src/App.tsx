import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { Shell } from "@/components/Shell"
import RegulationsPage from "@/pages/RegulationsPage"
import RegulationDetailPage from "@/pages/RegulationDetailPage"
import CalendarPage from "@/pages/CalendarPage"
import GraphPage from "@/pages/GraphPage"
import SettingsPage from "@/pages/SettingsPage"
import GlobalMapPage from "@/pages/GlobalMapPage"
import GovernancePage from "@/pages/GovernancePage"
import TopicsPage from "@/pages/TopicsPage"
import TypesPage from "@/pages/TypesPage"
import StatusesPage from "@/pages/StatusesPage"
import ResearchPage from "@/pages/ResearchPage"
import UseCasesPage from "@/pages/UseCasesPage"
import TrackerPage from "@/pages/TrackerPage"
import BreakdownsPage from "@/pages/BreakdownsPage"

export default function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route element={<Shell />}>
          <Route path="/regulations" element={<RegulationsPage />} />
          {/* /regulations/tracker must precede /:instrument_id to avoid "tracker" matching as an ID */}
          <Route path="/regulations/tracker" element={<TrackerPage />} />
          <Route path="/regulations/:instrument_id" element={<RegulationDetailPage />} />
          <Route path="/calendar" element={<CalendarPage />} />
          <Route path="/graph" element={<GraphPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/map" element={<GlobalMapPage />} />
          <Route path="/governance" element={<GovernancePage />} />
          <Route path="/topics" element={<TopicsPage />} />
          <Route path="/types" element={<TypesPage />} />
          <Route path="/statuses" element={<StatusesPage />} />
          <Route path="/research" element={<ResearchPage />} />
          <Route path="/use-cases" element={<UseCasesPage />} />
          <Route path="/use-cases/:slug" element={<UseCasesPage />} />
          <Route path="/breakdowns" element={<BreakdownsPage />} />
          <Route path="/breakdowns/:slug" element={<BreakdownsPage />} />
        </Route>
        <Route path="/" element={<Navigate to="/regulations" replace />} />
        <Route path="*" element={<Navigate to="/regulations" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
