import type { CSSProperties } from "react"

type Variant = "light" | "dark"

interface SkeletonBlockProps {
  className?: string
  variant?: Variant
  style?: CSSProperties
  rounded?: "sm" | "md" | "lg" | "xl" | "full"
}

export function SkeletonBlock({
  className = "",
  variant = "light",
  rounded = "md",
  style,
}: SkeletonBlockProps) {
  const base = "animate-pulse"
  const tone =
    variant === "dark" ? "bg-white/10" : "bg-slate-200/80"
  const radius = {
    sm: "rounded",
    md: "rounded-md",
    lg: "rounded-lg",
    xl: "rounded-xl",
    full: "rounded-full",
  }[rounded]
  return <div aria-hidden className={`${base} ${tone} ${radius} ${className}`} style={style} />
}

interface SkeletonLineProps {
  width?: string
  height?: string
  variant?: Variant
  className?: string
}

export function SkeletonLine({
  width = "100%",
  height = "0.75rem",
  variant = "light",
  className = "",
}: SkeletonLineProps) {
  return (
    <SkeletonBlock
      className={className}
      rounded="sm"
      style={{ width, height }}
      variant={variant}
    />
  )
}

export function SkeletonCard({
  variant = "light",
  className = "",
  children,
}: {
  variant?: Variant
  className?: string
  children?: React.ReactNode
}) {
  const surface =
    variant === "dark"
      ? "border border-white/[0.14] bg-brand-charcoal/70 shadow-[0_20px_60px_rgba(0,0,0,0.35)]"
      : "border border-slate-200 bg-white shadow-panel"
  return <div className={`rounded-lg ${surface} ${className}`}>{children}</div>
}
