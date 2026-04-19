import { Helmet } from "react-helmet-async"
import { siteOrigin } from "./siteOrigin"

const TITLE = "Connect Strava — Strava AI Coach"
const DESCRIPTION =
  "Link your Strava account to unlock AI debriefs, training load (CTL/ATL/TSB), ACWR, and race-aware coaching after every trail run."

export default function ConnectSeo() {
  const origin = siteOrigin()
  const canonical = origin ? `${origin}/connect` : undefined

  return (
    <Helmet htmlAttributes={{ lang: "en" }}>
      <title>{TITLE}</title>
      <meta content={DESCRIPTION} name="description" />
      {canonical ? <link href={canonical} rel="canonical" /> : null}
      <meta content={TITLE} property="og:title" />
      <meta content={DESCRIPTION} property="og:description" />
      {canonical ? <meta content={canonical} property="og:url" /> : null}
    </Helmet>
  )
}
