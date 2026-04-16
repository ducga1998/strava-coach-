interface AcwrGaugeProps {
  acwr: number
}

const radius = 52
const stroke = 12
const circumference = 2 * Math.PI * radius

export default function AcwrGauge({ acwr }: AcwrGaugeProps) {
  const zone = getAcwrZone(acwr)
  const offset = circumference * (1 - getGaugePercent(acwr))
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold uppercase text-slate-500">ACWR</h2>
          <p className="mt-1 text-4xl font-bold text-slate-950">{acwr.toFixed(2)}</p>
          <p className={`mt-2 text-sm font-semibold ${zone.textClass}`}>{zone.label}</p>
        </div>
        <GaugeCircle offset={offset} strokeClass={zone.strokeClass} />
      </div>
      <p className="mt-4 text-sm text-slate-600">{zone.guidance}</p>
    </section>
  )
}

function GaugeCircle(props: { offset: number; strokeClass: string }) {
  return (
    <svg viewBox="0 0 140 140" className="h-32 w-32 shrink-0" aria-hidden="true">
      <circle cx="70" cy="70" r={radius} fill="none" stroke="#e2e8f0" strokeWidth={stroke} />
      <circle
        cx="70"
        cy="70"
        r={radius}
        fill="none"
        stroke="currentColor"
        strokeDasharray={circumference}
        strokeDashoffset={props.offset}
        strokeLinecap="round"
        strokeWidth={stroke}
        className={`origin-center -rotate-90 ${props.strokeClass}`}
      />
    </svg>
  )
}

function getGaugePercent(acwr: number): number {
  return clamp((acwr - 0.5) / 1.3, 0.05, 1)
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function getAcwrZone(acwr: number) {
  if (acwr < 0.8) return zone("Undertraining", "text-blue-700", "text-blue-500", "Load is below chronic baseline.")
  if (acwr <= 1.3) return zone("Green zone", "text-emerald-700", "text-emerald-500", "Current load is inside the sustainable range.")
  if (acwr <= 1.5) return zone("Caution", "text-amber-700", "text-amber-500", "One hard week is acceptable; avoid stacking another.")
  return zone("Injury risk", "text-red-700", "text-red-500", "Consider deloading before adding more intensity.")
}

function zone(label: string, textClass: string, strokeClass: string, guidance: string) {
  return { label, textClass, strokeClass, guidance }
}
