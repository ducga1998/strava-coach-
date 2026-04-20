import { ReactNode } from "react"
import { Navigate, useLocation } from "react-router-dom"
import { useAdminMe } from "../api"

type Props = { children: ReactNode }

export default function RequireAdmin({ children }: Props) {
  const location = useLocation()
  const { data, isLoading, isError } = useAdminMe()

  if (isLoading) {
    return <div className="p-8 text-slate-500">Checking session…</div>
  }
  if (isError || !data) {
    return <Navigate to="/admin/login" state={{ from: location.pathname }} replace />
  }
  return <>{children}</>
}
