import axios, {
  AxiosError,
  type AxiosInstance,
  type AxiosResponse,
} from "axios"
import type {
  ActivityDetailResponse,
  ActivityListItem,
  AthleteInfo,
  AthleteProfileInfo,
  DashboardLoadResponse,
  ExistingFeedbackResponse,
  FeedbackCreateRequest,
  FeedbackItem,
  LanguageCode,
  OnboardingProfilePayload,
  PlanConfig,
  PlanEntry,
  PushDescriptionResponse,
  RaceTarget,
  RaceTargetPayload,
  RaceTargetUpdatePayload,
  SyncReport,
} from "../types"

const ATHLETE_ID_STORAGE_KEY = "strava-coach-athlete-id"

export const api: AxiosInstance = axios.create({
  baseURL: getApiBaseUrl(),
  withCredentials: true,
  headers: {
    Accept: "application/json",
  },
})

export class ApiClientError extends Error {
  readonly status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.name = "ApiClientError"
    this.status = status
  }
}

export function getApiBaseUrl(): string {
  return import.meta.env.VITE_API_URL ?? "http://localhost:8000"
}

export function getStoredAthleteId(): number | null {
  if (typeof window === "undefined") return null
  const queryId = parseAthleteId(new URLSearchParams(window.location.search))
  if (queryId !== null) return persistAthleteId(queryId)
  return parsePositiveNumber(window.localStorage.getItem(ATHLETE_ID_STORAGE_KEY))
}

export function persistAthleteId(athleteId: number): number {
  window.localStorage.setItem(ATHLETE_ID_STORAGE_KEY, String(athleteId))
  return athleteId
}

export function clearAthleteId(): void {
  window.localStorage.removeItem(ATHLETE_ID_STORAGE_KEY)
}

export function requireAthleteId(athleteId: number | null): number {
  if (athleteId === null) {
    throw new ApiClientError("Athlete id is required before calling this API")
  }
  return athleteId
}

export async function getAthleteInfo(athleteId: number): Promise<AthleteInfo> {
  return request(api.get(`/athletes/${athleteId}`))
}

export async function updateAthleteLanguage(
  athleteId: number,
  language: LanguageCode,
): Promise<AthleteProfileInfo> {
  return request(api.patch(`/athletes/${athleteId}/language`, { language }))
}

export async function getDashboardLoad(
  athleteId: number,
): Promise<DashboardLoadResponse> {
  return request(api.get(`/dashboard/load?athlete_id=${athleteId}`))
}

export async function listActivities(
  athleteId: number,
): Promise<ActivityListItem[]> {
  return request(api.get(`/activities/?athlete_id=${athleteId}`))
}

export async function getActivityDetail(
  activityId: number,
): Promise<ActivityDetailResponse> {
  return request(api.get(`/activities/${activityId}`))
}

export async function pushActivityDescription(
  activityId: number,
): Promise<PushDescriptionResponse> {
  return request(api.post(`/activities/${activityId}/push-description`))
}

export async function saveOnboardingProfile(
  payload: OnboardingProfilePayload,
): Promise<void> {
  await request(api.post("/onboarding/profile", payload))
}

export async function listRaceTargets(
  athleteId: number,
): Promise<RaceTarget[]> {
  return request(api.get(`/targets/?athlete_id=${athleteId}`))
}

export async function createRaceTarget(
  payload: RaceTargetPayload,
): Promise<RaceTarget> {
  return request(api.post("/targets", payload))
}

export async function updateRaceTarget(params: {
  id: number
  payload: RaceTargetUpdatePayload
}): Promise<RaceTarget> {
  return request(api.put(`/targets/${params.id}`, params.payload))
}

export async function deleteRaceTarget(params: {
  id: number
  athleteId: number
}): Promise<void> {
  await request(api.delete(`/targets/${params.id}?athlete_id=${params.athleteId}`))
}

export async function getExistingFeedback(
  activityId: number,
  athleteId: number,
): Promise<ExistingFeedbackResponse> {
  return request(api.get(`/feedback/activity/${activityId}?athlete_id=${athleteId}`))
}

export async function submitFeedback(
  payload: FeedbackCreateRequest,
): Promise<FeedbackItem> {
  return request(api.post("/feedback", payload))
}

export const PLAN_TEMPLATE_SHEET_URL =
  "https://docs.google.com/spreadsheets/d/your-template-id/edit"
// TODO(post-MVP): serve this from the backend so we can change it
//                 without a frontend deploy. Tracked in spec open question #3.

export async function putPlanConfig(params: {
  athleteId: number
  sheetUrl: string
}): Promise<PlanConfig> {
  return request(
    api.put("/plan/config", {
      athlete_id: params.athleteId,
      sheet_url: params.sheetUrl,
    }),
  )
}

export async function deletePlanConfig(athleteId: number): Promise<void> {
  await request(api.delete(`/plan/config?athlete_id=${athleteId}`))
}

export async function syncPlan(athleteId: number): Promise<SyncReport> {
  return request(api.post("/plan/sync", { athlete_id: athleteId }))
}

export async function importCsvText(params: {
  athleteId: number
  csvText: string
}): Promise<SyncReport> {
  return request(
    api.post("/plan/import-csv", {
      athlete_id: params.athleteId,
      csv_text: params.csvText,
    }),
  )
}

export async function getPlanRange(params: {
  athleteId: number
  from: string   // YYYY-MM-DD
  to: string
}): Promise<PlanEntry[]> {
  return request(
    api.get(
      `/plan?athlete_id=${params.athleteId}&from=${params.from}&to=${params.to}`,
    ),
  )
}

async function request<T>(promise: Promise<AxiosResponse<T>>): Promise<T> {
  try {
    const response = await promise
    return response.data
  } catch (error: unknown) {
    throw normalizeApiError(error)
  }
}

function parseAthleteId(params: URLSearchParams): number | null {
  return parsePositiveNumber(params.get("athlete_id"))
}

function parsePositiveNumber(value: string | null): number | null {
  if (value === null || value.trim() === "") return null
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function normalizeApiError(error: unknown): ApiClientError {
  if (!axios.isAxiosError(error)) return new ApiClientError("Unexpected error")
  return fromAxiosError(error)
}

function fromAxiosError(error: AxiosError<unknown>): ApiClientError {
  const status = error.response?.status
  const message = getErrorMessage(error.response?.data) ?? error.message
  return new ApiClientError(message, status)
}

function getErrorMessage(data: unknown): string | null {
  if (!isRecord(data)) return null
  const detail = data.detail ?? data.message
  return typeof detail === "string" ? detail : null
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null
}
