import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter, Route, Routes } from "react-router-dom"
import ActivityDetail from "./pages/ActivityDetail"
import Connect from "./pages/Connect"
import Dashboard from "./pages/Dashboard"
import Setup from "./pages/Setup"
import Targets from "./pages/Targets"

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
          <Route path="/" element={<Connect />} />
          <Route path="/setup" element={<Setup />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/activities/:id" element={<ActivityDetail />} />
          <Route path="/targets" element={<Targets />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
