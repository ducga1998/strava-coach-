import { useMutation, useQuery } from "@tanstack/react-query"
import { useEffect, useMemo, useState } from "react"
import { useParams, useSearchParams } from "react-router-dom"
import { getExistingFeedback, submitFeedback } from "../api/client"
import { SkeletonBlock, SkeletonLine } from "../components/Skeleton"
import type { FeedbackThumb } from "../types"

type Status = "idle" | "submitting" | "submitted" | "error"

export default function Feedback() {
  const activityId = useActivityId()
  const athleteId = useAthleteId()
  if (activityId === null || athleteId === null) return <MissingParams />
  return <FeedbackForm activityId={activityId} athleteId={athleteId} />
}

function FeedbackForm(props: { activityId: number; athleteId: number }) {
  const { activityId, athleteId } = props
  const existingQuery = useQuery({
    queryKey: ["feedback", "existing", activityId, athleteId],
    queryFn: () => getExistingFeedback(activityId, athleteId),
  })
  const mutation = useMutation({
    mutationFn: submitFeedback,
  })
  const [thumb, setThumb] = useState<FeedbackThumb | null>(null)
  const [comment, setComment] = useState("")
  const [status, setStatus] = useState<Status>("idle")

  useEffect(() => {
    if (existingQuery.data?.existing) setStatus("submitted")
  }, [existingQuery.data?.existing])

  const stravaActivityId = existingQuery.data?.strava_activity_id

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (thumb === null || status === "submitting") return
    setStatus("submitting")
    try {
      await mutation.mutateAsync({
        activity_id: activityId,
        athlete_id: athleteId,
        thumb,
        comment: comment.trim() || undefined,
      })
      setStatus("submitted")
    } catch {
      setStatus("error")
    }
  }

  if (existingQuery.isPending) {
    return (
      <Shell>
        <div aria-busy="true" aria-label="Đang tải" className="space-y-5">
          <SkeletonBlock className="h-8 w-8" rounded="md" />
          <div className="space-y-2">
            <SkeletonLine height="1rem" width="80%" />
            <SkeletonLine height="0.75rem" width="90%" />
            <SkeletonLine height="0.75rem" width="60%" />
          </div>
          <div className="flex gap-3">
            <SkeletonBlock className="h-16 flex-1" rounded="xl" />
            <SkeletonBlock className="h-16 flex-1" rounded="xl" />
          </div>
          <SkeletonBlock className="h-20 w-full" rounded="lg" />
          <SkeletonBlock className="h-11 w-full" rounded="lg" />
        </div>
      </Shell>
    )
  }

  if (status === "submitted") {
    return (
      <Shell>
        <div className="text-center">
          <div className="mb-2 text-4xl">💚</div>
          <h1 className="text-xl font-semibold">Nhận rồi — cảm ơn anh!</h1>
          <p className="mt-2 text-sm text-slate-600">
            Phản hồi của anh giúp tụi mình chỉnh debrief tốt hơn cho lần sau.
          </p>
          {stravaActivityId !== undefined && (
            <BackToStrava stravaActivityId={stravaActivityId} />
          )}
        </div>
      </Shell>
    )
  }

  return (
    <Shell>
      <div className="mb-1 text-3xl">👋</div>
      <h1 className="text-lg font-semibold leading-snug">
        Debrief này giúp được anh bao nhiêu?
      </h1>
      <p className="mt-1.5 text-sm text-slate-600 leading-relaxed">
        Tụi mình đang học cách viết debrief tốt hơn — mọi góc nhìn đều quý.
      </p>

      <form onSubmit={onSubmit} className="mt-5 space-y-4">
        <div className="flex gap-3">
          <ThumbButton
            label="👍"
            active={thumb === "up"}
            onClick={() => setThumb("up")}
          />
          <ThumbButton
            label="👎"
            active={thumb === "down"}
            onClick={() => setThumb("down")}
          />
        </div>

        <div>
          <label className="text-xs font-medium text-slate-600">
            Chia sẻ thêm (không bắt buộc)
          </label>
          <textarea
            className="mt-1.5 w-full rounded-lg border border-stone-200 bg-white p-3 text-sm focus:border-orange-400 focus:outline-none focus:ring-1 focus:ring-orange-200"
            rows={3}
            maxLength={2000}
            placeholder="VD: Next-action không thực tế với lịch của em..."
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            disabled={status === "submitting"}
          />
        </div>

        <button
          type="submit"
          disabled={thumb === null || status === "submitting"}
          className="w-full rounded-lg bg-slate-900 py-3 text-sm font-semibold text-white transition disabled:opacity-40"
        >
          {status === "submitting" ? "Đang gửi…" : "Gửi phản hồi"}
        </button>

        {status === "error" && (
          <p className="text-center text-sm text-red-600">
            Có lỗi xảy ra, anh thử lại giúp em nhé.
          </p>
        )}

        <p className="pt-1 text-center text-xs text-slate-400">
          Cảm ơn anh — đọc từng chữ.
        </p>
      </form>
    </Shell>
  )
}

function Shell(props: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-stone-50 px-4 py-8">
      <div className="mx-auto max-w-md rounded-2xl bg-white p-6 shadow-sm">
        {props.children}
      </div>
    </main>
  )
}

function ThumbButton(props: {
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={props.onClick}
      className={
        "flex-1 rounded-xl border-2 py-4 text-2xl transition " +
        (props.active
          ? "border-orange-500 bg-orange-50"
          : "border-stone-200 bg-white hover:border-stone-300")
      }
      aria-pressed={props.active}
    >
      {props.label}
    </button>
  )
}

function BackToStrava(props: { stravaActivityId: number }) {
  const webUrl = `https://www.strava.com/activities/${props.stravaActivityId}`
  const deepLink = `strava://activities/${props.stravaActivityId}`
  return (
    <a
      href={deepLink}
      onClick={(event) => {
        event.preventDefault()
        window.location.href = deepLink
        window.setTimeout(() => {
          window.location.href = webUrl
        }, 600)
      }}
      className="mt-5 inline-block rounded-lg bg-orange-500 px-5 py-2.5 text-sm font-semibold text-white"
    >
      Quay lại Strava
    </a>
  )
}

function MissingParams() {
  return (
    <main className="min-h-screen bg-stone-50 px-4 py-8">
      <div className="mx-auto max-w-md rounded-2xl bg-white p-6 shadow-sm">
        <p className="text-sm text-slate-600">
          Link không hợp lệ. Anh mở lại từ activity trên Strava giúp em nhé.
        </p>
      </div>
    </main>
  )
}

function useActivityId(): number | null {
  const params = useParams<{ activityId: string }>()
  const parsed = Number(params.activityId)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function useAthleteId(): number | null {
  const [params] = useSearchParams()
  const raw = params.get("athlete_id")
  const parsed = useMemo(() => (raw === null ? NaN : Number(raw)), [raw])
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}
