import { Route, Routes } from "react-router-dom"
import AdminNav from "./components/AdminNav"
import RequireAdmin from "./components/RequireAdmin"
import Feedback from "./pages/Feedback"
import Home from "./pages/Home"
import Login from "./pages/Login"

function Protected({ children }: { children: React.ReactNode }) {
  return (
    <RequireAdmin>
      <div className="min-h-screen bg-white">
        <AdminNav />
        {children}
      </div>
    </RequireAdmin>
  )
}

export default function AdminApp() {
  return (
    <Routes>
      <Route path="login" element={<Login />} />
      <Route path="feedback" element={<Protected><Feedback /></Protected>} />
      <Route path="" element={<Protected><Home /></Protected>} />
      <Route path="*" element={<Protected><Home /></Protected>} />
    </Routes>
  )
}
