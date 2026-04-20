import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import axios, { AxiosError } from "axios"
import type { Admin, ChangePasswordRequest, LoginError, LoginRequest } from "./types"

const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000"

export const adminHttp = axios.create({
  baseURL: apiUrl,
  withCredentials: true, // send admin_session cookie
})

export const adminQueryKeys = {
  me: ["admin", "me"] as const,
}

export function useAdminMe() {
  return useQuery<Admin, AxiosError<LoginError>>({
    queryKey: adminQueryKeys.me,
    queryFn: async () => {
      const { data } = await adminHttp.get<Admin>("/admin/auth/me")
      return data
    },
    retry: false,
    staleTime: 60_000,
  })
}

export function useAdminLogin() {
  const qc = useQueryClient()
  return useMutation<Admin, AxiosError<LoginError>, LoginRequest>({
    mutationFn: async (body) => {
      const { data } = await adminHttp.post<Admin>("/admin/auth/login", body)
      return data
    },
    onSuccess: (data) => {
      qc.setQueryData(adminQueryKeys.me, data)
    },
  })
}

export function useAdminLogout() {
  const qc = useQueryClient()
  return useMutation<void, AxiosError>({
    mutationFn: async () => {
      await adminHttp.post("/admin/auth/logout")
    },
    onSuccess: () => {
      qc.setQueryData(adminQueryKeys.me, null)
      qc.invalidateQueries({ queryKey: adminQueryKeys.me })
    },
  })
}

export function useAdminChangePassword() {
  return useMutation<void, AxiosError<LoginError>, ChangePasswordRequest>({
    mutationFn: async (body) => {
      await adminHttp.post("/admin/auth/change-password", body)
    },
  })
}
