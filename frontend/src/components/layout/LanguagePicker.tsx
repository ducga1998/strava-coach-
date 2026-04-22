import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useRef, useState } from "react"
import { getAthleteInfo, getStoredAthleteId, updateAthleteLanguage } from "../../api/client"
import type { LanguageCode } from "../../types"

const OPTIONS: Array<{ code: LanguageCode; label: string; short: string }> = [
  { code: "en", label: "English", short: "EN" },
  { code: "vi", label: "Tiếng Việt", short: "VI" },
]

export default function LanguagePicker() {
  const athleteId = getStoredAthleteId()
  if (athleteId === null) return null
  return <LanguagePickerInner athleteId={athleteId} />
}

function LanguagePickerInner({ athleteId }: { athleteId: number }) {
  const queryClient = useQueryClient()
  const athleteQuery = useQuery({
    queryKey: ["athlete", athleteId],
    queryFn: () => getAthleteInfo(athleteId),
  })
  const mutation = useMutation({
    mutationFn: (language: LanguageCode) => updateAthleteLanguage(athleteId, language),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["athlete", athleteId] })
      setOpen(false)
      flashSaved()
    },
  })

  const [open, setOpen] = useState(false)
  const [saved, setSaved] = useState(false)
  const savedTimer = useRef<number | null>(null)
  const rootRef = useRef<HTMLDivElement | null>(null)

  function flashSaved() {
    setSaved(true)
    if (savedTimer.current !== null) window.clearTimeout(savedTimer.current)
    savedTimer.current = window.setTimeout(() => setSaved(false), 1800)
  }

  useEffect(() => {
    return () => {
      if (savedTimer.current !== null) window.clearTimeout(savedTimer.current)
    }
  }, [])

  useEffect(() => {
    if (!open) return
    function handleClickOutside(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [open])

  const current: LanguageCode = athleteQuery.data?.profile?.language ?? "en"
  const currentShort = OPTIONS.find((o) => o.code === current)?.short ?? "EN"

  return (
    <div className="relative" ref={rootRef}>
      <button
        aria-haspopup="listbox"
        aria-expanded={open}
        className="flex items-center gap-1 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 font-mono text-[11px] font-semibold text-brand-muted transition hover:border-white/30 hover:text-white disabled:opacity-50 md:text-xs"
        disabled={mutation.isPending || !athleteQuery.data}
        onClick={() => setOpen((v) => !v)}
        type="button"
      >
        {saved ? "Saved ✓" : mutation.isPending ? "…" : `${currentShort} ▾`}
      </button>
      {open ? (
        <ul
          className="absolute right-0 mt-2 min-w-[140px] overflow-hidden rounded-md border border-white/15 bg-brand-void/95 shadow-xl backdrop-blur-md"
          role="listbox"
        >
          {OPTIONS.map((option) => {
            const isCurrent = option.code === current
            return (
              <li key={option.code}>
                <button
                  aria-selected={isCurrent}
                  className={[
                    "flex w-full items-center justify-between gap-4 px-3 py-2 text-left font-mono text-[11px] transition md:text-xs",
                    isCurrent ? "text-white" : "text-brand-muted hover:bg-white/5 hover:text-white",
                  ].join(" ")}
                  disabled={isCurrent || mutation.isPending}
                  onClick={() => mutation.mutate(option.code)}
                  role="option"
                  type="button"
                >
                  <span>{option.label}</span>
                  <span className="text-[10px] uppercase tracking-wider opacity-60">
                    {option.short}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      ) : null}
    </div>
  )
}
