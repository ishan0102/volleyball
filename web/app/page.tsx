"use client"

import { useEffect, useRef, useState } from "react"
import { Film, Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { VideoPlayer } from "@/components/video-player"
import { ClipLibrary } from "@/components/clip-library"
import { ClipDetails } from "@/components/clip-details"
import { TagEditor } from "@/components/tag-editor"
import {
  api,
  clock,
  type Clip,
  type Draft,
  type Mark,
  type Match,
  type Suggestion,
  type Tag,
} from "@/lib/film"

type Pending = Draft & { original?: Tag }
type Saved = { id: string; match: Match }
function message(e: unknown) {
  return e instanceof Error ? e.message : "Something went wrong. Try again."
}

export default function FilmRoom() {
  const [match, setMatch] = useState<Match | null>(null),
    [id, setId] = useState("")
  const [draft, setDraft] = useState<Pending | null>(null),
    [busy, setBusy] = useState(false)
  const [player, setPlayer] = useState(""),
    [hits, setHits] = useState<Suggestion[]>([])
  const [searching, setSearching] = useState(false),
    [exporting, setExporting] = useState(false),
    [download, setDownload] = useState("")
  const [status, setStatus] = useState(""),
    [initialTime, setInitialTime] = useState(0)
  const video = useRef<HTMLVideoElement>(null),
    lock = useRef(false),
    scope = useRef(0)
  const active = match?.clips.find((c) => c.id === id) ?? match?.clips[0]
  const names = Array.from(
    new Set(match?.clips.flatMap((c) => c.tags.map((t) => t.name))),
  ).sort()
  useEffect(() => {
    let mounted = true
    api<Match>("/match")
      .then((data) => {
        if (!mounted) return
        let pending: Pending | null = null
        try {
          pending = JSON.parse(
            sessionStorage.getItem("volleyball-tag/" + data.match_id) || "null",
          )
        } catch {}
        const target =
          data.clips.find(
            (c) => c.id === (pending?.clipId || location.hash.slice(1)),
          ) ||
          data.clips.find((c) => c.keep) ||
          data.clips[0]
        setMatch(data)
        setId(target.id)
        setInitialTime(pending?.time ?? target.start)
        setDraft(pending)
      })
      .catch((e) => setStatus(message(e)))
    return () => {
      mounted = false
    }
  }, [])
  useEffect(() => {
    const v = video.current
    if (!v) return
    const restore = () => {
      v.currentTime = initialTime
    }
    if (v.readyState >= 1) restore()
    else v.addEventListener("loadedmetadata", restore, { once: true })
    return () => v.removeEventListener("loadedmetadata", restore)
  }, [initialTime, !!match])
  function remember(value: Pending | null) {
    setDraft(value)
    try {
      const key = "volleyball-tag/" + match!.match_id
      if (value) sessionStorage.setItem(key, JSON.stringify(value))
      else sessionStorage.removeItem(key)
    } catch {}
  }
  function seek(t: number) {
    if (video.current) {
      video.current.pause()
      video.current.currentTime = t
    }
  }
  function select(c: Clip) {
    setId(c.id)
    history.replaceState(null, "", "#" + c.id)
    seek(c.start)
    setStatus("")
  }
  function pin(mark: Mark) {
    if (!match || !active || busy) return
    if (draft) {
      remember({ ...draft, ...mark })
      return
    }
    const covers = (c: Clip) => c.start <= mark.time && mark.time <= c.end
    const target = covers(active) ? active : match.clips.find(covers)
    if (target) setId(target.id)
    remember({
      ...mark,
      id: crypto.randomUUID(),
      clipId: target?.id ?? null,
      name: player,
      skill: "Appearance",
      result: "Ungraded",
    })
    setStatus(
      target ? "" : "Saving this tag will create a clip around this moment.",
    )
  }
  function accepted(response: Saved) {
    setMatch(response.match)
    setId(response.id)
    setDownload("")
    history.replaceState(null, "", "#" + response.id)
  }
  async function persist(c: Clip) {
    if (lock.current || !match) return false
    lock.current = true
    setBusy(true)
    try {
      accepted(await api<Saved>("/save", { ...c, revision: match.revision }))
      setStatus("Clip saved")
      return true
    } catch (e) {
      setStatus(message(e))
      return false
    } finally {
      setBusy(false)
      lock.current = false
    }
  }
  async function saveTag() {
    if (!draft || !match || lock.current) return
    const { clipId, original, ...tag } = draft
    const existing = names.find(
      (n) => n.toLowerCase() === tag.name.trim().toLowerCase(),
    )
    tag.name = existing || tag.name.trim()
    lock.current = true
    setBusy(true)
    try {
      if (original) {
        const c = match.clips.find((c) => c.id === clipId)!
        const index = c.tags.findIndex(
          (t) => JSON.stringify(t) === JSON.stringify(original),
        )
        if (index < 0)
          throw Error("This tag changed. Cancel and reopen it to edit.")
        if (tag.source === "automatic") tag.source = "reviewed"
        const tags = c.tags.map((t, i) => (i === index ? tag : t))
        accepted(
          await api<Saved>("/save", { ...c, tags, revision: match.revision }),
        )
      } else {
        accepted(await api<Saved>("/tag", { clipId, tag }))
      }
      remember(null)
      setHits((h) => h.filter((s) => s.id !== clipId))
      setStatus("Saved tag for " + tag.name)
    } catch (e) {
      setStatus(message(e))
    } finally {
      lock.current = false
      setBusy(false)
    }
  }
  function filter(name: string) {
    scope.current++
    setPlayer(name)
    setHits([])
    setSearching(false)
    setExporting(false)
    setDownload("")
    setStatus("")
    const c = match?.clips.find(
      (c) => !name || c.tags.some((t) => t.name === name),
    )
    if (c) select(c)
  }
  async function appearances() {
    const token = scope.current
    setSearching(true)
    setStatus("Comparing player appearances…")
    try {
      const data = await api<{ hits: Suggestion[] }>("/suggest", { player })
      if (token === scope.current) {
        setHits(data.hits)
        setStatus(
          data.hits.length
            ? "Choose a suggested time to review the player."
            : "No similar appearances found.",
        )
      }
    } catch (e) {
      if (token === scope.current) setStatus(message(e))
    } finally {
      if (token === scope.current) setSearching(false)
    }
  }
  async function render() {
    const token = scope.current
    setExporting(true)
    setStatus("Rendering from the original…")
    try {
      const data = await api<{ url: string }>("/export", { player })
      if (token === scope.current) {
        setDownload(data.url)
        setStatus("Reel ready to download")
      }
    } catch (e) {
      if (token === scope.current) setStatus(message(e))
    } finally {
      if (token === scope.current) setExporting(false)
    }
  }
  if (!match || !active)
    return (
      <main>
        <h1>Film room</h1>
        <p role="status">{status || "Opening match…"}</p>
      </main>
    )
  return (
    <>
      <header>
        <div>
          <Film size={18} />
          <strong>Volleyball</strong>
          <span>/</span>Film room
        </div>
        {match.appearances && (
          <a className="download" href="/review">
            Review player matches
          </a>
        )}
        <span className="time">{clock(match.duration)} match</span>
      </header>
      <main>
        <div className="page-title">
          <h1>{match.title}</h1>
          <Button
            variant="outline"
            size="sm"
            disabled={busy || !!draft}
            onClick={async () => {
              const t = video.current?.currentTime || 0
              video.current?.pause()
              await persist({
                id: "new",
                start: Math.max(0, t - 4),
                end: Math.min(match.duration, t + 6),
                keep: false,
                note: "",
                tags: [],
              })
            }}
          >
            <Plus />
            New clip here
          </Button>
        </div>
        <div className="layout">
          <div className="workspace">
            <VideoPlayer
              video={video}
              duration={match.duration}
              clip={active}
              draft={draft}
              busy={busy}
              onMark={pin}
            />
            {draft && (
              <TagEditor
                draft={draft}
                match={match}
                names={names}
                busy={busy}
                change={remember}
                cancel={() => {
                  remember(null)
                  setStatus("")
                }}
                save={saveTag}
              />
            )}
            <p className="notice" role="status">
              {status}
            </p>
            <ClipDetails
              key={active.id}
              clip={active}
              busy={busy || !!draft}
              playhead={() => video.current?.currentTime || 0}
              seek={seek}
              save={persist}
              editTag={(tag) => {
                seek(tag.time)
                remember({
                  ...tag,
                  id: tag.id || crypto.randomUUID(),
                  clipId: active.id,
                  original: tag,
                })
              }}
            />
          </div>
          <ClipLibrary
            clips={match.clips}
            active={active.id}
            names={names}
            player={player}
            busy={busy || !!draft}
            choose={select}
            filter={filter}
            hits={hits}
            searching={searching}
            search={appearances}
            exporting={exporting}
            download={download}
            exportReel={render}
            inspect={(h) => {
              setId(h.id)
              seek(h.time)
              remember({
                id: crypto.randomUUID(),
                time: h.time,
                x: h.x,
                y: h.y,
                clipId: h.id,
                name: player,
                skill: "Appearance",
                result: "Ungraded",
              })
              setStatus("Check the pin and save if the player matches.")
            }}
          />
        </div>
      </main>
    </>
  )
}
