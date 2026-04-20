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
