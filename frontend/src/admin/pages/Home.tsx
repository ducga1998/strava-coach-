import { useAdminMe } from "../api"

export default function Home() {
  const { data } = useAdminMe()
  return (
    <div className="p-8">
      <h1 className="mb-2 text-2xl font-semibold">Welcome, {data?.name ?? data?.email}</h1>
      <p className="text-slate-600">
        Admin dashboard home. Overview stats land in a later slice.
      </p>
    </div>
  )
}
