import { motion, useScroll, useTransform } from "framer-motion"
import { useRef } from "react"

/** Approximate VMM-style elevation polyline in viewBox 0 0 1200 200 */
const PATH_D =
  "M0 160 L80 140 L160 155 L240 120 L320 135 L400 90 L480 105 L560 70 L640 88 L720 55 L800 75 L880 45 L960 60 L1040 35 L1120 50 L1200 40"

const CPS = [
  { x: "8%", label: "CP1" },
  { x: "22%", label: "CP2" },
  { x: "36%", label: "CP3" },
  { x: "48%", label: "CP4", note: "3:00 AM · CNS fatigue. 200mg caffeine + 40g slow carbs." },
  { x: "58%", label: "CP5" },
  { x: "68%", label: "CP6" },
  { x: "78%", label: "CP7", note: "The Wall. HR drift 12%. Hold pace — sub-30h window." },
  { x: "90%", label: "CP8" },
]

export default function VmmHorizontal() {
  const scrollRef = useRef<HTMLDivElement>(null)
  const { scrollXProgress } = useScroll({ container: scrollRef })
  const pathDraw = useTransform(scrollXProgress, [0, 0.92], [0.08, 1])
  const cp4 = useTransform(scrollXProgress, [0.38, 0.52], [0, 1])
  const cp7 = useTransform(scrollXProgress, [0.62, 0.78], [0, 1])

  return (
    <section className="border-y border-white/[0.14] bg-[#030303] py-20">
      <div className="mx-auto max-w-6xl px-4">
        <p className="font-mono text-xs font-semibold uppercase tracking-[0.3em] text-brand-teal">VMM 160 km</p>
        <h2 className="mt-3 text-3xl font-bold text-white md:text-4xl">Scroll the race course</h2>
        <p className="mt-3 max-w-2xl text-brand-muted">
          Horizontal scrub: neon elevation trace with checkpoint intel — the same load language your debrief speaks.
        </p>
      </div>

      <div
        className="mt-12 w-full overflow-x-auto overflow-y-hidden scroll-smooth pb-4 [scrollbar-width:thin] [&::-webkit-scrollbar]:h-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-brand-teal/40"
        ref={scrollRef}
      >
        <div className="relative w-[340vw] min-w-[900px] px-4 md:w-[280vw]">
          <div className="relative h-[320px] md:h-[380px]">
            <svg className="absolute inset-0 h-full w-full" preserveAspectRatio="none" viewBox="0 0 1200 200">
              <defs>
                <linearGradient id="vmg" x1="0" x2="1" y1="0" y2="0">
                  <stop offset="0%" stopColor="#00ffd1" stopOpacity="0" />
                  <stop offset="50%" stopColor="#00ffd1" stopOpacity="0.9" />
                  <stop offset="100%" stopColor="#ccff00" stopOpacity="0.5" />
                </linearGradient>
                <filter id="vmBlur" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur result="b" stdDeviation="4" />
                  <feMerge>
                    <feMergeNode in="b" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>
              <motion.path
                d={`${PATH_D} L1200 200 L0 200 Z`}
                fill="url(#vmg)"
                opacity="0.12"
                stroke="none"
              />
              <motion.path
                d={PATH_D}
                fill="none"
                filter="url(#vmBlur)"
                pathLength={1}
                stroke="#00ffd1"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="3"
                style={{ pathLength: pathDraw }}
              />
            </svg>

            {CPS.map((cp) => (
              <div
                className="absolute top-[42%] flex -translate-x-1/2 flex-col items-center"
                key={cp.label}
                style={{ left: cp.x }}
              >
                <span className="rounded border border-white/20 bg-brand-void/90 px-2 py-0.5 font-mono text-[9px] font-bold text-brand-teal">
                  {cp.label}
                </span>
                <span className="mt-1 h-8 w-px bg-gradient-to-b from-brand-teal/60 to-transparent" />
              </div>
            ))}

            <motion.div
              className="absolute bottom-6 left-[44%] max-w-xs rounded-xl border border-brand-teal/40 bg-brand-void/95 p-4 font-mono text-[11px] leading-relaxed text-brand-muted shadow-[0_0_40px_rgba(0,255,209,0.12)] backdrop-blur-md md:left-[46%]"
              style={{ opacity: cp4 }}
            >
              <p className="text-[10px] font-bold uppercase tracking-wider text-brand-teal">CP4 · night trench</p>
              <p className="mt-2 text-slate-200">
                3:00 AM. CNS fatigue detected. AI recommends 200mg caffeine + 40g slow carbs.
              </p>
            </motion.div>

            <motion.div
              className="absolute bottom-6 left-[72%] max-w-xs rounded-xl border border-brand-lime/40 bg-brand-void/95 p-4 font-mono text-[11px] leading-relaxed text-brand-muted shadow-[0_0_40px_rgba(204,255,0,0.1)] backdrop-blur-md"
              style={{ opacity: cp7 }}
            >
              <p className="text-[10px] font-bold uppercase tracking-wider text-brand-lime">CP7 · the wall</p>
              <p className="mt-2 text-slate-200">
                Heart rate drift at 12%. Hold current pace to finish sub-30h.
              </p>
            </motion.div>
          </div>

          <p className="mt-4 font-mono text-[10px] text-brand-muted">Scroll horizontally →</p>
        </div>
      </div>
    </section>
  )
}
