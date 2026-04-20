import { useState } from "react"
import {
  useAdminFeedbackCounts,
  useAdminFeedbackList,
  useMarkFeedbackRead,
} from "../api"
import type { AdminFeedbackFilter, AdminFeedbackItem } from "../types"

export default function FeedbackPage() {
  const [filter, setFilter] = useState<AdminFeedbackFilter>("all")
  const counts = useAdminFeedbackCounts()
  const list = useAdminFeedbackList(filter)
  const markRead = useMarkFeedbackRead()

  return (
    <div className="p-6">
      <h1 className="mb-4 text-2xl font-semibold">Phản hồi từ runner</h1>

      <div className="mb-6 flex flex-wrap gap-2">
        <Chip
          label={`Tất cả ${counts.data?.all ?? 0}`}
          active={filter === "all"}
          onClick={() => setFilter("all")}
        />
        <Chip
          label={`👎 ${counts.data?.down ?? 0}`}
          active={filter === "down"}
          onClick={() => setFilter("down")}
        />
        <Chip
          label={`👍 ${counts.data?.up ?? 0}`}
          active={filter === "up"}
          onClick={() => setFilter("up")}
        />
        <Chip
          label={`Chưa đọc ${counts.data?.unread ?? 0}`}
          active={filter === "unread"}
          onClick={() => setFilter("unread")}
        />
      </div>

      {list.isPending && <Skeleton />}
      {list.isError && (
        <ErrorBanner onRetry={() => list.refetch()} />
      )}
      {list.data && (
        <>
          {list.data.pages.flatMap((page) => page.items).length === 0 ? (
            <p className="text-sm text-slate-500">Chưa có phản hồi nào.</p>
          ) : (
            <ul className="space-y-3">
              {list.data.pages.flatMap((page) => page.items).map((item) => (
                <FeedbackCard
                  key={item.id}
                  item={item}
                  onRead={() => markRead.mutate(item.id)}
                />
              ))}
            </ul>
          )}
          {list.hasNextPage && (
            <button
              onClick={() => list.fetchNextPage()}
              disabled={list.isFetchingNextPage}
              className="mt-4 rounded border border-slate-300 px-4 py-2 text-sm hover:bg-slate-50"
            >
              {list.isFetchingNextPage ? "Đang tải…" : "Tải thêm"}
            </button>
          )}
        </>
      )}
    </div>
  )
}

function Chip(props: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={props.onClick}
      className={
        "rounded-full px-3 py-1.5 text-sm transition " +
        (props.active
          ? "bg-slate-900 text-white"
          : "bg-slate-100 text-slate-700 hover:bg-slate-200")
      }
    >
      {props.label}
    </button>
  )
}

function FeedbackCard(props: { item: AdminFeedbackItem; onRead: () => void }) {
  const { item } = props
  const unread = item.read_at === null
  return (
    <li
      onClick={() => {
        if (unread) props.onRead()
      }}
      className={
        "cursor-pointer rounded-lg border p-4 transition " +
        (unread
          ? "border-orange-200 bg-orange-50/50 hover:bg-orange-50"
          : "border-slate-200 bg-white hover:bg-slate-50")
      }
    >
      <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
        <span className="text-base">{item.thumb === "up" ? "👍" : "👎"}</span>
        <span className="font-semibold">{item.athlete_name}</span>
        <span className="text-slate-400">·</span>
        <span className="text-slate-700">{item.activity_name}</span>
        <span className="text-slate-400">·</span>
        <span className="text-slate-500">{relativeTime(item.created_at)}</span>
        {unread && <UnreadDot />}
        <a
          href={`/activities/${item.activity_id}?athlete_id=${item.athlete_id}`}
          target="_blank"
          rel="noreferrer"
          onClick={(event) => event.stopPropagation()}
          className="ml-auto text-sm text-blue-600 hover:underline"
        >
          Mở activity →
        </a>
      </div>
      {item.comment ? (
        <p className="whitespace-pre-wrap text-sm text-slate-700">{item.comment}</p>
      ) : (
        <p className="text-sm italic text-slate-400">(không có comment)</p>
      )}
    </li>
  )
}

function UnreadDot() {
  return (
    <span
      aria-label="chưa đọc"
      className="ml-1 inline-block h-2 w-2 rounded-full bg-orange-500"
    />
  )
}

function Skeleton() {
  return (
    <ul className="space-y-3">
      {[0, 1, 2].map((i) => (
        <li key={i} className="h-24 animate-pulse rounded-lg bg-slate-100" />
      ))}
    </ul>
  )
}

function ErrorBanner(props: { onRetry: () => void }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
      <p>Không tải được danh sách phản hồi.</p>
      <button
        onClick={props.onRetry}
        className="mt-2 rounded border border-red-300 px-3 py-1 text-xs hover:bg-red-100"
      >
        Tải lại
      </button>
    </div>
  )
}

function relativeTime(iso: string): string {
  const date = new Date(iso)
  const diffSec = Math.floor((Date.now() - date.getTime()) / 1000)
  if (diffSec < 60) return "vừa xong"
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}p trước`
  if (diffSec < 86_400) return `${Math.floor(diffSec / 3600)}h trước`
  return `${Math.floor(diffSec / 86_400)}d trước`
}
