import { useReducedMotion } from "framer-motion"
import AppChromeHeader from "../components/layout/AppChromeHeader"
import { useDarkPageChrome } from "../hooks/useDarkPageChrome"
import AuthorStrip from "../components/landing/AuthorStrip"
import CursorFollower from "../components/landing/CursorFollower"
import FeatureBento from "../components/landing/FeatureBento"
import HeroParallax from "../components/landing/HeroParallax"
import ProblemSticky from "../components/landing/ProblemSticky"
import TerminalFooter from "../components/landing/TerminalFooter"
import VmmHorizontal from "../components/landing/VmmHorizontal"
import { useLenis } from "../hooks/useLenis"
import HomeSeo from "../seo/HomeSeo"

export default function Home() {
  const reduceMotion = useReducedMotion()
  useLenis(reduceMotion !== true)

  useDarkPageChrome()

  return (
    <div className="min-h-screen bg-[#050505] bg-brand-void font-sans text-neutral-50 antialiased">
      <HomeSeo />
      <CursorFollower />
      <AppChromeHeader />

      <main>
        <HeroParallax />
        <ProblemSticky />
        <FeatureBento />
        <VmmHorizontal />
      </main>
      <AuthorStrip />
      <TerminalFooter />
    </div>
  )
}
