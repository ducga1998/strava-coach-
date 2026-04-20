import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import axios, { AxiosError } from "axios"
import type {
  Admin,
  AdminFeedbackCounts,
  AdminFeedbackFilter,
  AdminFeedbackItem,
  AdminFeedbackPage,
  ChangePasswordRequest,
  LoginError,
  LoginRequest,
} from "./types"

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

export const adminFeedbackKeys = {
  list: (filter: AdminFeedbackFilter) => ["admin", "feedback", "list", filter] as const,
  counts: ["admin", "feedback", "counts"] as const,
}

function buildListQuery(filter: AdminFeedbackFilter, cursor: number | null): string {
  const params = new URLSearchParams()
  if (filter === "up" || filter === "down") params.set("thumb", filter)
  if (filter === "unread") params.set("unread", "true")
  if (cursor !== null) params.set("cursor", String(cursor))
  const qs = params.toString()
  return qs ? `/admin/feedback?${qs}` : "/admin/feedback"
}

export function useAdminFeedbackList(filter: AdminFeedbackFilter) {
  return useInfiniteQuery<AdminFeedbackPage, AxiosError>({
    queryKey: adminFeedbackKeys.list(filter),
    initialPageParam: null as number | null,
    queryFn: async ({ pageParam }) => {
      const { data } = await adminHttp.get<AdminFeedbackPage>(
        buildListQuery(filter, pageParam as number | null),
      )
      return data
    },
    getNextPageParam: (last) => last.next_cursor,
  })
}

export function useAdminFeedbackCounts() {
  return useQuery<AdminFeedbackCounts, AxiosError>({
    queryKey: adminFeedbackKeys.counts,
    queryFn: async () => {
      const { data } = await adminHttp.get<AdminFeedbackCounts>("/admin/feedback/counts")
      return data
    },
    staleTime: 30_000,
  })
}

export function useMarkFeedbackRead() {
  const qc = useQueryClient()
  return useMutation<void, AxiosError, number>({
    mutationFn: async (feedbackId) => {
      await adminHttp.patch(`/admin/feedback/${feedbackId}/read`)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: adminFeedbackKeys.counts })
      qc.invalidateQueries({ queryKey: ["admin", "feedback", "list"] })
    },
  })
}

export type { AdminFeedbackItem }
