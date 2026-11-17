"use client"

import { useEffect, useRef, useState } from "react"
import {
  ArrowLeft,
  ArrowRight,
  Download,
  Grid2X2,
  List,
  Play,
  Plus,
  Search,
  X,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { NativeSelect } from "@/components/ui/native-select"
import { FilmShell } from "@/components/film-shell"
import { ClipLibrary } from "@/components/clip-library"
import { ClipDetails } from "@/components/clip-details"
import { TagEditor } from "@/components/tag-editor"
import { VideoPlayer } from "@/components/video-player"
import {
  api,
  clock,
  clipName,
  hasTouch,
  type Clip,
  type Draft,
  type Mark,
  type Match,
  type Tag,
} from "@/lib/film"

type Pending = Draft & { original?: Tag }
type Saved = { id: string; match: Match }
type ViewFilter = "all" | "untagged" | "touches" | "automatic" | "confirmed"

export default function FilmRoom() {
  const [match, setMatch] = useState<Match | null>(null)
  const [id, setId] = useState("")
  const [player, setPlayer] = useState("")
  const [query, setQuery] = useState("")
  const [reel, setReel] = useState(false)
  const [filter, setFilter] = useState<ViewFilter>("all")
  const [sort, setSort] = useState("time")
  const [layout, setLayout] = useState<"grid" | "list">("grid")
  const [limit, setLimit] = useState(24)
  const [draft, setDraft] = useState<Pending | null>(null)
  const [busy, setBusy] = useState(false)
  const [tagging, setTagging] = useState(false)
  const [fullMatch, setFullMatch] = useState(false)
  const [status, setStatus] = useState("")
  const [exporting, setExporting] = useState(false)
  const [download, setDownload] = useState("")
  const video = useRef<HTMLVideoElement>(null)
  const dialog = useRef<HTMLDialogElement>(null)
  const lock = useRef(false)
  const scope = useRef(0)
  const ready = useRef(false)
  const trigger = useRef<HTMLElement | null>(null)
  const autoplay = useRef(false)
  const seekTo = useRef<number | null>(null)
  const unsaved = useRef(false)
  const savedUrl = useRef("")
  const matchId = useRef("")
  unsaved.current = !!draft
  const active = match?.clips.find((c) => c.id === id)
  const names = [
    ...new Set(match?.clips.flatMap((c) => c.tags.map((t) => t.name))),
  ].sort()

  useEffect(() => {
    function restore() {
      if (unsaved.current) {
        if (!confirm("Discard this unsaved tag?")) {
          history.pushState(null, "", savedUrl.current)
          return
        }
        setDraft(null)
        try {
          sessionStorage.removeItem("volleyball-tag/" + matchId.current)
        } catch {}
      }
      const params = new URLSearchParams(location.search)
      setPlayer(params.get("player") || "")
      setReel(params.get("reel") === "1")
      setQuery(params.get("q") || "")
      setFilter(
        (["all", "untagged", "touches", "automatic", "confirmed"].includes(
          params.get("filter") || "",
        )
          ? params.get("filter")
          : "all") as ViewFilter,
      )
      setSort(
        ["time", "latest", "duration"].includes(params.get("sort") || "")
          ? params.get("sort")!
          : "time",
      )
      setLayout(params.get("layout") === "list" ? "list" : "grid")
      setId(location.hash.slice(1))
    }
    let alive = true
    api<Match>("/match")
      .then((data) => {
        if (!alive) return
        setMatch(data)
        matchId.current = data.match_id
        restore()
        try {
          const saved: Pending | null = JSON.parse(
            sessionStorage.getItem("volleyball-tag/" + data.match_id) || "null",
          )
          if (saved) {
            setDraft(saved)
            const target =
              data.clips.find((c) => c.id === saved.clipId) || data.clips[0]
            setId(target.id)
            seekTo.current = saved.time
            history.replaceState(
              null,
              "",
              location.pathname + location.search + "#" + target.id,
            )
          }
        } catch {}
        ready.current = true
      })
      .catch((e) => setStatus(e.message))
    function guardUnload(e: BeforeUnloadEvent) {
      if (unsaved.current) {
        e.preventDefault()
        e.returnValue = ""
      }
    }
    window.addEventListener("beforeunload", guardUnload)
    window.addEventListener("popstate", restore)
    return () => {
      alive = false
      window.removeEventListener("popstate", restore)
      window.removeEventListener("beforeunload", guardUnload)
    }
  }, [])

  useEffect(() => {
    if (!ready.current) return
    const params = new URLSearchParams()
    if (player) params.set("player", player)
    if (reel) params.set("reel", "1")
    if (query) params.set("q", query)
    if (filter !== "all") params.set("filter", filter)
    if (sort !== "time") params.set("sort", sort)
    if (layout !== "grid") params.set("layout", layout)
    const search = params.toString()
    history.replaceState(
      null,
      "",
      "/" + (search ? "?" + search : "") + (id ? "#" + id : ""),
    )
    savedUrl.current = location.pathname + location.search + location.hash
  }, [player, reel, query, filter, sort, layout, id])

  useEffect(() => {
    const modal = dialog.current
    if (active && modal && !modal.open) modal.showModal()
    if (!active && modal?.open) modal.close()
    if (!active) return
    const v = video.current
    if (!v) return
    function position() {
      if (!v || !active) return
      v.currentTime = seekTo.current ?? active.start
      seekTo.current = null
      if (autoplay.current) {
        autoplay.current = false
        void v.play().catch(() => {})
      }
    }
    if (v.readyState >= 1) position()
    else v.addEventListener("loadedmetadata", position, { once: true })
    return () => v.removeEventListener("loadedmetadata", position)
  }, [active?.id])

  const scoped =
    match?.clips.filter(
      (c) => (!player || hasTouch(c, player)) && (!reel || c.keep),
    ) ?? []
  const filtered = scoped
    .filter((c) => {
      const selectedTags = player
        ? c.tags.filter((t) => t.name === player)
        : c.tags
      const passes =
        filter === "untagged"
          ? !c.tags.length
          : filter === "touches"
            ? selectedTags.some((t) => t.skill !== "Appearance")
            : filter === "automatic"
              ? selectedTags.some((t) => t.source === "automatic")
              : filter === "confirmed"
                ? selectedTags.some((t) => t.source !== "automatic")
                : true
      const text = [
        c.note,
        c.description,
        clock(c.start),
        ...c.tags.flatMap((t) => [t.name, t.skill, t.result]),
      ]
        .join(" ")
        .toLowerCase()
      return passes && text.includes(query.toLowerCase().trim())
    })
    .sort((a, b) =>
      sort === "latest"
        ? b.start - a.start
        : sort === "duration"
          ? b.end - b.start - (a.end - a.start)
          : a.start - b.start,
    )
  const index = filtered.findIndex((c) => c.id === id)
  const kept =
    match?.clips.filter((c) => c.keep && (!player || hasTouch(c, player))) ?? []

  function remember(value: Pending | null) {
    setDraft(value)
    try {
      const key = "volleyball-tag/" + match!.match_id
      if (value) sessionStorage.setItem(key, JSON.stringify(value))
      else sessionStorage.removeItem(key)
    } catch {}
  }
  function choose(c: Clip, play = true) {
    if (draft || busy) return
    if (!id) trigger.current = document.activeElement as HTMLElement
    autoplay.current = play
    seekTo.current = c.start
    if (id === c.id && video.current) {
      video.current.currentTime = c.start
      if (play) void video.current.play().catch(() => {})
    }
    setTagging(false)
    setId(c.id)
    setStatus("")
    history.pushState(
      null,
      "",
      location.pathname + location.search + "#" + c.id,
    )
  }
  function close() {
    if (busy) return
    if (draft && !confirm("Discard this unsaved tag?")) return
    remember(null)
    video.current?.pause()
    setTagging(false)
    setId("")
    dialog.current?.close()
    history.replaceState(null, "", location.pathname + location.search)
    trigger.current?.focus()
  }
  function seek(time: number) {
    if (video.current) {
      video.current.pause()
      video.current.currentTime = time
    }
  }
  function pin(mark: Mark) {
    if (!match || busy) return
    if (draft) {
      remember({ ...draft, ...mark })
      return
    }
    const covers = (c: Clip) => c.start <= mark.time && c.end >= mark.time
    const target = active && covers(active) ? active : match.clips.find(covers)
    remember({
      ...mark,
      id: crypto.randomUUID(),
      clipId: target?.id ?? null,
      name: player,
      skill: "",
      result: "Ungraded",
    })
    setTagging(false)
  }
  async function persist(c: Clip, follow = false) {
    if (!match || lock.current) return false
    lock.current = true
    setBusy(true)
    try {
      const result = await api<Saved>("/save", {
        ...c,
        revision: match.revision,
      })
      setMatch(result.match)
      setDownload("")
      if (follow) {
        setId(result.id)
        seekTo.current = c.start
      }
      setStatus("Saved")
      return true
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Could not save. Try again.")
      return false
    } finally {
      lock.current = false
      setBusy(false)
    }
  }
  async function saveTag() {
    if (!match || !draft || lock.current) return
    const { clipId, original, ...tag } = draft
    tag.name =
      names.find((n) => n.toLowerCase() === tag.name.trim().toLowerCase()) ||
      tag.name.trim()
    lock.current = true
    setBusy(true)
    try {
      let result: Saved
      if (original) {
        const clip = match.clips.find((c) => c.id === clipId)
        if (!clip) throw Error("The clip changed. Refresh before editing.")
        const position = clip.tags.findIndex(
          (t) => JSON.stringify(t) === JSON.stringify(original),
        )
        if (position < 0) throw Error("The tag changed. Cancel and reopen it.")
        if (tag.source === "automatic") tag.source = "reviewed"
        result = await api<Saved>("/save", {
          ...clip,
          revision: match.revision,
          tags: clip.tags.map((t, i) => (i === position ? tag : t)),
        })
      } else result = await api<Saved>("/tag", { clipId, tag })
      setMatch(result.match)
      setId(result.id)
      setDownload("")
      remember(null)
      setTagging(false)
      setStatus("Saved tag for " + tag.name)
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Could not save tag.")
    } finally {
      lock.current = false
      setBusy(false)
    }
  }
  function setScope(name: string, onlyReel: boolean) {
    scope.current++
    setPlayer(name)
    setReel(onlyReel)
    setQuery("")
    setFilter("all")
    setLimit(24)
    setDownload("")
    setExporting(false)
    setStatus("")
  }
  function reset() {
    setScope("", false)
  }
  async function render() {
    const token = scope.current
    setExporting(true)
    setStatus("Rendering your reel from the original footage…")
    try {
      const data = await api<{ url: string }>("/export", { player })
      if (token === scope.current) {
        setDownload(data.url)
        setStatus("Reel ready to download")
      }
    } catch (e) {
      if (token === scope.current)
        setStatus(e instanceof Error ? e.message : "Could not export reel.")
    } finally {
      if (token === scope.current) setExporting(false)
    }
  }
  const unlabeled = scoped.filter((c) => !c.tags.length).length
  return (
    <FilmShell
      match={match}
      section="clips"
      player={player}
      reel={reel}
      choose={setScope}
    >
      <main className="library-page">
        <div className="page-heading">
          <div>
            <p className="eyebrow">{match?.title || "Match library"}</p>
            <h1>
              {player
                ? player + (reel ? "’s reel" : "’s clips")
                : reel
                  ? "Your reel"
                  : "Match clips"}
            </h1>
            <p className="subtitle">
              {match
                ? scoped.length +
                  (player ? " touch clips · " : " clips · ") +
                  clock(Math.round(match.duration)) +
                  " recording"
                : "Loading your clips…"}
            </p>
          </div>
          <div className="heading-actions">
            <Button
              variant="outline"
              disabled={!filtered.length}
              onClick={() => choose(filtered[0])}
            >
              <Play size={16} />
              Watch clips
            </Button>
            <Button disabled={exporting || !kept.length} onClick={render}>
              <Download size={16} />
              {exporting ? "Exporting…" : "Export reel"}
              <span className="button-count">{kept.length}</span>
            </Button>
            {download && (
              <a className="download" href={download} download>
                Download MP4
              </a>
            )}
          </div>
        </div>
        {player && (
          <p className="scope-note">
            Clips with a labeled touch by {player}. Appearance matches stay in{" "}
            <a href={"/review?player=" + encodeURIComponent(player)}>
              player review
            </a>
            .
          </p>
        )}
        <div className="library-toolbar">
          <label className="search-field">
            <Search size={17} />
            <Input
              aria-label="Search clips"
              placeholder="Search players, touches, or a time…"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setLimit(24)
              }}
            />
          </label>
          <div className="toolbar-options">
            <NativeSelect
              aria-label="Label status"
              value={filter}
              onChange={(e) => {
                setFilter(e.target.value as ViewFilter)
                setLimit(24)
              }}
            >
              <option value="all">All labels</option>
              <option value="untagged">No player tags ({unlabeled})</option>
              <option value="touches">Touch labeled</option>
              <option value="automatic">Auto-tagged</option>
              <option value="confirmed">Player confirmed</option>
            </NativeSelect>
            <NativeSelect
              aria-label="Sort clips"
              value={sort}
              onChange={(e) => setSort(e.target.value)}
            >
              <option value="time">Match order</option>
              <option value="latest">Latest first</option>
              <option value="duration">Longest first</option>
            </NativeSelect>
            <div className="view-switch" role="group" aria-label="Clip layout">
              <button
                aria-label="Grid view"
                aria-pressed={layout === "grid"}
                onClick={() => setLayout("grid")}
              >
                <Grid2X2 size={17} />
              </button>
              <button
                aria-label="List view"
                aria-pressed={layout === "list"}
                onClick={() => setLayout("list")}
              >
                <List size={18} />
              </button>
            </div>
          </div>
        </div>
        <div className="results-bar">
          <p>
            {filtered.length} {filtered.length === 1 ? "clip" : "clips"}
            {filter !== "all" || query ? " found" : ""}
          </p>
          <p className="coverage">
            {scoped.filter((c) => c.tags.length).length} with player tags ·{" "}
            {
              scoped.filter((c) => c.tags.some((t) => t.skill !== "Appearance"))
                .length
            }{" "}
            with touches
          </p>
        </div>
        {!active && status && (
          <p className="notice" role="status">
            {status}
          </p>
        )}
        {match && (
          <ClipLibrary
            clips={filtered.slice(0, limit)}
            player={player}
            layout={layout}
            choose={choose}
            busy={busy}
            keep={(c) => void persist({ ...c, keep: !c.keep })}
            reset={reset}
          />
        )}
        {filtered.length > limit && (
          <div className="load-more">
            <Button variant="outline" onClick={() => setLimit((n) => n + 24)}>
              Show more clips
            </Button>
            <p>
              Showing {Math.min(limit, filtered.length)} of {filtered.length}
            </p>
          </div>
        )}
      </main>
      <dialog
        ref={dialog}
        className="clip-dialog"
        aria-labelledby="clip-title"
        onCancel={(e) => {
          e.preventDefault()
          close()
        }}
        onClick={(e) => {
          if (e.target === e.currentTarget) close()
        }}
      >
        {active && (
          <div className="viewer-inner">
            <div className="viewer-header">
              <div>
                <p className="eyebrow">
                  {clock(active.start)} – {clock(active.end)}
                </p>
                <h2 id="clip-title">{clipName(active)}</h2>
              </div>
              <div className="buttons">
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Previous clip"
                  disabled={busy || !!draft || index <= 0}
                  onClick={() => choose(filtered[index - 1])}
                >
                  <ArrowLeft />
                </Button>
                <span className="viewer-position">
                  {index >= 0
                    ? index + 1 + " / " + filtered.length
                    : "Saved clip"}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Next clip"
                  disabled={
                    busy || !!draft || index < 0 || index >= filtered.length - 1
                  }
                  onClick={() => choose(filtered[index + 1])}
                >
                  <ArrowRight />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Close clip"
                  disabled={busy}
                  onClick={close}
                >
                  <X />
                </Button>
              </div>
            </div>
            <div className="viewer-body">
              <div className="viewer-media">
                <VideoPlayer
                  video={video}
                  clip={active}
                  draft={draft}
                  busy={busy}
                  onMark={pin}
                  tagging={tagging}
                  setTagging={setTagging}
                  fullMatch={fullMatch}
                  setFullMatch={setFullMatch}
                />
                {draft && (
                  <TagEditor
                    draft={draft}
                    match={match!}
                    names={names}
                    busy={busy}
                    change={remember}
                    cancel={() => {
                      remember(null)
                      setTagging(false)
                    }}
                    save={saveTag}
                  />
                )}
                {status && (
                  <p className="notice" role="status">
                    {status}
                  </p>
                )}
              </div>
              <div className="viewer-details">
                <ClipDetails
                  key={active.id}
                  clip={active}
                  busy={busy || !!draft}
                  playhead={() => video.current?.currentTime ?? 0}
                  seek={seek}
                  save={persist}
                  editTag={(t) => {
                    seek(t.time)
                    remember({
                      ...t,
                      id: t.id || crypto.randomUUID(),
                      clipId: active.id,
                      original: t,
                    })
                  }}
                />
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={busy || !!draft}
                  onClick={async () => {
                    const time = video.current?.currentTime ?? active.start
                    video.current?.pause()
                    await persist(
                      {
                        id: "new",
                        start: Math.max(0, time - 4),
                        end: Math.min(match!.duration, time + 6),
                        keep: false,
                        tags: [],
                        note: "",
                      },
                      true,
                    )
                  }}
                >
                  <Plus />
                  New clip at playhead
                </Button>
              </div>
            </div>
          </div>
        )}
      </dialog>
    </FilmShell>
  )
}
