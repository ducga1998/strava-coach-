import { SITE_AUTHOR } from "../../constants/author"

export default function AuthorStrip() {
  return (
    <section aria-label="Author" className="border-t border-white/[0.14] bg-brand-void px-4 py-8">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="font-mono text-[10px] font-semibold uppercase tracking-widest text-brand-muted">Author</p>
        <ul className="flex flex-col gap-3 font-mono text-sm sm:flex-row sm:gap-8">
          <li>
            <a
              className="text-brand-teal transition hover:text-brand-teal/90 hover:underline"
              href={SITE_AUTHOR.githubUrl}
              rel="noopener noreferrer"
              target="_blank"
            >
              GitHub — ducga1998
            </a>
          </li>
          <li>
            <a className="text-brand-muted transition hover:text-neutral-200" href={`mailto:${SITE_AUTHOR.email}`}>
              {SITE_AUTHOR.email}
            </a>
          </li>
        </ul>
      </div>
    </section>
  )
}
