import { ChangeEvent, useCallback, useEffect, useRef, useState } from 'react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
type Job = { id: string; filename: string; status: string; progress: number; created_at: string; error?: string; summary?: { frames_processed: number; tracks_seen: number; risk_assessed: boolean; risk_reason?: string; pose_available?: boolean; pose_detections?: number }; video_url?: string | null }
type Incident = { id: number; job_id: string; track_id: number; state: string; score: number | null; timestamp_seconds: number; created_at: string; class_name?: string | null }

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, init)
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `Request failed (${response.status})`)
  return response.json()
}

export default function App() {
  const [health, setHealth] = useState<any>(null)
  const [jobs, setJobs] = useState<Job[]>([])
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [selected, setSelected] = useState<Job | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [incidentsLoaded, setIncidentsLoaded] = useState(false)
  const [soundEnabled, setSoundEnabled] = useState(false)
  const knownIncidents = useRef<Set<number> | null>(null)
  const audioContext = useRef<AudioContext | null>(null)

  const selectedId = selected?.id ?? null
  const refresh = useCallback(async () => {
    try {
      const [h, j, i] = await Promise.all([api<any>('/api/health'), api<Job[]>('/api/jobs'), api<Incident[]>('/api/incidents')])
      setHealth(h); setJobs(j); setIncidents(i)
      setIncidentsLoaded(true)
      if (selectedId) {
        const updated = await api<Job>(`/api/jobs/${selectedId}`)
        setSelected(current => current?.id === selectedId ? { ...current, ...updated } : current)
      }
      setError('')
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to connect to the monitoring service.') }
  }, [selectedId])

  useEffect(() => { void refresh(); const timer = window.setInterval(() => void refresh(), 2500); return () => window.clearInterval(timer) }, [refresh])
  useEffect(() => {
    if (!incidentsLoaded) return
    const next = new Set(incidents.map(item => item.id))
    if (knownIncidents.current && soundEnabled && incidents.some(item => !knownIncidents.current!.has(item.id))) playAlert()
    knownIncidents.current = next
  }, [incidents, soundEnabled, incidentsLoaded])

  function getAudioContext() {
    if (typeof AudioContext === 'undefined') return null
    audioContext.current ??= new AudioContext()
    return audioContext.current
  }

  async function playBuzzer() {
    const context = getAudioContext()
    if (!context) return
    await context.resume()
    // A repeated, two-tone square-wave buzzer. The gain is close to full browser
    // output; the operating system and device still control the actual volume.
    const startAt = context.currentTime + 0.03
    for (let i = 0; i < 6; i++) {
      const start = startAt + i * 0.43
      const end = start + 0.31
      for (const frequency of [720 + (i % 2) * 110, 960 - (i % 2) * 110]) {
        const tone = context.createOscillator()
        const volume = context.createGain()
        tone.type = 'square'
        tone.frequency.setValueAtTime(frequency, start)
        volume.gain.setValueAtTime(0.0001, start)
        volume.gain.exponentialRampToValueAtTime(0.42, start + 0.015)
        volume.gain.setValueAtTime(0.42, end - 0.025)
        volume.gain.exponentialRampToValueAtTime(0.0001, end)
        tone.connect(volume)
        volume.connect(context.destination)
        tone.start(start)
        tone.stop(end + 0.01)
      }
    }
  }

  function toggleSound() {
    const next = !soundEnabled
    setSoundEnabled(next)
    if (next) void getAudioContext()?.resume()
  }

  function playAlert() {
    if (audioContext.current?.state === 'running') void playBuzzer()
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setBusy(true); setError('')
    const form = new FormData(); form.append('file', file)
    try {
      const job = await api<Job>('/api/jobs', { method: 'POST', body: form })
      setSelected(job); await refresh()
    } catch (e) { setError(e instanceof Error ? e.message : 'Upload failed.') }
    finally { setBusy(false) }
  }

  return <main className="shell">
    <header className="top"><div className="brand"><span className="mark">◉</span><div><strong>POOLWATCH</strong><small>VIDEO SAFETY RESEARCH PROTOTYPE</small></div></div><div className="connection"><i className={health?.status === 'ok' ? 'dot online' : 'dot'} />{health?.status === 'ok' ? 'SERVICE CONNECTED' : 'SERVICE OFFLINE'}</div></header>
    {!selected && <section className="hero"><div><p className="eyebrow">MONITORING CONSOLE / LOCAL ANALYSIS</p><h1>Every second<br/><em>matters.</em></h1><p className="lead">Analyze pool footage with object detection and persistent person tracking.</p><label className={`upload ${busy ? 'disabled' : ''}`}><input type="file" accept="video/*,.mp4,.mov,.avi,.mkv,.webm" disabled={busy} onChange={upload}/><span>{busy ? 'UPLOADING…' : '＋  ANALYZE A VIDEO'}</span></label><span className="meta">MP4, MOV, AVI, MKV, WEBM · max 500 MB</span></div><div className="status-card"><div className="card-head"><span>SYSTEM STATUS</span><span className="pulse"/></div><div className="risk"><span className="risk-icon">!</span><div><strong>RISK UNASSESSED</strong><small>{health?.risk_model_available ? 'Temporal classifier is configured' : 'No validated temporal model is installed'}</small></div></div><div className="status-line"><span>Person tracker</span><b>DeepSORT</b></div><div className="status-line"><span>Live CCTV</span><b className="muted">NOT CONFIGURED</b></div><div className="status-line"><span>Pose estimation</span><b className="muted">{health?.pose_enabled ? 'ENABLED' : health?.pose_requested ? 'MODEL MISSING' : 'DISABLED'}</b></div><p className="note">Detection labels are not a validated drowning-risk score. Maintain continuous human supervision.</p></div></section>}
    {error && <div className="error" role="alert">{error}<button onClick={() => void refresh()}>Retry</button></div>}
    {selected ? <Monitor job={selected} incidents={incidents.filter(i => i.job_id === selected.id)} health={health} busy={busy} onUpload={upload} onViewAll={() => setSelected(null)} soundEnabled={soundEnabled} onToggleSound={toggleSound} onTestBuzzer={() => void playBuzzer()}/> : <section className="grid"><div className="panel"><div className="panel-title"><div><p className="eyebrow">ANALYSIS</p><h2>Videos & results</h2></div></div>
      {jobs.length === 0 ? <div className="empty"><span>▧</span><strong>No videos analyzed</strong><p>Upload a pool video to create your first analysis job.</p></div> : <div className="job-list">{jobs.map(job => <button className="job" key={job.id} aria-label={`${job.status === 'completed' ? 'View result for' : 'Open'} ${job.filename}`} onClick={() => void api<Job>(`/api/jobs/${job.id}`).then(setSelected).catch(e => setError(e.message))}><span className="file-icon">▶</span><span className="job-name"><b>{job.filename}</b><small>{new Date(job.created_at).toLocaleString()}</small></span><span className={`badge ${job.status}`}>{job.status === 'completed' ? 'VIEW RESULT' : job.status.toUpperCase()}</span><span className="arrow">›</span></button>)}</div>}
    </div><div className="panel incidents"><div className="panel-title"><div><p className="eyebrow">EVENT LOG</p><h2>Flagged incidents</h2></div><div className="event-tools"><button className={`sound-toggle ${soundEnabled ? 'active' : 'sound-off'}`} aria-pressed={soundEnabled} title={soundEnabled ? 'Alert tones are armed' : 'Click to arm browser alert tones'} onClick={toggleSound}>ALARM {soundEnabled ? 'ON' : 'OFF · ARM'}</button><button className="sound-test" onClick={() => void playBuzzer()}>TEST BUZZER</button><span className="count">{incidents.length}</span></div></div>{incidents.length === 0 ? <div className="empty compact"><span>◷</span><strong>No detection warnings yet</strong><p>Drowning-class detections raise a warning. Temporal risk stays unassessed until a validated risk model is installed.</p></div> : <div className="incident-list">{incidents.slice(0, 8).map(i => <div className="incident" key={i.id}><span className={i.state === 'EMERGENCY' ? 'incident-icon emergency' : 'incident-icon'}>!</span><div><b>{i.class_name || i.state} · {i.state} · Track {i.track_id}</b><small>Job {i.job_id.slice(0, 8)} · {i.timestamp_seconds.toFixed(1)} sec</small></div><time>{new Date(i.created_at).toLocaleDateString()}</time></div>)}</div>}</div></section>}
    <footer><span>POOLWATCH <i/> RESEARCH BUILD 0.1</span><p>Safety-support prototype. Never replaces lifeguards, emergency response, or continuous supervision.</p></footer>
  </main>
}

function Monitor({ job, incidents, health, busy, onUpload, onViewAll, soundEnabled, onToggleSound, onTestBuzzer }: {
  job: Job; incidents: Incident[]; health: any; busy: boolean;
  onUpload: (event: ChangeEvent<HTMLInputElement>) => void; onViewAll: () => void;
  soundEnabled: boolean; onToggleSound: () => void; onTestBuzzer: () => void;
}) {
  const processing = job.status === 'processing'
  const queued = job.status === 'queued'
  const complete = job.status === 'completed'
  return <section className="monitor">
    <div className="monitor-title"><div><p className="eyebrow">VIDEO MONITOR / TRACKING VIEW</p><h1>{processing ? 'Live analysis' : queued ? 'Analysis queued' : complete ? 'Analysis result' : 'Analysis failed'}</h1><p className="lead monitor-filename">{job.filename}</p></div><div className="monitor-actions"><label className={`upload upload-small ${busy ? 'disabled' : ''}`}><input type="file" accept="video/*,.mp4,.mov,.avi,.mkv,.webm" disabled={busy} onChange={onUpload}/><span>{busy ? 'UPLOADING…' : '＋ NEW VIDEO'}</span></label><button className="text-button" onClick={onViewAll}>ALL VIDEOS</button></div></div>
    {(processing || queued) && <div className="monitor-progress"><div className="progress-label"><span>{queued ? 'Waiting for the video worker to start' : 'Analyzing frames · live tracking updates as each frame is processed'}</span><b>{Math.round(job.progress || 0)}%</b></div><div className="progress"><i style={{ width: `${job.progress || 0}%` }}/></div></div>}
    <div className="monitor-layout"><div className="monitor-main">
      {processing || queued ? <LivePreview jobId={job.id} active={processing}/> : complete ? <video className="monitor-video" controls src={`${API}/api/jobs/${job.id}/video`}/> : <div className="failure"><b>Analysis could not finish</b><p>{job.error}</p><p className="subtle">Check that trained YOLO weights are installed and configured.</p></div>}
      <div className="metrics monitor-metrics"><div><small>{complete ? 'FRAMES' : 'PROGRESS'}</small><b>{complete ? job.summary?.frames_processed ?? '—' : `${Math.round(job.progress || 0)}%`}</b></div><div><small>{complete ? 'TRACKS SEEN' : 'TRACKING'}</small><b>{complete ? job.summary?.tracks_seen ?? '—' : job.summary?.tracks_seen ?? 'ACTIVE'}</b></div><div><small>WARNINGS</small><b>{incidents.length}</b></div><div><small>POSE</small><b>{complete ? job.summary?.pose_available ? `${job.summary.pose_detections ?? 0}` : 'OFF' : health?.pose_enabled ? 'ON' : 'OFF'}</b></div></div>
      {complete && <p className="subtle">{job.summary?.risk_reason || 'Risk states require a validated temporal classifier.'}</p>}
    </div><aside className="monitor-side"><div className="panel monitor-status"><div className="panel-title"><div><p className="eyebrow">SYSTEM STATUS</p><h2>Analysis limits</h2></div></div><div className="status-line"><span>Temporal risk model</span><b className="muted">{health?.risk_model_available ? 'INSTALLED' : 'NOT INSTALLED'}</b></div><div className="status-line"><span>Pose estimation</span><b>{health?.pose_enabled ? 'ENABLED' : 'DISABLED'}</b></div><div className="status-line"><span>Live CCTV</span><b className="muted">NOT CONFIGURED</b></div><p className="note">Detector warnings are not validated risk scores. Keep a human supervisor watching the pool.</p></div>
      <div className="panel monitor-events"><div className="panel-title"><div><p className="eyebrow">THIS VIDEO</p><h2>Warnings</h2></div><div className="event-tools"><button className={`sound-toggle ${soundEnabled ? 'active' : 'sound-off'}`} aria-pressed={soundEnabled} title={soundEnabled ? 'Alert tones are armed' : 'Click to arm browser alert tones'} onClick={onToggleSound}>ALARM {soundEnabled ? 'ON' : 'OFF · ARM'}</button><button className="sound-test" onClick={onTestBuzzer}>TEST BUZZER</button><span className="count">{incidents.length}</span></div></div>{incidents.length === 0 ? <div className="empty compact"><strong>{processing ? 'Watching for detector warnings' : 'No warnings recorded'}</strong><p>Drowning-class detections will appear here. Risk remains unassessed.</p></div> : <div className="incident-list">{incidents.slice(0, 12).map(i => <div className="incident" key={i.id}><span className={i.state === 'EMERGENCY' ? 'incident-icon emergency' : 'incident-icon'}>!</span><div><b>{i.class_name || i.state} · {i.state}</b><small>Track {i.track_id} · {i.timestamp_seconds.toFixed(1)} sec</small></div></div>)}</div>}</div></aside></div>
  </section>
}

function LivePreview({ jobId, active }: { jobId: string; active: boolean }) {
  const [frameUrl, setFrameUrl] = useState('')
  const [frameTime, setFrameTime] = useState<number | null>(null)
  useEffect(() => {
    let mounted = true
    let currentUrl = ''
    let inFlight = false
    const fetchFrame = async () => {
      if (inFlight) return
      inFlight = true
      try {
        const response = await fetch(`${API}/api/jobs/${jobId}/preview`, { cache: 'no-store' })
        if (!response.ok) return
        const nextUrl = URL.createObjectURL(await response.blob())
        if (!mounted) { URL.revokeObjectURL(nextUrl); return }
        if (currentUrl) URL.revokeObjectURL(currentUrl)
        currentUrl = nextUrl
        setFrameUrl(nextUrl)
        setFrameTime(Date.now())
      } catch { /* The first analyzed frame may not be ready yet. */ }
      finally { inFlight = false }
    }
    void fetchFrame()
    const timer = active ? window.setInterval(() => void fetchFrame(), 400) : undefined
    return () => {
      mounted = false
      if (timer) window.clearInterval(timer)
      if (currentUrl) URL.revokeObjectURL(currentUrl)
    }
  }, [jobId, active])
  return <div className="preview-wrap"><div className="preview-heading"><span><b>TRACKING VIEW</b><small>Annotated frames · boxes show detected people · IDs follow tracks</small></span><span className={active ? 'preview-live' : 'preview-live final'}>{frameTime ? active ? 'LIVE · UPDATING' : 'LAST FRAME' : active ? 'STARTING' : 'PREVIEW'}</span></div>
    {frameUrl ? <img className="tracking-preview" src={frameUrl} alt="Latest annotated frame showing detected and tracked swimmers"/> : <div className="preview-placeholder"><span className="preview-spinner"/><b>{active ? 'Starting video analysis…' : 'No annotated frame available'}</b><small>{active ? 'The live tracking view will appear as soon as the first frame is processed.' : 'Upload a video to see detections and tracking IDs here.'}</small></div>}
  </div>
}
