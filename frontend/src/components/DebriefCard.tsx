import type { Debrief } from "../types"

interface DebriefCardProps {
  debrief: Debrief
}

const sections = [
  ["Load verdict", "load_verdict", "border-blue-500"],
  ["Technical insight", "technical_insight", "border-amber-500"],
  ["Next session", "next_session_action", "border-emerald-500"],
] as const

export default function DebriefCard({ debrief }: DebriefCardProps) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
      <h2 className="text-lg font-bold text-slate-950">Post-run debrief</h2>
      <div className="mt-5 space-y-4">
        {sections.map(([label, key, borderClass]) => (
          <DebriefSection
            key={key}
            borderClass={borderClass}
            label={label}
            text={debrief[key]}
          />
        ))}
      </div>
    </section>
  )
}

function DebriefSection(props: {
  borderClass: string
  label: string
  text: string
}) {
  return (
    <article className={`border-l-4 pl-4 ${props.borderClass}`}>
      <h3 className="text-xs font-semibold uppercase text-slate-500">{props.label}</h3>
      <p className="mt-1 text-sm leading-6 text-slate-800">{props.text}</p>
    </article>
  )
}
