import { ChangeEvent, useCallback, useEffect, useRef, useState } from 'react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
type Job = { id: string; filename: string; status: string; progress: number; created_at: string; error?: string; summary?: { frames_processed: number; tracks_seen: number; risk_assessed: boolean; risk_reason?: string }; video_url?: string | null }
type Incident = { id: number; job_id: string; track_id: number; state: string; score: number | null; timestamp_seconds: number; created_at: string }

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
  const [soundEnabled, setSoundEnabled] = useState(() => localStorage.getItem('poolwatch-sound') === 'true')
  const knownIncidents = useRef<Set<number> | null>(null)
  const audioContext = useRef<AudioContext | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [h, j, i] = await Promise.all([api<any>('/api/health'), api<Job[]>('/api/jobs'), api<Incident[]>('/api/incidents')])
      setHealth(h); setJobs(j); setIncidents(i)
      setIncidentsLoaded(true)
      if (selected) setSelected(await api<Job>(`/api/jobs/${selected.id}`))
      setError('')
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to connect to the monitoring service.') }
  }, [selected])

  useEffect(() => { void refresh(); const timer = window.setInterval(() => void refresh(), 2500); return () => window.clearInterval(timer) }, [refresh])
  useEffect(() => {
    if (!incidentsLoaded) return
    const next = new Set(incidents.map(item => item.id))
    if (knownIncidents.current && soundEnabled && incidents.some(item => !knownIncidents.current!.has(item.id))) playAlert()
    knownIncidents.current = next
  }, [incidents, soundEnabled, incidentsLoaded])

  function toggleSound() {
    const next = !soundEnabled
    setSoundEnabled(next); localStorage.setItem('poolwatch-sound', String(next))
    if (next && typeof AudioContext !== 'undefined') {
      audioContext.current ??= new AudioContext()
      void audioContext.current.resume()
    }
  }

  function playAlert() {
    if (!audioContext.current || audioContext.current.state !== 'running') return
    const context = audioContext.current
    for (let i = 0; i < 3; i++) {
      const start = context.currentTime + i * 0.28
      const tone = context.createOscillator(), volume = context.createGain()
      tone.frequency.value = 880; volume.gain.setValueAtTime(0.0001, start)
      volume.gain.exponentialRampToValueAtTime(0.12, start + 0.02); volume.gain.exponentialRampToValueAtTime(0.0001, start + 0.18)
      tone.connect(volume); volume.connect(context.destination); tone.start(start); tone.stop(start + 0.19)
    }
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
    <section className="hero"><div><p className="eyebrow">MONITORING CONSOLE / LOCAL ANALYSIS</p><h1>Every second<br/><em>matters.</em></h1><p className="lead">Analyze pool footage with object detection and persistent person tracking.</p><label className={`upload ${busy ? 'disabled' : ''}`}><input type="file" accept="video/*,.mp4,.mov,.avi,.mkv,.webm" disabled={busy} onChange={upload}/><span>{busy ? 'UPLOADING…' : '＋  ANALYZE A VIDEO'}</span></label><span className="meta">MP4, MOV, AVI, MKV, WEBM · max 500 MB</span></div><div className="status-card"><div className="card-head"><span>SYSTEM STATUS</span><span className="pulse"/></div><div className="risk"><span className="risk-icon">!</span><div><strong>RISK UNASSESSED</strong><small>{health?.risk_model_available ? 'Temporal classifier is configured' : 'No validated temporal model is installed'}</small></div></div><div className="status-line"><span>Person tracker</span><b>DeepSORT</b></div><div className="status-line"><span>Live CCTV</span><b className="muted">NOT CONFIGURED</b></div><div className="status-line"><span>Pose estimation</span><b className="muted">{health?.pose_enabled ? 'ENABLED' : health?.pose_requested ? 'MODEL MISSING' : 'DISABLED'}</b></div><p className="note">Detection labels are not a validated drowning-risk score. Maintain continuous human supervision.</p></div></section>
    {error && <div className="error" role="alert">{error}<button onClick={() => void refresh()}>Retry</button></div>}
    <section className="grid"><div className="panel"><div className="panel-title"><div><p className="eyebrow">ANALYSIS</p><h2>{selected ? 'Selected video' : 'Recent jobs'}</h2></div><button className="text-button" onClick={() => { setSelected(null); void refresh() }}>VIEW ALL</button></div>
      {selected ? <JobDetails job={selected} /> : jobs.length === 0 ? <div className="empty"><span>▧</span><strong>No videos analyzed</strong><p>Upload a pool video to create your first analysis job.</p></div> : <div className="job-list">{jobs.map(job => <button className="job" key={job.id} onClick={() => void api<Job>(`/api/jobs/${job.id}`).then(setSelected).catch(e => setError(e.message))}><span className="file-icon">▶</span><span className="job-name"><b>{job.filename}</b><small>{new Date(job.created_at).toLocaleString()}</small></span><span className={`badge ${job.status}`}>{job.status.toUpperCase()}</span><span className="arrow">›</span></button>)}</div>}
    </div><div className="panel incidents"><div className="panel-title"><div><p className="eyebrow">EVENT LOG</p><h2>Flagged incidents</h2></div><div className="event-tools"><button className={`sound-toggle ${soundEnabled ? 'active' : ''}`} aria-pressed={soundEnabled} onClick={toggleSound}>SOUND {soundEnabled ? 'ON' : 'OFF'}</button><span className="count">{incidents.length}</span></div></div>{incidents.length === 0 ? <div className="empty compact"><span>◷</span><strong>No flagged incidents</strong><p>Incidents appear only when a supported risk model is configured.</p></div> : <div className="incident-list">{incidents.map(i => <div className="incident" key={i.id}><span className={i.state === 'EMERGENCY' ? 'incident-icon emergency' : 'incident-icon'}>!</span><div><b>{i.state} · Track {i.track_id}</b><small>Job {i.job_id.slice(0, 8)} · {i.timestamp_seconds.toFixed(1)} sec</small></div><time>{new Date(i.created_at).toLocaleDateString()}</time></div>)}</div>}</div></section>
    <footer><span>POOLWATCH <i/> RESEARCH BUILD 0.1</span><p>Safety-support prototype. Never replaces lifeguards, emergency response, or continuous supervision.</p></footer>
  </main>
}

function JobDetails({ job }: { job: Job }) {
  return <div className="detail">{job.status === 'processing' || job.status === 'queued' ? <><div className="progress-label"><span>{job.status === 'queued' ? 'Waiting for the video worker' : 'Processing frames'}</span><b>{Math.round(job.progress || 0)}%</b></div><div className="progress"><i style={{ width: `${job.progress || 0}%` }}/></div><p className="subtle">The worker runs detection and DeepSORT locally. This can take several minutes.</p></> : job.status === 'failed' ? <div className="failure"><b>Analysis could not finish</b><p>{job.error}</p><p className="subtle">Check that trained YOLO weights are installed and configured.</p></div> : <><video className="result-video" controls src={`${API}/api/jobs/${job.id}/video`}/><div className="metrics"><div><small>FRAMES</small><b>{job.summary?.frames_processed ?? '—'}</b></div><div><small>TRACKS</small><b>{job.summary?.tracks_seen ?? '—'}</b></div><div><small>RISK MODEL</small><b>{job.summary?.risk_assessed ? 'ACTIVE' : 'NONE'}</b></div></div><p className="subtle">{job.summary?.risk_reason || 'Risk states require a validated temporal classifier.'}</p></>}</div>
}
