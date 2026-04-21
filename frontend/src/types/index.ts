export type UnitSystem = "metric" | "imperial"
export type LanguageCode = "en" | "vi"
export type RacePriority = "A" | "B" | "C"
export type TrainingPhase = "Base" | "Build" | "Peak" | "Taper"
export type ProcessingStatus = "pending" | "processing" | "done" | "failed"

export interface LoadPoint {
  date: string
  ctl: number
  atl: number
  tsb: number
  acwr?: number
}

export type AcwrZone = "green" | "yellow" | "red"

export interface LoadSnapshot {
  ctl: number
  atl: number
  tsb: number
  acwr: number
  /** Optional — provided by backend per LEADER.md contract; may be absent in current impl. */
  acwr_zone?: AcwrZone
}

export interface WeeklyVolume {
  distance_km: number
  elevation_gain_m: number
  duration_sec?: number
}

export interface RaceTarget {
  id: number
  athlete_id?: number
  race_name: string
  race_date: string
  distance_km: number
  elevation_gain_m: number | null
  goal_time_sec: number | null
  priority: RacePriority
}

export interface DashboardLoadResponse {
  training_phase: TrainingPhase
  latest: LoadSnapshot
  history: LoadPoint[]
  weekly_volume?: WeeklyVolume
  target?: RaceTarget | null
  /** Optional server-provided warning copy (per LEADER.md). Display verbatim when present. */
  warning?: string | null
}

export interface ActivityListItem {
  id: number
  strava_activity_id: number
  name: string
  sport_type: string
  start_date: string
  distance_m: number
  elapsed_time_sec: number
  total_elevation_gain_m?: number | null
  processing_status: ProcessingStatus
}

export interface ActivityMetrics {
  tss: number | null
  hr_tss: number | null
  gap_avg_sec_km?: number | null
  ngp_sec_km: number | null
  hr_drift_pct: number | null
  aerobic_decoupling_pct: number | null
  zone_distribution?: ZoneDistribution | null
}

export interface ZoneDistribution {
  z1_pct: number
  z2_pct: number
  z3_pct: number
  z4_pct: number
  z5_pct: number
}

export interface Debrief {
  load_verdict: string
  technical_insight: string
  next_session_action: string
  nutrition_protocol?: string
  vmm_projection?: string
  plan_compliance?: string
}

export interface ActivityDetail {
  id: number
  name: string
  sport_type: string
  start_date: string
  distance_m: number
  elapsed_time_sec: number
  total_elevation_gain_m: number | null
}

export interface ActivityDetailResponse {
  activity: ActivityDetail
  metrics: ActivityMetrics | null
  debrief: Debrief | null
}

export interface OnboardingProfilePayload {
  athlete_id: number
  lthr?: number
  max_hr?: number
  threshold_pace_sec_km?: number
  weight_kg?: number
  vo2max_estimate?: number
  units: UnitSystem
  language: LanguageCode
}

export interface RaceTargetPayload {
  athlete_id: number
  race_name: string
  race_date: string
  distance_km: number
  elevation_gain_m?: number
  goal_time_sec?: number
  priority: RacePriority
}

export type RaceTargetUpdatePayload = Partial<
  Omit<RaceTargetPayload, "athlete_id">
> & {
  athlete_id: number
}

export interface AthleteProfileInfo {
  onboarding_complete: boolean
  lthr: number | null
  max_hr: number | null
  threshold_pace_sec_km: number | null
  weight_kg: number | null
  vo2max_estimate: number | null
}

export interface PushDescriptionResponse {
  description: string
}

export interface AthleteInfo {
  id: number
  strava_athlete_id: number
  firstname: string | null
  lastname: string | null
  avatar_url: string | null
  city: string | null
  country: string | null
  profile: AthleteProfileInfo | null
}

export type FeedbackThumb = "up" | "down"

export interface FeedbackItem {
  id: number
  thumb: FeedbackThumb
  comment: string | null
  created_at: string
}

export interface FeedbackCreateRequest {
  activity_id: number
  athlete_id: number
  thumb: FeedbackThumb
  comment?: string
}

export interface ExistingFeedbackResponse {
  existing: FeedbackItem | null
  strava_activity_id: number
}

export type WorkoutType =
  | "recovery"
  | "easy"
  | "long"
  | "tempo"
  | "interval"
  | "hill"
  | "race"
  | "rest"
  | "cross"
  | "strength"

export interface PlanEntry {
  date: string  // ISO YYYY-MM-DD
  workout_type: WorkoutType
  planned_tss: number | null
  planned_duration_min: number | null
  planned_distance_km: number | null
  planned_elevation_m: number | null
  description: string | null
}

export interface PlanConfig {
  athlete_id: number
  sheet_url: string | null
  plan_synced_at: string | null
}

export interface SyncReportRow {
  row_number: number
  reason: string
}

export interface SyncReport {
  status: "ok" | "failed"
  fetched_rows: number
  accepted: number
  rejected: SyncReportRow[]
  error: string | null
}
