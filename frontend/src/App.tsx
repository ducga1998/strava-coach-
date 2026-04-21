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
import { SkeletonBlock, SkeletonLine } from "./components/Skeleton"

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
              <Suspense fallback={<AdminRouteSkeleton />}>
                <AdminApp />
              </Suspense>
            }
          />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

function AdminRouteSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading admin" className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-5xl space-y-4">
        <SkeletonLine height="1.25rem" width="200px" />
        <SkeletonBlock className="h-20 w-full" rounded="lg" />
        <SkeletonBlock className="h-64 w-full" rounded="lg" />
      </div>
    </div>
  )
}
