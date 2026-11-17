"use client"

import { Film, Grid2X2, ListChecks, Bookmark, ArrowUpRight } from "lucide-react"
import type { ReactNode } from "react"
import { hasTouch, type Match } from "@/lib/film"

export function FilmShell({
  match,
  section,
  player = "",
  reel = false,
  choose,
  children,
}: {
  match: Match | null
  section: "clips" | "review"
  player?: string
  reel?: boolean
  choose?: (name: string, reel: boolean) => void
  children: ReactNode
}) {
  const pending = Object.values(match?.appearances ?? {}).filter(
    (e) => e.status === "pending",
  ).length
  const names = [
    ...new Set(match?.clips.flatMap((c) => c.tags.map((t) => t.name))),
  ].sort()
  const portraits = Object.values(match?.appearances ?? {})
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a href="/" className="brand">
          <Film size={22} />
          <span>Volleyball</span>
        </a>
        <nav aria-label="Library" className="primary-nav">
          {choose ? (
            <button
              aria-current={!reel ? "page" : undefined}
              onClick={() => choose("", false)}
            >
              <Grid2X2 size={18} />
              All clips<span>{match?.clips.length}</span>
            </button>
          ) : (
            <a href="/">
              <Grid2X2 size={18} />
              All clips
            </a>
          )}
          {choose ? (
            <button
              aria-current={reel ? "page" : undefined}
              onClick={() => choose(player, true)}
            >
              <Bookmark size={18} />
              Reel<span>{match?.clips.filter((c) => c.keep).length}</span>
            </button>
          ) : (
            <a href="/?reel=1">
              <Bookmark size={18} />
              Reel
            </a>
          )}
          <a
            href={
              "/review" +
              (player ? "?player=" + encodeURIComponent(player) : "")
            }
            aria-current={section === "review" ? "page" : undefined}
          >
            <ListChecks size={18} />
            Review matches
            {pending > 0 && <span className="nav-count">{pending}</span>}
          </a>
        </nav>
        <div className="roster-heading">Player touches</div>
        <nav aria-label="Players" className="player-nav">
          {names.map((name) => {
            const photo = portraits.find((e) => e.name === name)?.reference
            const count = match?.clips.filter((c) => hasTouch(c, name)).length
            const contents = (
              <>
                <span className="avatar">
                  {photo ? (
                    <img src={"/scan-crop/" + photo} alt="" loading="lazy" />
                  ) : (
                    name[0]
                  )}
                </span>
                <span>{name}</span>
                <small aria-label={count + " touch clips"}>{count}</small>
              </>
            )
            return choose ? (
              <button
                key={name}
                aria-current={player === name ? "true" : undefined}
                onClick={() => choose(name, false)}
              >
                {contents}
              </button>
            ) : (
              <a key={name} href={"/?player=" + encodeURIComponent(name)}>
                {contents}
              </a>
            )
          })}
        </nav>
        <div className="sidebar-footer">
          <a href="https://ishanshah.me" target="_blank" rel="noreferrer">
            A project by Ishan
            <ArrowUpRight size={13} />
          </a>
        </div>
      </aside>
      <div className="app-content">
        <div className="topbar">
          <span>Film room</span>
          <span className="topbar-divider">/</span>
          <span>{match?.title || "Opening match…"}</span>
          <span className="local-status">Local library</span>
        </div>
        {children}
      </div>
    </div>
  )
}
