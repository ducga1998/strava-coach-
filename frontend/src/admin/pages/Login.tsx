import { FormEvent, useState } from "react"
import { Navigate, useNavigate } from "react-router-dom"
import { useAdminLogin, useAdminMe } from "../api"

export default function Login() {
  const { data: me, isLoading: meLoading } = useAdminMe()
  const login = useAdminLogin()
  const navigate = useNavigate()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")

  if (meLoading) return null
  if (me) return <Navigate to="/admin" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    try {
      await login.mutateAsync({ email, password })
      navigate("/admin", { replace: true })
    } catch {
      // react-query holds the error; UI reads login.error below
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm space-y-4 rounded-xl bg-white p-8 shadow"
      >
        <h1 className="text-xl font-semibold">Admin login</h1>

        <label className="block">
          <span className="mb-1 block text-sm text-slate-700">Email</span>
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full rounded border border-slate-300 px-3 py-2"
            autoFocus
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-sm text-slate-700">Password</span>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="w-full rounded border border-slate-300 px-3 py-2"
          />
        </label>

        {login.isError && (
          <div className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">
            {login.error?.response?.data?.detail ?? "Login failed"}
          </div>
        )}

        <button
          type="submit"
          disabled={login.isPending}
          className="w-full rounded bg-slate-900 py-2 text-white disabled:bg-slate-400"
        >
          {login.isPending ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  )
}
