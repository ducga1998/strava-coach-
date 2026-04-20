export type Admin = {
  id: number
  email: string
  name: string | null
}

export type LoginRequest = {
  email: string
  password: string
}

export type ChangePasswordRequest = {
  current: string
  new: string
}

export type LoginError = {
  detail: string
}

export interface AdminFeedbackItem {
  id: number
  thumb: "up" | "down"
  comment: string | null
  created_at: string
  read_at: string | null
  activity_id: number
  activity_name: string
  athlete_id: number
  athlete_name: string
}

export interface AdminFeedbackPage {
  items: AdminFeedbackItem[]
  next_cursor: number | null
}

export interface AdminFeedbackCounts {
  all: number
  up: number
  down: number
  unread: number
}

export type AdminFeedbackFilter = "all" | "up" | "down" | "unread"
