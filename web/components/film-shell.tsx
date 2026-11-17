"use client"

import {
  Film,
  Grid2X2,
  ListChecks,
  Bookmark,
  PanelLeft,
  Users,
  X,
} from "lucide-react"
import { useRef, useState, type ReactNode } from "react"
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
  const [collapsed, setCollapsed] = useState(false)
  const drawer = useRef<HTMLDialogElement>(null)
  const pending = Object.values(match?.appearances ?? {}).filter(
    (e) => e.status === "pending",
  ).length
  const names = [
    ...new Set(match?.clips.flatMap((c) => c.tags.map((t) => t.name))),
  ].sort()
  const items = [
    {
      label: "All clips",
      icon: Grid2X2,
      href: "/",
      active: section === "clips" && !player && !reel,
      action: () => choose?.("", false),
    },
    {
      label: "Reel",
      icon: Bookmark,
      href: "/?reel=1",
      active: section === "clips" && reel,
      action: () => choose?.(player, true),
    },
    {
      label: "Review players",
      icon: ListChecks,
      href: "/review" + (player ? "?player=" + encodeURIComponent(player) : ""),
      active: section === "review",
      count: pending,
    },
  ]
  function select(name: string) {
    choose?.(name, false)
    drawer.current?.close()
  }
  function navigation() {
    return (
      <>
        <nav aria-label="Library" className="primary-nav">
          {items.map(({ label, icon: Icon, href, active, action, count }) => {
            const contents = (
              <>
                <Icon size={16} />
                <span className="nav-label">{label}</span>
                {!!count && <span className="nav-count">{count}</span>}
              </>
            )
            return action && choose ? (
              <button
                key={label}
                title={label}
                aria-label={label}
                aria-current={active ? "page" : undefined}
                onClick={() => {
                  action()
                  drawer.current?.close()
                }}
              >
                {contents}
              </button>
            ) : (
              <a
                key={label}
                href={href}
                title={label}
                aria-label={label}
                aria-current={active ? "page" : undefined}
              >
                {contents}
              </a>
            )
          })}
        </nav>
        <button
          className="collapsed-players"
          title="Show players"
          aria-label="Show players"
          onClick={() => setCollapsed(false)}
        >
          <Users size={16} />
        </button>
        <div className="player-section">
          <div className="roster-heading">Player touches</div>
          <nav aria-label="Players" className="player-nav">
            {names.map((name) => {
              const count =
                match?.clips.filter((c) => hasTouch(c, name)).length ?? 0
              const contents = (
                <>
                  <span className="nav-label">{name}</span>
                  {count > 0 && (
                    <small aria-label={count + " touch clips"}>{count}</small>
                  )}
                </>
              )
              return choose ? (
                <button
                  key={name}
                  aria-current={
                    section === "clips" && !reel && player === name
                      ? "page"
                      : undefined
                  }
                  onClick={() => select(name)}
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
        </div>
        <div className="sidebar-footer">
          <Film size={16} />
          <div>
            <span>{match?.title || "Match footage"}</span>
            <small>{match ? "Match footage" : "Opening match…"}</small>
          </div>
        </div>
      </>
    )
  }
  return (
    <div className={"app-shell" + (collapsed ? " sidebar-collapsed" : "")}>
      <aside className="sidebar desktop-sidebar" aria-label="Main navigation">
        <div className="sidebar-header">
          <a href="/" className="brand" aria-label="Volleyball home">
            <Film size={22} />
            <span>Volleyball</span>
          </a>
          <button
            className="sidebar-toggle"
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!collapsed}
            onClick={() => setCollapsed(!collapsed)}
          >
            <PanelLeft size={18} />
          </button>
        </div>
        {navigation()}
      </aside>
      <div className="app-content">
        <header className="mobile-header">
          <button
            className="sidebar-toggle"
            aria-label="Open navigation"
            aria-haspopup="dialog"
            onClick={() => drawer.current?.showModal()}
          >
            <PanelLeft size={20} />
          </button>
          <a href="/">Volleyball</a>
          <span>
            {player ||
              (section === "review" ? "Review" : reel ? "Reel" : "All clips")}
          </span>
        </header>
        <dialog
          ref={drawer}
          className="mobile-navigation"
          aria-label="Navigation"
          onClick={(e) => {
            if (e.target === e.currentTarget) drawer.current?.close()
          }}
        >
          <div className="sidebar sidebar-mobile">
            <div className="sidebar-header">
              <a href="/" className="brand">
                <Film size={22} />
                <span>Volleyball</span>
              </a>
              <button
                className="sidebar-toggle"
                aria-label="Close navigation"
                onClick={() => drawer.current?.close()}
              >
                <X size={18} />
              </button>
            </div>
            {navigation()}
          </div>
        </dialog>
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
