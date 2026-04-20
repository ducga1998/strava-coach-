import { Link, useNavigate } from "react-router-dom"
import { useAdminLogout, useAdminMe } from "../api"

export default function AdminNav() {
  const { data } = useAdminMe()
  const logout = useAdminLogout()
  const navigate = useNavigate()

  async function handleLogout() {
    try {
      await logout.mutateAsync()
    } catch {
      // Session may still be alive server-side, but the user clicked logout.
      // We navigate to login anyway — the session will expire on its own.
    }
    navigate("/admin/login", { replace: true })
  }

  return (
    <nav className="flex h-14 items-center justify-between border-b border-slate-200 px-6">
      <div className="flex items-center gap-6">
        <span className="font-semibold">Admin</span>
        <Link to="/admin" className="text-sm text-slate-700 hover:text-slate-900">
          Home
        </Link>
        <span className="text-sm text-slate-400">Users</span>
        <span className="text-sm text-slate-400">Prompts</span>
        <span className="text-sm text-slate-400">Debriefs</span>
      </div>
      <div className="flex items-center gap-4 text-sm text-slate-600">
        <span>{data?.name ?? data?.email}</span>
        <button
          onClick={handleLogout}
          className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100"
        >
          Logout
        </button>
      </div>
    </nav>
  )
}
