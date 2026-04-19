import { motion, useMotionValue, useSpring, useTransform } from "framer-motion"

const card =
  "group relative overflow-hidden rounded-2xl border border-white/[0.14] bg-brand-charcoal/80 p-6 shadow-[0_20px_60px_rgba(0,0,0,0.45)] transition hover:border-brand-teal/45"

export default function FeatureBento() {
  return (
    <section className="bg-brand-void px-4 py-24">
      <div className="mx-auto max-w-6xl">
        <p className="font-mono text-xs font-semibold uppercase tracking-[0.3em] text-brand-teal">The stack</p>
        <h2 className="mt-3 text-3xl font-bold text-white md:text-4xl">Built for the long game</h2>
        <p className="mt-4 max-w-2xl text-brand-muted">
          Subjective memory, vert debt, and race-day cognition — not just pace and distance.
        </p>

        <div className="mt-14 grid gap-4 md:grid-cols-2">
          <motion.div className={card} whileHover={{ scale: 1.01 }}>
            <span className="font-mono text-[10px] font-bold text-brand-muted">01</span>
            <h3 className="mt-2 text-lg font-bold text-white">Subjective Memory</h3>
            <p className="mt-2 text-sm leading-relaxed text-brand-muted">
              &quot;I saw ghosts at mile 80.&quot; AI remembers your notes to adjust future load.
            </p>
            <div className="relative mt-6 h-28 rounded-xl border border-white/10 bg-black/40 p-3">
              <motion.div
                animate={{ y: [0, -4, 0] }}
                className="max-w-[85%] rounded-lg rounded-bl-none border border-brand-teal/30 bg-brand-teal/10 px-3 py-2 font-mono text-[10px] text-brand-teal"
                transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
              >
                flagged: hallucination @ km 128
              </motion.div>
              <motion.span
                animate={{ opacity: [0.4, 1, 0.4] }}
                className="absolute bottom-3 right-3 rounded-full border border-amber-400/50 bg-amber-500/20 px-2 py-0.5 font-mono text-[9px] font-semibold uppercase text-amber-200"
                transition={{ duration: 2.2, repeat: Infinity }}
              >
                hallucination
              </motion.span>
            </div>
          </motion.div>

          <VertDebtCard />

          <motion.div className={card} whileHover={{ scale: 1.01 }}>
            <span className="font-mono text-[10px] font-bold text-brand-muted">03</span>
            <h3 className="mt-2 text-lg font-bold text-white">The Strava Push</h3>
            <p className="mt-2 text-sm leading-relaxed text-brand-muted">
              Automatic coaching insights pushed directly to your Strava description.
            </p>
            <div className="relative mt-6 h-28 overflow-hidden rounded-xl border border-white/10 bg-slate-950/80">
              <motion.div
                animate={{ x: ["100%", "0%", "0%", "-100%"] }}
                className="absolute inset-y-0 right-0 flex w-[92%] flex-col gap-1 border-l border-white/10 bg-slate-900/95 p-2"
                transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
              >
                <p className="font-mono text-[9px] text-slate-400">Morning trail · 42 km</p>
                <p className="text-[10px] leading-snug text-slate-100">
                  Debrief: Aerobic decoupling +6.2% after 3h — hold Z2 next long run.
                </p>
              </motion.div>
              <p className="p-2 font-mono text-[9px] text-slate-500">activity feed…</p>
            </div>
          </motion.div>

          <motion.div className={card} whileHover={{ scale: 1.01 }}>
            <span className="font-mono text-[10px] font-bold text-brand-muted">04</span>
            <h3 className="mt-2 text-lg font-bold text-white">Local-first</h3>
            <p className="mt-2 text-sm leading-relaxed text-brand-muted">
              Privacy by design. Your physiological data never leaves your device.
            </p>
            <div className="mt-6 flex h-28 items-center justify-center rounded-xl border border-white/10 bg-black/40">
              <motion.div
                animate={{ scale: [1, 1.08, 1], opacity: [0.7, 1, 0.7] }}
                className="flex flex-col items-center gap-2"
                transition={{ duration: 2.5, repeat: Infinity }}
              >
                <span className="text-3xl" aria-hidden>
                  🔒
                </span>
                <span className="font-mono text-[10px] font-semibold text-brand-teal">0ms latency</span>
              </motion.div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  )
}

function VertDebtCard() {
  const progress = useMotionValue(0)
  const spring = useSpring(progress, { stiffness: 120, damping: 22 })
  const c = 2 * Math.PI * 28
  const dash = useTransform(spring, [0, 1], [c, 0])

  function onEnter() {
    progress.set(1)
  }
  function onLeave() {
    progress.set(0)
  }

  return (
    <motion.div
      className={card}
      data-metric-hover
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      whileHover={{ scale: 1.01 }}
    >
      <span className="font-mono text-[10px] font-bold text-brand-muted">02</span>
      <h3 className="mt-2 text-lg font-bold text-white">Vert Debt Gauge</h3>
      <p className="mt-2 text-sm leading-relaxed text-brand-muted">
        VMM 160 is about climbing. Track cumulative vertical gain vs. target.
      </p>
      <div className="mt-6 flex h-32 items-center justify-center">
        <div className="relative h-28 w-28">
          <svg className="-rotate-90" viewBox="0 0 64 64">
            <circle cx="32" cy="32" fill="none" r="28" stroke="rgba(255,255,255,0.08)" strokeWidth="6" />
            <motion.circle
              cx="32"
              cy="32"
              fill="none"
              r="28"
              stroke="#00ffd1"
              strokeDasharray={2 * Math.PI * 28}
              strokeLinecap="round"
              strokeWidth="6"
              style={{ strokeDashoffset: dash }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="font-mono text-xl font-bold text-white">72%</span>
            <span className="font-mono text-[9px] uppercase text-brand-muted">vert debt</span>
          </div>
        </div>
      </div>
    </motion.div>
  )
}
