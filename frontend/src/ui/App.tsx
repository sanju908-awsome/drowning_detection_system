import { ChangeEvent, FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { createUserWithEmailAndPassword, onAuthStateChanged, signInWithEmailAndPassword, signOut } from 'firebase/auth'
import type { User } from 'firebase/auth'
import { auth, firebaseConfigured } from './firebase'

const API = import.meta.env.VITE_API_URL?.replace(/\/$/, '') || (import.meta.env.DEV ? 'http://localhost:8000' : '')
let currentUser: User | null = null
function apiUrl(path: string) {
  if (!API) throw new Error('The monitoring backend is not configured. Set VITE_API_URL in the Vercel project settings.')
  return `${API}${path}`
}
async function authorizedFetch(path: string, init?: RequestInit) {
  const headers = new Headers(init?.headers)
  if (currentUser) headers.set('Authorization', `Bearer ${await currentUser.getIdToken()}`)
  const response = await fetch(apiUrl(path), {...init, headers})
  if (response.status === 401) {
    if (auth) void signOut(auth)
  }
  return response
}
type Job = { id: string; filename: string; status: string; progress: number; created_at: string; error?: string; summary?: { frames_processed: number; tracks_seen: number; risk_assessed: boolean; risk_reason?: string; pose_available?: boolean; pose_detections?: number }; video_url?: string | null }
type Incident = { id: number; job_id: string; track_id: number; state: string; score: number | null; timestamp_seconds: number; created_at: string; class_name?: string | null }

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await authorizedFetch(path, init)
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `Request failed (${response.status})`)
  return response.json()
}

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [authReady, setAuthReady] = useState(false)
  const [accessReady, setAccessReady] = useState(false)
  const [authorized, setAuthorized] = useState(false)
  useEffect(() => {
    if (!auth) { setAuthReady(true); return }
    return onAuthStateChanged(auth, signedInUser => { currentUser = signedInUser; setUser(signedInUser); setAuthReady(true) })
  }, [])
  useEffect(() => {
    if (!user) { setAccessReady(false); setAuthorized(false); return }
    let current = true
    void api<{authorized: boolean}>('/api/auth/status')
      .then(result => { if (current) { setAuthorized(result.authorized); setAccessReady(true) } })
      .catch(() => { if (current) { setAuthorized(false); setAccessReady(true) } })
    return () => { current = false }
  }, [user])
  if (!firebaseConfigured) return <AuthSetupMessage />
  if (!authReady) return <main className="shell" style={{minHeight: '100vh', display: 'grid', placeItems: 'center'}}>Loading secure sign-in…</main>
  if (!user) return <AccessGate />
  if (!accessReady) return <main className="shell" style={{minHeight: '100vh', display: 'grid', placeItems: 'center'}}>Checking access approval…</main>
  if (!authorized) return <AccessPending email={user.email || ''} onLogout={() => { if (auth) void signOut(auth) }} />
  return <MonitoringApp onLogout={() => { if (auth) void signOut(auth) }} />
}

function AuthSetupMessage() {
  return <main className="shell" style={{minHeight: '100vh', display: 'grid', placeItems: 'center'}}><section className="panel" style={{width: 'min(100%, 460px)', padding: '2rem'}}><p className="eyebrow">POOLWATCH · SIGN-IN SETUP</p><h1 style={{fontSize: '2rem'}}>Firebase is not configured</h1><p className="subtle">Set VITE_FIREBASE_API_KEY, VITE_FIREBASE_AUTH_DOMAIN, VITE_FIREBASE_PROJECT_ID, and VITE_FIREBASE_APP_ID in the Vercel project settings, then redeploy.</p></section></main>
}

function AccessGate() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [createAccount, setCreateAccount] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function unlock(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('')
    try {
      if (!auth) throw new Error('Firebase is not configured for this site.')
      if (createAccount) await createUserWithEmailAndPassword(auth, email, password)
      else await signInWithEmailAndPassword(auth, email, password)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not connect to the monitoring service.')
    } finally { setBusy(false) }
  }
  return <main className="shell" style={{minHeight: '100vh', display: 'grid', placeItems: 'center'}}>
    <section className="panel" style={{width: 'min(100%, 460px)', padding: '2rem'}}>
      <p className="eyebrow">POOLWATCH · PRIVATE MONITORING</p><h1 style={{fontSize: '2rem', margin: '0 0 .5rem'}}>Sign in</h1>
      <p className="subtle">Sign in with your account. New accounts must be approved by the system owner before monitoring access is granted.</p>
      <form onSubmit={unlock} style={{display: 'grid', gap: '1rem', marginTop: '1.5rem'}}>
        <label>EMAIL<input autoComplete="username" type="email" required value={email} onChange={event => setEmail(event.target.value)} aria-label="Account email" style={{display: 'block', width: '100%', marginTop: '.5rem'}} /></label>
        <label>PASSWORD<input autoComplete="current-password" type="password" required value={password} onChange={event => setPassword(event.target.value)} aria-label="Account password" style={{display: 'block', width: '100%', marginTop: '.5rem'}} /></label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="camera-connect" disabled={busy || !email || !password}>{busy ? (createAccount ? 'CREATING ACCOUNT…' : 'SIGNING IN…') : createAccount ? 'CREATE ACCOUNT' : 'SIGN IN'}</button>
      </form>
      <button className="text-button" style={{marginTop: '1rem'}} onClick={() => {setCreateAccount(!createAccount); setError('')}}>{createAccount ? 'Already have an account? Sign in' : 'Need an account? Create one'}</button>
    </section>
  </main>
}

function AccessPending({email, onLogout}: {email: string; onLogout: () => void}) {
  const subject = encodeURIComponent('PoolWatch monitoring access request')
  const body = encodeURIComponent(`Please review monitoring access for this Firebase account: ${email}`)
  return <main className="shell" style={{minHeight: '100vh', display: 'grid', placeItems: 'center'}}><section className="panel" style={{width: 'min(100%, 460px)', padding: '2rem'}}><p className="eyebrow">POOLWATCH · ACCESS REVIEW</p><h1 style={{fontSize: '2rem'}}>Approval required</h1><p className="subtle">Your account ({email}) is signed in, but it cannot access monitoring until the system owner approves it.</p><p><a href={`mailto:sanjukarra15@gmail.com?subject=${subject}&body=${body}`}>Email the system owner to request access</a></p><p className="subtle">After approval, the owner must add your email to the backend allowlist.</p><button className="text-button" onClick={onLogout}>SIGN OUT</button></section></main>
}

function MonitoringApp({onLogout}: {onLogout: () => void}) {
  const [health, setHealth] = useState<any>(null)
  const [jobs, setJobs] = useState<Job[]>([])
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [selected, setSelected] = useState<Job | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [incidentsLoaded, setIncidentsLoaded] = useState(false)
  const [soundEnabled, setSoundEnabled] = useState(true)
  const [screen, setScreen] = useState<'analysis' | 'cctv' | 'webcam'>('analysis')
  const knownIncidents = useRef<Set<number> | null>(null)
  const alertedIncidentIds = useRef<Set<number>>(new Set())
  const alertableJobs = useRef<Set<string>>(new Set())
  const buzzerPlaying = useRef(false)
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
    if (!soundEnabled) return
    const timer = window.setInterval(() => {
      void api<Incident[]>('/api/incidents').then(setIncidents).catch(() => undefined)
    }, 350)
    return () => window.clearInterval(timer)
  }, [soundEnabled])
  useEffect(() => {
    if (!incidentsLoaded) return
    const next = new Set(incidents.map(item => item.id))
    const newDrowning = incidents.filter(item => item.class_name?.trim().toLowerCase() === 'drowning detector'
      && !alertedIncidentIds.current.has(item.id)
      && (knownIncidents.current === null ? alertableJobs.current.has(item.job_id) : !knownIncidents.current.has(item.id) || alertableJobs.current.has(item.job_id)))
    if (soundEnabled && newDrowning.length && audioContext.current?.state === 'running') {
      newDrowning.forEach(item => alertedIncidentIds.current.add(item.id))
      playAlert()
    }
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
    if (buzzerPlaying.current) return
    buzzerPlaying.current = true
    try { await context.resume() } catch { buzzerPlaying.current = false; return }
    window.setTimeout(() => { buzzerPlaying.current = false }, 2850)
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
    if (next) {
      void getAudioContext()?.resume()
      const activeWarning = incidents.find(item => selected?.id === item.job_id && item.class_name?.trim().toLowerCase() === 'drowning detector' && !alertedIncidentIds.current.has(item.id))
      if (activeWarning && (selected?.status === 'processing' || selected?.status === 'queued')) {
        alertedIncidentIds.current.add(activeWarning.id)
        void playBuzzer()
      }
    }
  }

  function unlockSound() {
    if (!soundEnabled) return
    const context = getAudioContext()
    if (!context) return
    void context.resume().then(() => {
      if (context.state !== 'running') return
      const pending = incidents.find(item => item.class_name?.trim().toLowerCase() === 'drowning detector'
        && !alertedIncidentIds.current.has(item.id)
        && (alertableJobs.current.has(item.job_id) || knownIncidents.current?.has(item.id) === false))
      if (pending) {
        alertedIncidentIds.current.add(pending.id)
        void playBuzzer()
      }
    }).catch(() => undefined)
  }

  function playAlert() {
    if (soundEnabled) void playBuzzer()
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setBusy(true); setError('')
    const form = new FormData(); form.append('file', file)
    try {
      const job = await api<Job>('/api/jobs', { method: 'POST', body: form })
      alertableJobs.current.add(job.id)
      setSelected(job); await refresh()
    } catch (e) { setError(e instanceof Error ? e.message : 'Upload failed.') }
    finally { setBusy(false) }
  }

  return <main className="shell" onPointerDownCapture={unlockSound} onKeyDownCapture={unlockSound}>
    <header className="top"><div className="brand"><span className="mark">◉</span><div><strong>POOLWATCH</strong><small>VIDEO SAFETY RESEARCH PROTOTYPE</small></div></div><nav className="screen-nav" aria-label="Application screens"><button className={screen === 'analysis' ? 'screen-tab active' : 'screen-tab'} onClick={() => setScreen('analysis')}>VIDEO ANALYSIS</button><button className={screen === 'cctv' ? 'screen-tab active' : 'screen-tab'} onClick={() => setScreen('cctv')}>CCTV LIVE</button><button className={screen === 'webcam' ? 'screen-tab active' : 'screen-tab'} onClick={() => setScreen('webcam')}>PC WEBCAM</button></nav><div className="header-alert"><button className={`sound-toggle ${soundEnabled ? 'active' : 'sound-off'}`} aria-pressed={soundEnabled} onClick={toggleSound}>ALARM {soundEnabled ? 'ON' : 'OFF · ARM'}</button><button className="sound-test" onClick={() => void playBuzzer()}>TEST SOUND</button><button className="text-button" onClick={onLogout}>LOCK</button></div><div className="connection"><i className={health?.status === 'ok' ? 'dot online' : 'dot'} />{health?.status === 'ok' ? 'SERVICE CONNECTED' : 'SERVICE OFFLINE'}</div></header>
    {screen === 'cctv' ? <CctvPanel /> : screen === 'webcam' ? <WebcamPanel onAlert={() => { if (soundEnabled) playAlert() }} /> : <>
    {!selected && <section className="hero"><div><p className="eyebrow">MONITORING CONSOLE / LOCAL ANALYSIS</p><h1>Every second<br/><em>matters.</em></h1><p className="lead">Analyze pool footage with object detection and persistent person tracking.</p><label className={`upload ${busy ? 'disabled' : ''}`}><input type="file" accept="video/*,.mp4,.mov,.avi,.mkv,.webm" disabled={busy} onChange={upload}/><span>{busy ? 'UPLOADING…' : '＋  ANALYZE A VIDEO'}</span></label><span className="meta">MP4, MOV, AVI, MKV, WEBM · max 500 MB</span></div><div className="status-card"><div className="card-head"><span>SYSTEM STATUS</span><span className="pulse"/></div><div className="risk"><span className="risk-icon">!</span><div><strong>RISK UNASSESSED</strong><small>{health?.risk_model_available ? 'Experimental SAFE/EMERGENCY temporal model installed' : 'No temporal model is installed'}</small></div></div><div className="status-line"><span>Person tracker</span><b>DeepSORT</b></div><div className="status-line"><span>Live CCTV</span><b className={health?.cctv_enabled ? '' : 'muted'}>{health?.cctv_enabled ? 'CONNECTED' : 'NOT CONNECTED'}</b></div><div className="status-line"><span>Pose estimation</span><b className="muted">{health?.pose_enabled ? 'ENABLED' : health?.pose_requested ? 'MODEL MISSING' : 'DISABLED'}</b></div><p className="note">Experimental motion alerts are not safety-validated and do not replace human supervision.</p></div></section>}
    {error && <div className="error" role="alert">{error}<button onClick={() => void refresh()}>Retry</button></div>}
    {selected ? <Monitor job={selected} incidents={incidents.filter(i => i.job_id === selected.id)} health={health} busy={busy} onUpload={upload} onViewAll={() => setSelected(null)} soundEnabled={soundEnabled} onToggleSound={toggleSound} onTestBuzzer={() => void playBuzzer()}/> : <section className="grid"><div className="panel"><div className="panel-title"><div><p className="eyebrow">ANALYSIS</p><h2>Videos & results</h2></div></div>
      {jobs.length === 0 ? <div className="empty"><span>▧</span><strong>No videos analyzed</strong><p>Upload a pool video to create your first analysis job.</p></div> : <div className="job-list">{jobs.map(job => <button className="job" key={job.id} aria-label={`${job.status === 'completed' ? 'View result for' : 'Open'} ${job.filename}`} onClick={() => void api<Job>(`/api/jobs/${job.id}`).then(opened => { if (opened.status === 'processing' || opened.status === 'queued') alertableJobs.current.add(opened.id); setSelected(opened) }).catch(e => setError(e.message))}><span className="file-icon">▶</span><span className="job-name"><b>{job.filename}</b><small>{new Date(job.created_at).toLocaleString()}</small></span><span className={`badge ${job.status}`}>{job.status === 'completed' ? 'VIEW RESULT' : job.status.toUpperCase()}</span><span className="arrow">›</span></button>)}</div>}
    </div><div className="panel incidents"><div className="panel-title"><div><p className="eyebrow">EVENT LOG</p><h2>Flagged incidents</h2></div><div className="event-tools"><button className={`sound-toggle ${soundEnabled ? 'active' : 'sound-off'}`} aria-pressed={soundEnabled} title={soundEnabled ? 'Alert tones are armed' : 'Click to arm browser alert tones'} onClick={toggleSound}>ALARM {soundEnabled ? 'ON' : 'OFF · ARM'}</button><button className="sound-test" onClick={() => void playBuzzer()}>TEST BUZZER</button><span className="count">{incidents.length}</span></div></div>{incidents.length === 0 ? <div className="empty compact"><span>◷</span><strong>No detection warnings yet</strong><p>Tracked temporal risk is experimental and binary (SAFE/EMERGENCY); confidence and alert behavior are not safety-validated.</p></div> : <div className="incident-list">{incidents.slice(0, 8).map(i => <div className="incident" key={i.id}><span className={i.state === 'EMERGENCY' ? 'incident-icon emergency' : 'incident-icon'}>!</span><div><b>{i.class_name || i.state} · {i.state} · Track {i.track_id}</b><small>Job {i.job_id.slice(0, 8)} · {i.timestamp_seconds.toFixed(1)} sec</small></div><time>{new Date(i.created_at).toLocaleDateString()}</time></div>)}</div>}</div></section>}
    </>}
    <footer><span>POOLWATCH <i/> RESEARCH BUILD 0.1</span><p>Safety-support prototype. Never replaces lifeguards, emergency response, or continuous supervision.</p></footer>
  </main>
}

function WebcamPanel({onAlert}: {onAlert: () => void}) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const sessionRef = useRef('')
  const onAlertRef = useRef(onAlert)
  onAlertRef.current = onAlert
  const mountedRef = useRef(true)
  const [active, setActive] = useState(false)
  const [detecting, setDetecting] = useState(false)
  const [sessionId, setSessionId] = useState('')
  const [frameUrl, setFrameUrl] = useState('')
  const [riskState, setRiskState] = useState('UNASSESSED')
  const [trackCount, setTrackCount] = useState(0)
  const [message, setMessage] = useState('Open the webcam, then start live detection.')
  const [analysisError, setAnalysisError] = useState('')

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      streamRef.current?.getTracks().forEach(track => track.stop())
      streamRef.current = null
      const id = sessionRef.current
      if (id) void authorizedFetch('/api/webcam/stop', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({session_id: id})}).catch(() => undefined)
    }
  }, [])

  useEffect(() => {
    if (videoRef.current) videoRef.current.srcObject = streamRef.current
  }, [active])

  async function startCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
      setMessage('Camera access is unavailable. Open this page over HTTPS or from localhost in a supported browser.')
      return
    }
    setMessage('Requesting permission to use the webcam…')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({video: true, audio: false})
      if (!mountedRef.current) {
        stream.getTracks().forEach(track => track.stop())
        return
      }
      streamRef.current = stream
      setActive(true)
      setMessage('Webcam is open. Start live detection to send sampled frames to the monitoring backend for analysis.')
    } catch (error) {
      const name = error instanceof DOMException ? error.name : ''
      setMessage(name === 'NotAllowedError'
        ? 'Camera permission was denied. Allow camera access for this site in your browser settings, then try again.'
        : name === 'NotFoundError'
          ? 'No webcam was found. Connect or enable a camera, then try again.'
          : name === 'NotReadableError'
            ? 'The webcam is busy in another app. Close that app and try again.'
            : 'Could not open the webcam. Check that it is connected and enabled.')
    }
  }

  function stopCamera() {
    stopDetection()
    streamRef.current?.getTracks().forEach(track => track.stop())
    streamRef.current = null
    setActive(false)
    setFrameUrl('')
    setMessage('Webcam stopped.')
  }

  async function startDetection() {
    setAnalysisError('')
    setMessage('Starting the detector and tracker…')
    try {
      const result = await api<{session_id: string; temporal_model_ready: boolean}>('/api/webcam/start', {method: 'POST'})
      sessionRef.current = result.session_id
      setSessionId(result.session_id)
      setRiskState('UNASSESSED')
      setTrackCount(0)
      setFrameUrl('')
      setDetecting(true)
      setMessage(result.temporal_model_ready
        ? 'Detection is running. Experimental temporal risk results are not safety validated.'
        : 'Person detection and tracking are running; temporal risk classification is unavailable on this backend.')
    } catch (error) {
      setAnalysisError(error instanceof Error ? error.message : 'Could not start live detection.')
      setMessage('Live detection could not start.')
    }
  }

  function stopDetection() {
    const id = sessionRef.current
    sessionRef.current = ''
    setSessionId('')
    setDetecting(false)
    setRiskState('UNASSESSED')
    setTrackCount(0)
    setFrameUrl('')
    if (id) void authorizedFetch('/api/webcam/stop', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({session_id: id})}).catch(() => undefined)
  }

  useEffect(() => {
    if (!active || !detecting || !sessionId) return
    let live = true
    let timer = 0
    let pending = false
    const analyzeFrame = async () => {
      if (!live || pending) return
      const video = videoRef.current
      const canvas = canvasRef.current
      if (!video || !canvas || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
        timer = window.setTimeout(analyzeFrame, 350)
        return
      }
      pending = true
      try {
        const scale = Math.min(1, 960 / video.videoWidth)
        canvas.width = Math.max(1, Math.round(video.videoWidth * scale))
        canvas.height = Math.max(1, Math.round(video.videoHeight * scale))
        canvas.getContext('2d')?.drawImage(video, 0, 0, canvas.width, canvas.height)
        const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.72))
        if (!blob) throw new Error('Could not capture a webcam frame.')
        const response = await authorizedFetch(`/api/webcam/frame?session_id=${encodeURIComponent(sessionId)}`, {
          method: 'POST', headers: {'Content-Type': 'image/jpeg'}, body: blob,
        })
        const result = await response.json().catch(() => ({}))
        if (!response.ok) throw new Error(result.detail || `Frame analysis failed (${response.status}).`)
        if (!live) return
        setFrameUrl(`data:image/jpeg;base64,${result.frame_jpeg_base64}`)
        setRiskState(result.risk_state || 'UNASSESSED')
        setTrackCount(result.track_count || 0)
        setAnalysisError('')
        if (result.events?.length) onAlertRef.current()
      } catch (error) {
        if (live) setAnalysisError(error instanceof Error ? error.message : 'Live frame analysis failed.')
      } finally {
        pending = false
        if (live) timer = window.setTimeout(analyzeFrame, 350)
      }
    }
    void analyzeFrame()
    return () => { live = false; window.clearTimeout(timer) }
  }, [active, detecting, sessionId])

  return <section className="cctv-screen webcam-screen">
    <div className="cctv-screen-head"><div><p className="eyebrow">THIS DEVICE · LIVE ANALYSIS</p><h1>PC Webcam</h1><p>Show the webcam and analyze sampled frames in real time</p></div><span className={`camera-state ${detecting ? 'connected' : active ? 'disconnected' : 'disconnected'}`}>{detecting ? 'DETECTING' : active ? 'CAMERA ON' : 'STOPPED'}</span></div>
    <div className="webcam-controls"><div><b>Camera and detection controls</b><small>Browser permission opens the camera. During detection, sampled frames are sent to the configured backend and are not saved as video.</small></div><div className="webcam-actions">{!active ? <button className="camera-connect" onClick={() => void startCamera()}>OPEN PC WEBCAM</button> : <><button className="camera-connect" disabled={detecting} onClick={() => void startDetection()}>{detecting ? 'DETECTION RUNNING' : 'START LIVE DETECTION'}</button>{detecting && <button className="camera-disconnect" onClick={stopDetection}>STOP DETECTION</button>}<button className="camera-disconnect" onClick={stopCamera}>CLOSE CAMERA</button></>}</div></div>
    <p className={`camera-message ${active ? 'connected' : ''}`} role="status">{message}</p>
    <div className="cctv-viewer webcam-viewer" aria-label="PC webcam preview">
      {active && <video ref={videoRef} autoPlay muted playsInline aria-label="Live preview from this computer’s webcam"/>}
      {detecting && frameUrl && <img className="webcam-analysis-frame" src={frameUrl} alt={`Analyzed webcam frame. Risk ${riskState}; ${trackCount} tracked people.`}/>}
      {!active && <div className="cctv-empty"><span className="camera-pulse">◉</span><b>Webcam preview</b><small>Select “Open PC Webcam” and allow browser camera permission to begin.</small></div>}
    </div>
    <canvas ref={canvasRef} className="webcam-capture-canvas" aria-hidden="true"/>
    <div className="webcam-metrics"><div><small>TRACKED PEOPLE</small><b>{detecting ? trackCount : '—'}</b></div><div><small>TEMPORAL RISK</small><b className={riskState === 'WARNING' || riskState === 'EMERGENCY' ? 'webcam-risk-alert' : ''}>{detecting ? riskState : 'UNASSESSED'}</b></div><div><small>DETECTOR</small><b>{detecting ? 'LIVE' : 'STOPPED'}</b></div></div>
    {analysisError && <p className="camera-message error" role="alert">{analysisError}</p>}
    <div className="cctv-screen-note">This is an experimental detector, not a validated drowning alarm. Keep a trained human supervisor watching; never rely on this prototype for emergency response.</div>
  </section>
}

function CctvPanel() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [status, setStatus] = useState('not_configured')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [frameUrl, setFrameUrl] = useState('')
  const [riskState, setRiskState] = useState('UNASSESSED')
  const [trackCount, setTrackCount] = useState(0)
  const [analysisError, setAnalysisError] = useState('')

  useEffect(() => {
    void api<{status: string; risk_state?: string; track_count?: number; analysis_error?: string | null}>('/api/cctv/status').then(result => { setStatus(result.status); setRiskState(result.risk_state || 'UNASSESSED'); setTrackCount(result.track_count || 0); setAnalysisError(result.analysis_error || '') }).catch(() => setStatus('error'))
  }, [])

  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true); setStatus('connecting'); setMessage('Checking the camera login and opening its stream…')
    try {
      const result = await api<{status: string; error?: string | null; risk_state?: string; track_count?: number; analysis_error?: string | null}>('/api/cctv/connect', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username, password}),
      })
      setStatus(result.status)
      setRiskState(result.risk_state || 'UNASSESSED'); setTrackCount(result.track_count || 0); setAnalysisError(result.analysis_error || '')
      setMessage(result.status === 'connected' ? 'Camera connected. Live frames are updating below.' : result.error || 'Connection is still starting; check camera settings if it does not connect.')
      if (result.status === 'connected') setPassword('')
    } catch (error) {
      setStatus('error')
      setMessage(error instanceof Error ? error.message : 'Could not connect to the camera.')
    } finally { setBusy(false) }
  }

  async function disconnect() {
    setBusy(true)
    try { await api('/api/cctv/disconnect', {method: 'POST'}); setStatus('disconnected'); setMessage('Camera disconnected.') }
    catch (error) { setMessage(error instanceof Error ? error.message : 'Could not disconnect the camera.') }
    finally { setBusy(false) }
  }

  useEffect(() => {
    if (status !== 'connecting' && status !== 'connected') return
    let live = true
    const poll = async () => {
      try {
        const result = await api<{status: string; error?: string | null; risk_state?: string; track_count?: number; analysis_error?: string | null}>('/api/cctv/status')
        if (!live) return
        setStatus(result.status)
        setRiskState(result.risk_state || 'UNASSESSED'); setTrackCount(result.track_count || 0); setAnalysisError(result.analysis_error || '')
        if (result.status === 'error') setMessage(result.error || 'Camera stream failed.')
      } catch { /* The API connection banner reports backend availability. */ }
    }
    const timer = window.setInterval(() => void poll(), 800)
    return () => { live = false; window.clearInterval(timer) }
  }, [status])

  useEffect(() => {
    if (status !== 'connected') return
    let live = true
    let previous = ''
    let requestPending = false
    const fetchFrame = async () => {
      if (requestPending) return
      requestPending = true
      try {
        const response = await authorizedFetch('/api/cctv/frame', {cache: 'no-store'})
        if (!response.ok) return
        const next = URL.createObjectURL(await response.blob())
        if (!live) { URL.revokeObjectURL(next); return }
        if (previous) URL.revokeObjectURL(previous)
        previous = next; setFrameUrl(next)
      } catch { /* Status remains visible; retry on the next frame tick. */ }
      finally { requestPending = false }
    }
    void fetchFrame()
    const timer = window.setInterval(() => void fetchFrame(), 250)
    return () => { live = false; window.clearInterval(timer); if (previous) URL.revokeObjectURL(previous) }
  }, [status])

  return <section className="cctv-screen">
    <div className="cctv-screen-head"><div><p className="eyebrow">LIVE CAMERA MONITOR</p><h1>Pool CCTV</h1><p>Live stream and camera sign-in</p></div><span className={`camera-state ${status}`}>{status.replace('_', ' ').toUpperCase()}</span></div>
    <div className="cctv-login-panel"><form className="cctv-login" onSubmit={connect}>
      <label>USERNAME<input value={username} onChange={event => setUsername(event.target.value)} autoComplete="username" aria-label="Camera username"/></label>
      <label>PASSWORD<input type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete="current-password" aria-label="Camera password"/></label>
      <button className="camera-connect" disabled={busy}>{busy ? 'CONNECTING…' : 'SIGN IN TO CAMERA'}</button>
      <button className="camera-disconnect" type="button" disabled={busy || status !== 'connected'} onClick={() => void disconnect()}>DISCONNECT</button>
    </form><small>Camera login is sent to the local app and held in memory only. Use a camera you own or are authorized to access.</small></div>
    {message && <p className={`camera-message ${status}`}>{message}</p>}
    <div className="cctv-viewer" aria-label="Live CCTV footage">
      {status === 'connected' && frameUrl ? <img src={frameUrl} alt="Live frame from connected CCTV camera"/> : <div className="cctv-empty"><span className="camera-pulse">◉</span><b>{status === 'connecting' ? 'Connecting to camera…' : status === 'not_configured' ? 'Camera address needs setup' : status === 'error' ? 'Camera connection failed' : 'Live footage will appear here'}</b><small>{status === 'not_configured' ? 'The camera RTSP address and stream path must be configured for this project before sign-in can connect.' : 'Keep this page open while viewing the feed.'}</small></div>}
    </div>
    <div className="status-line"><span>Live tracks</span><b>{status === 'connected' ? trackCount : '—'}</b></div>
    <div className="status-line"><span>Temporal state</span><b>{status === 'connected' ? riskState : 'UNASSESSED'}</b></div>
    {analysisError && <p className="camera-message error">{analysisError}</p>}
    <div className="cctv-screen-note">Live detection is experimental and binary (SAFE/EMERGENCY). Maintain continuous human supervision.</div>
  </section>
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
      {processing || queued ? <LivePreview jobId={job.id} active={processing}/> : complete ? <ProtectedVideo jobId={job.id}/> : <div className="failure"><b>Analysis could not finish</b><p>{job.error}</p><p className="subtle">Check that trained YOLO weights are installed and configured.</p></div>}
      <div className="metrics monitor-metrics"><div><small>{complete ? 'FRAMES' : 'PROGRESS'}</small><b>{complete ? job.summary?.frames_processed ?? '—' : `${Math.round(job.progress || 0)}%`}</b></div><div><small>{complete ? 'TRACKS SEEN' : 'TRACKING'}</small><b>{complete ? job.summary?.tracks_seen ?? '—' : job.summary?.tracks_seen ?? 'ACTIVE'}</b></div><div><small>WARNINGS</small><b>{incidents.length}</b></div><div><small>POSE</small><b>{complete ? job.summary?.pose_available ? `${job.summary.pose_detections ?? 0}` : 'OFF' : health?.pose_enabled ? 'ON' : 'OFF'}</b></div></div>
      {complete && <p className="subtle">{job.summary?.risk_assessed
        ? 'The temporal risk classifier ran for this video. Its predictions are experimental and are not validated for safety use.'
        : job.summary?.risk_reason || 'Temporal risk was not assessed for this video.'}</p>}
    </div><aside className="monitor-side"><div className="panel monitor-status"><div className="panel-title"><div><p className="eyebrow">SYSTEM STATUS</p><h2>Analysis limits</h2></div></div><div className="status-line"><span>Temporal risk model</span><b className="muted">{health?.risk_model_available ? 'EXPERIMENTAL · BINARY' : 'NOT INSTALLED'}</b></div><div className="status-line"><span>Pose estimation</span><b>{health?.pose_enabled ? 'ENABLED' : 'DISABLED'}</b></div><div className="status-line"><span>Live CCTV preview</span><b className={health?.cctv_enabled ? '' : 'muted'}>{health?.cctv_enabled ? 'CONNECTED · PREVIEW' : 'NOT CONNECTED'}</b></div><p className="note">The model predicts only SAFE/EMERGENCY; alerts are not safety-validated. Keep a human supervisor watching the pool.</p></div>
      <div className="panel monitor-events"><div className="panel-title"><div><p className="eyebrow">THIS VIDEO</p><h2>Warnings</h2></div><div className="event-tools"><button className={`sound-toggle ${soundEnabled ? 'active' : 'sound-off'}`} aria-pressed={soundEnabled} title={soundEnabled ? 'Alert tones are armed' : 'Click to arm browser alert tones'} onClick={onToggleSound}>ALARM {soundEnabled ? 'ON' : 'OFF · ARM'}</button><button className="sound-test" onClick={onTestBuzzer}>TEST BUZZER</button><span className="count">{incidents.length}</span></div></div>{incidents.length === 0 ? <div className="empty compact"><strong>{processing ? 'Watching for temporal alerts' : 'No temporal alerts recorded'}</strong><p>The temporal classifier is experimental and binary (SAFE/EMERGENCY); its alerts are not safety-validated.</p></div> : <div className="incident-list">{incidents.slice(0, 12).map(i => <div className="incident" key={i.id}><span className={i.state === 'EMERGENCY' ? 'incident-icon emergency' : 'incident-icon'}>!</span><div><b>{i.class_name || i.state} · {i.state}</b><small>Track {i.track_id} · {i.timestamp_seconds.toFixed(1)} sec</small></div></div>)}</div>}</div></aside></div>
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
        const response = await authorizedFetch(`/api/jobs/${jobId}/preview`, { cache: 'no-store' })
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

function ProtectedVideo({jobId}: {jobId: string}) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    let live = true
    let objectUrl = ''
    void authorizedFetch(`/api/jobs/${jobId}/video`).then(async response => {
      if (!response.ok) return
      objectUrl = URL.createObjectURL(await response.blob())
      if (live) setUrl(objectUrl)
      else URL.revokeObjectURL(objectUrl)
    }).catch(() => undefined)
    return () => { live = false; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [jobId])
  return url ? <video className="monitor-video" controls src={url}/> : <div className="preview-placeholder"><b>Loading analyzed video…</b></div>
}
