export type Mark = { x: number; y: number; time: number }
export type Tag = Mark & {
  id?: string
  name: string
  source?: "automatic" | "reviewed"
  skill: string
  result: string
}
export type Detection = {
  review?: {
    verdict: "supported" | "rejected" | "unverified"
    evidence: string
    title: string
    model: string
    time: number | null
    skill: string
  }
  validation?: "supported" | "unverified" | "rejected"
  time: number
  score: number
  identityScore: number
  identityMargin: number
  uncertain: boolean
  status: "automatic" | "confirmed" | "dismissed"
  box: number[]
}
export type ScanStatus = {
  unit?: string
  updated?: number
  state: "idle" | "running" | "complete" | "needs_review" | "failed"
  phase?: string
  completed?: number
  total?: number
  added?: number
  detected?: number
}
export type Clip = {
  analysis?: {
    kind: "rally" | "serve" | "between_points" | "unclear"
    title: string
    description: string
    liveStart?: number
    liveEnd?: number
    complete?: boolean
    highlightScore?: number
    highlightReason?: string
    number?: number
    model: string
    status: "automatic" | "reviewed"
    claim?: string
    evidence?: string
    moments?: {
      time: number
      action: string
      player: string
      evidence: string
    }[]
  }
  detection?: Detection
  id: string
  start: number
  end: number
  keep: boolean
  tags: Tag[]
  note: string
  description?: string
}
export type CoachingNote = {
  id: string
  player: string
  kind: "strength" | "improvement"
  title: string
  observation: string
  action: string
  drill?: string
  evidence: { clipId: string; time: number }[]
}
export type Match = {
  coaching?: CoachingNote[]
  analysis?: {
    labeled: number
    rallies: number
    windows: number[]
    totalWindows: number
    model: string
  }
  appearances?: Record<string, Appearance>
  title: string
  match_id: string
  duration: number
  revision: number
  clips: Clip[]
  skills: string[]
  results: string[]
}
export type Draft = Tag & { id: string; clipId: string | null }
export type Suggestion = Mark & { id: string }

export function clock(seconds: number) {
  return (
    Math.floor(seconds / 60) +
    ":" +
    String(Math.floor(seconds % 60)).padStart(2, "0")
  )
}

export const touchSkills = [
  "Touch",
  "Serve",
  "Pass",
  "Set",
  "Attack",
  "Block",
  "Dig",
]

export function hasTouch(
  clip: Clip,
  player?: string,
  includeDismissed = false,
) {
  if (!includeDismissed && clip.detection?.status === "dismissed") return false
  return clip.tags.some(
    (t) => (!player || t.name === player) && touchSkills.includes(t.skill),
  )
}

export function touchSupported(clip: Clip) {
  return (
    !clip.detection ||
    clip.detection.status === "confirmed" ||
    (clip.detection.status !== "dismissed" &&
      clip.detection.validation === "supported")
  )
}

export function isRally(clip: Clip) {
  return (
    clip.analysis?.kind === "rally" && clip.analysis.liveStart !== undefined
  )
}

export function rallyDuration(clip: Clip) {
  return clip.analysis?.liveStart !== undefined &&
    clip.analysis.liveEnd !== undefined
    ? clip.analysis.liveEnd - clip.analysis.liveStart
    : clip.end - clip.start
}

export function clipName(clip: Clip) {
  if (
    clip.detection &&
    !touchSupported(clip) &&
    clip.note.endsWith(" · detected touch")
  )
    return "Possible touch · " + clip.tags.map((t) => t.name).join(", ")
  return (
    clip.note ||
    (clip.tags.length
      ? Array.from(new Set(clip.tags.map((t) => t.name))).join(" · ")
      : "Suggested clip")
  )
}

export function clipDescription(clip: Clip) {
  if (
    clip.detection &&
    !touchSupported(clip) &&
    clip.description?.startsWith("Ball contact detected at ")
  )
    return undefined
  return clip.description
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    path,
    body === undefined
      ? { cache: "no-store" }
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  )
  const data = await response.json()
  if (!response.ok)
    throw new Error(data.error || "Request failed. Please retry.")
  return data
}

export type Appearance = {
  id: string
  name: string
  time: number
  file: string
  reference: string
  box: [number, number, number, number]
  status: "pending" | "automatic" | "reviewed" | "rejected"
}

export function contactLabel(clip: Clip) {
  if (clip.detection?.status === "dismissed") return "Dismissed"
  if (clip.detection?.status === "confirmed") return "Touch confirmed"
  switch (clip.detection?.review?.verdict) {
    case "supported":
      return "GPU · likely touch"
    case "rejected":
      return "GPU · unlikely touch"
    case "unverified":
      return "GPU · uncertain"
    default:
      return "Unverified touch"
  }
}
