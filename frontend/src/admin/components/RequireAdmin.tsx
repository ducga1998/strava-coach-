import { ReactNode } from "react"
import { Navigate, useLocation } from "react-router-dom"
import { useAdminMe } from "../api"
import { SkeletonBlock, SkeletonLine } from "../../components/Skeleton"

type Props = { children: ReactNode }

export default function RequireAdmin({ children }: Props) {
  const location = useLocation()
  const { data, isLoading, isError } = useAdminMe()

  if (isLoading) {
    return <AdminAuthSkeleton />
  }
  if (isError || !data) {
    return <Navigate to="/admin/login" state={{ from: location.pathname }} replace />
  }
  return <>{children}</>
}

function AdminAuthSkeleton() {
  return (
    <div aria-busy="true" aria-label="Checking session" className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-5xl space-y-4">
        <div className="flex items-center gap-3">
          <SkeletonBlock className="h-10 w-10" rounded="full" />
          <div className="flex-1 space-y-2">
            <SkeletonLine height="1rem" width="180px" />
            <SkeletonLine height="0.625rem" width="120px" />
          </div>
        </div>
        <SkeletonBlock className="h-24 w-full" rounded="lg" />
        <SkeletonBlock className="h-64 w-full" rounded="lg" />
      </div>
    </div>
  )
}
