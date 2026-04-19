import { Helmet } from "react-helmet-async"
import { SITE_AUTHOR } from "../constants/author"
import { siteOrigin } from "./siteOrigin"

const TITLE = "Strava AI Coach — AI trail & ultra running debriefs"
const DESCRIPTION =
  "Stop tracking. Start diagnosing. AI coaching for trail and ultra runners: training load, ACWR, hallucination-aware debriefs, and VMM-style vert debt — built for Southeast Asia mountains."

export default function HomeSeo() {
  const origin = siteOrigin()
  const canonical = origin ? `${origin}/` : undefined

  return (
    <Helmet htmlAttributes={{ lang: "en" }}>
      <title>{TITLE}</title>
      <meta content={DESCRIPTION} name="description" />
      <meta
        content="Strava, trail running, ultra running, VMM, training load, ACWR, AI coach, debrief, Southeast Asia"
        name="keywords"
      />
      {canonical ? <link href={canonical} rel="canonical" /> : null}

      <meta content="website" property="og:type" />
      <meta content={TITLE} property="og:title" />
      <meta content={DESCRIPTION} property="og:description" />
      {canonical ? <meta content={canonical} property="og:url" /> : null}
      <meta content="en_US" property="og:locale" />

      <meta content="summary" name="twitter:card" />
      <meta content={TITLE} name="twitter:title" />
      <meta content={DESCRIPTION} name="twitter:description" />
      <meta content={SITE_AUTHOR.githubUrl} name="author" />

      <script type="application/ld+json">
        {JSON.stringify({
          "@context": "https://schema.org",
          "@type": "SoftwareApplication",
          name: "Strava AI Coach",
          applicationCategory: "HealthApplication",
          description: DESCRIPTION,
          offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
          author: {
            "@type": "Person",
            name: "ducga1998",
            url: SITE_AUTHOR.githubUrl,
            email: SITE_AUTHOR.email,
            sameAs: [SITE_AUTHOR.githubUrl],
          },
          ...(canonical ? { url: canonical } : {}),
        })}
      </script>
    </Helmet>
  )
}
