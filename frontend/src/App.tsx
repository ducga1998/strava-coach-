import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { lazy, Suspense } from "react"
import { BrowserRouter, Route, Routes } from "react-router-dom"
import ActivityDetail from "./pages/ActivityDetail"
import Connect from "./pages/Connect"
import Dashboard from "./pages/Dashboard"
import Feedback from "./pages/Feedback"
import Home from "./pages/Home"
import Setup from "./pages/Setup"
import Targets from "./pages/Targets"

const AdminApp = lazy(() => import("./admin/AdminApp"))

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/connect" element={<Connect />} />
          <Route path="/setup" element={<Setup />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/activities/:id" element={<ActivityDetail />} />
          <Route path="/feedback/:activityId" element={<Feedback />} />
          <Route path="/targets" element={<Targets />} />
          <Route
            path="/admin/*"
            element={
              <Suspense fallback={<div className="p-8">Loading admin…</div>}>
                <AdminApp />
              </Suspense>
            }
          />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
