import { useEffect, useState } from "react"

const ROTATING: string[] = [
  "[INFO] Ingesting Strava stream…",
  "[OK] Stream buffered",
  "[INFO] Computing ACWR…",
  "[OK] 1.12",
  "[INFO] hrTSS rollup…",
  "[OK] 312",
  "[INFO] LangGraph debrief queue…",
  "[OK] Worker idle",
]

export default function TerminalFooter() {
  const [lines, setLines] = useState<string[]>(() => ["[INFO] Strava AI Coach — awaiting sync"])

  useEffect(() => {
    let i = 0
    const id = window.setInterval(() => {
      const line = ROTATING[i % ROTATING.length]
      i += 1
      setLines((prev) => [...prev.slice(-14), line])
    }, 2100)
    return () => window.clearInterval(id)
  }, [])

  return (
    <footer className="border-t border-white/[0.14] bg-black/70 px-4 py-4 font-mono text-[11px] text-brand-muted backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl flex-col gap-1">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-brand-teal">// pipeline</p>
        <div className="max-h-24 overflow-hidden leading-relaxed">
          {lines.map((line, idx) => (
            <p
              className={line.includes("[OK]") ? "text-emerald-300" : "text-brand-muted"}
              key={`${idx}-${line}`}
            >
              {line}
            </p>
          ))}
        </div>
      </div>
    </footer>
  )
}
