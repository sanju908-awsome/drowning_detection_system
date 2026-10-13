import base64
import json
import mimetypes
import uuid
import threading
import time
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .cctv import CameraStream
from .processor import process_video
from .settings import get_settings
from .store import Store

settings = get_settings()
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.output_dir.mkdir(parents=True, exist_ok=True)
store = Store(settings.database_url)
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="video-worker")
preview_lock = threading.Lock()
latest_previews: dict[str, bytes] = {}
cctv_lock = threading.Lock()
cctv_stream: CameraStream | None = None
cctv_incident_lock = threading.Lock()
cctv_incidents: list[dict] = []
webcam_lock = threading.Lock()
webcam_session: dict | None = None
webcam_incidents: list[dict] = []


def record_webcam_incident(event: dict):
    incident = {**event, "id": int(datetime.now(timezone.utc).timestamp() * 1_000_000),
                "job_id": "PC-WEBCAM-LIVE", "created_at": datetime.now(timezone.utc).isoformat()}
    with webcam_lock:
        webcam_incidents.append(incident)
        del webcam_incidents[:-100]


def record_cctv_incident(event: dict):
    incident = {**event, "id": int(datetime.now(timezone.utc).timestamp() * 1_000_000),
                "job_id": "CCTV-LIVE", "created_at": datetime.now(timezone.utc).isoformat()}
    with cctv_incident_lock:
        cctv_incidents.append(incident)
        del cctv_incidents[:-100]
@asynccontextmanager
async def lifespan(_app):
    global cctv_stream
    store.initialize()
    try:
        yield
    finally:
        with cctv_lock:
            stream, cctv_stream = cctv_stream, None
        if stream:
            stream.stop()


async def require_firebase_user(request: Request):
    if request.url.path == "/api/health":
        return
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Sign in with your Firebase account to access monitoring.")
    if not settings.firebase_project_id.strip():
        raise HTTPException(503, "Firebase authentication is not configured. Set FIREBASE_PROJECT_ID on the backend.")
    try:
        import firebase_admin
        from firebase_admin import auth
        try:
            firebase_app = firebase_admin.get_app()
        except ValueError:
            firebase_app = firebase_admin.initialize_app(options={"projectId": settings.firebase_project_id})
        decoded_token = auth.verify_id_token(token, app=firebase_app, check_revoked=False)
    except Exception as exc:
        raise HTTPException(401, "Firebase sign-in expired or is invalid. Sign in again.") from exc
    allowed_emails = {email.strip().lower() for email in settings.firebase_allowed_emails.split(",") if email.strip()}
    user_email = str(decoded_token.get("email", "")).strip().lower()
    request.state.firebase_email = user_email
    request.state.firebase_allowed = bool(allowed_emails and user_email in allowed_emails)
    if not request.state.firebase_allowed and request.url.path != "/api/auth/status":
        raise HTTPException(403, "This Firebase account is not authorized for monitoring.")


app = FastAPI(title="Drowning Watch Research Prototype", version="0.1.0", lifespan=lifespan,
              description="Safety-support research prototype. Never use as a substitute for a lifeguard.",
              dependencies=[Depends(require_firebase_user)])
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Authorization"])


def run_job(job_id: str, source: Path, destination: Path):
    store.update_job(job_id, status="processing", progress=0)
    try:
        last_percent = [-1]
        def update(progress: float):
            whole_percent = int(progress)
            if whole_percent != last_percent[0]:
                store.update_job(job_id, progress=whole_percent)
                last_percent[0] = whole_percent
        def save_preview(frame: bytes):
            with preview_lock:
                latest_previews[job_id] = frame
            # Keep the last annotated frame available after the worker finishes
            # or the API process restarts, so completed jobs still show a preview.
            preview_path = settings.output_dir / f"{job_id}-preview.jpg"
            preview_path.write_bytes(frame)
        def record_event(event: dict):
            store.add_incidents(job_id, [event], datetime.now(timezone.utc).isoformat())
        summary = process_video(source, destination, settings, progress=update,
                                preview=save_preview, on_event=record_event)
        store.update_job(job_id, status="completed", progress=100, output_path=str(destination),
                         summary=json.dumps(summary))
    except Exception as exc:
        store.update_job(job_id, status="failed", error=f"{type(exc).__name__}: {exc}")
    finally:
        source.unlink(missing_ok=True)


def validate_video_upload(filename: str, content_type: str) -> tuple[str, str]:
    """Validate only the safe basename, extension and claimed MIME type."""
    original_name = Path(filename or "upload").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in {".mp4", ".mov", ".avi", ".mkv", ".webm"}:
        raise HTTPException(415, "Upload a video file with one of these extensions: mp4, mov, avi, mkv, webm.")
    guessed_type = content_type or mimetypes.guess_type(original_name)[0] or ""
    if not guessed_type.startswith("video/") and guessed_type != "application/octet-stream":
        raise HTTPException(415, "The uploaded file does not have a video content type.")
    return original_name, suffix


@app.get("/api/health")
def health():
    return {"status": "ok", "mode": "research-prototype", "detector_weights_available": settings.yolo_model.is_file(),
            "risk_model_available": settings.risk_model.is_file(),
            "pose_enabled": settings.pose_enabled and settings.pose_model.is_file(),
            "pose_requested": settings.pose_enabled, "pose_model_available": settings.pose_model.is_file(),
            "cctv_enabled": cctv_status()["status"] == "connected", "warning": "This prototype is not a substitute for trained lifeguards or emergency procedures."}


@app.get("/api/auth/status")
def auth_status(request: Request):
    return {"authorized": bool(getattr(request.state, "firebase_allowed", False))}


class CameraConnection(BaseModel):
    username: str = Field(default="", max_length=128)
    password: str = Field(default="", max_length=256)


class WebcamSessionRequest(BaseModel):
    session_id: str = Field(min_length=16, max_length=64)


@app.post("/api/webcam/start")
def start_webcam_analysis():
    global webcam_session
    try:
        from .live_analysis import LiveRiskAnalyzer
        analyzer = LiveRiskAnalyzer(settings)
    except FileNotFoundError as exc:
        raise HTTPException(503, "Webcam detection is unavailable because the configured YOLO model file is missing.") from exc
    except Exception as exc:
        raise HTTPException(503, f"Webcam detector could not start ({type(exc).__name__}). Check backend model and dependencies.") from exc
    session = {"id": uuid.uuid4().hex, "analyzer": analyzer, "started_at": time.monotonic(), "lock": threading.Lock()}
    with webcam_lock:
        webcam_session = session
    return {"session_id": session["id"], "detector_ready": True,
            "temporal_model_ready": analyzer.risk.ready,
            "risk_message": "Experimental temporal risk classifier; not validated for real-world safety."}


@app.post("/api/webcam/stop")
def stop_webcam_analysis(request: WebcamSessionRequest):
    global webcam_session
    with webcam_lock:
        if webcam_session and webcam_session["id"] == request.session_id:
            webcam_session = None
    return {"status": "stopped"}


def analyze_webcam_frame(session: dict, frame_bytes: bytes):
    import cv2
    with session["lock"]:
        with webcam_lock:
            if webcam_session is not session:
                raise HTTPException(409, "Webcam analysis session ended. Start it again.")
        import numpy as np
        image = cv2.imdecode(np.frombuffer(frame_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise HTTPException(400, "Could not decode the webcam frame.")
        annotated, events = session["analyzer"].process(image, time.monotonic() - session["started_at"])
        ok, encoded = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 76])
        if not ok:
            raise HTTPException(500, "Could not encode the analyzed webcam frame.")
        for event in events:
            record_webcam_incident(event)
        return {"frame_jpeg_base64": base64.b64encode(encoded.tobytes()).decode("ascii"),
                "risk_state": session["analyzer"].latest_state,
                "track_count": session["analyzer"].track_count,
                "events": events,
                "temporal_model_ready": session["analyzer"].risk.ready}


@app.post("/api/webcam/frame")
async def analyze_pc_webcam_frame(request: Request, session_id: str):
    with webcam_lock:
        session = webcam_session
    if not session or session["id"] != session_id:
        raise HTTPException(409, "Webcam analysis session is not active. Start the webcam analysis first.")
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() not in {"image/jpeg", "application/octet-stream"}:
        raise HTTPException(415, "Send a JPEG webcam frame.")
    frame_bytes = await request.body()
    if not frame_bytes or len(frame_bytes) > 3 * 1024 * 1024:
        raise HTTPException(413, "Webcam frame is empty or exceeds the 3 MB limit.")
    return await run_in_threadpool(analyze_webcam_frame, session, frame_bytes)


def cctv_status():
    with cctv_lock:
        stream = cctv_stream
    if stream:
        return stream.snapshot()
    return {"status": "not_configured" if not settings.cctv_rtsp_url else "disconnected",
            "error": None, "has_frame": False}


@app.post("/api/cctv/connect")
def connect_cctv(connection: CameraConnection):
    global cctv_stream
    if not settings.cctv_rtsp_url.strip():
        raise HTTPException(503, "Camera address is not configured. Add the camera RTSP URL to the project .env as CCTV_RTSP_URL, then restart the backend.")
    try:
        stream = CameraStream(settings.cctv_rtsp_url, connection.username, connection.password,
                              settings=settings, on_event=record_cctv_incident)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    with cctv_lock:
        previous = cctv_stream
        cctv_stream = stream
    if previous:
        previous.stop()
    stream.start()
    # Give the camera a short chance to return its first frame for useful UI feedback.
    deadline = threading.Event()
    for _ in range(55):
        state = stream.snapshot()
        if state["status"] != "connecting":
            break
        deadline.wait(0.1)
    return stream.snapshot()


@app.post("/api/cctv/disconnect")
def disconnect_cctv():
    global cctv_stream
    with cctv_lock:
        stream, cctv_stream = cctv_stream, None
    if stream:
        stream.stop()
    return {"status": "disconnected", "error": None, "has_frame": False}


@app.get("/api/cctv/status")
def get_cctv_status():
    return cctv_status()


@app.get("/api/cctv/frame")
def cctv_frame():
    with cctv_lock:
        stream = cctv_stream
    frame = stream.frame() if stream else None
    if frame is None:
        raise HTTPException(404, "No camera frame is available yet.")
    return Response(frame, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.post("/api/jobs", status_code=202)
async def create_job(file: UploadFile = File(...)):
    original_name, suffix = validate_video_upload(file.filename or "upload", file.content_type or "")
    job_id = uuid.uuid4().hex
    source = settings.upload_dir / f"{job_id}{suffix}"
    destination = settings.output_dir / f"{job_id}.webm"
    size, limit = 0, settings.max_upload_mb * 1024 * 1024
    try:
        with source.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, f"Video exceeds the {settings.max_upload_mb} MB upload limit.")
                out.write(chunk)
        if size == 0:
            raise HTTPException(400, "The uploaded file is empty.")
        created = datetime.now(timezone.utc).isoformat()
        store.create_job(job_id, original_name, created)
        with preview_lock:
            latest_previews.pop(job_id, None)
        executor.submit(run_job, job_id, source, destination)
        return {"id": job_id, "filename": original_name, "status": "queued", "created_at": created}
    except Exception:
        source.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@app.get("/api/jobs")
def jobs():
    return store.list_jobs()


@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    result = store.get_job(job_id)
    if not result:
        raise HTTPException(404, "Job not found.")
    result["summary"] = json.loads(result["summary"]) if result.get("summary") else None
    result["video_url"] = f"/api/jobs/{job_id}/video" if result["status"] == "completed" else None
    return result


@app.get("/api/jobs/{job_id}/video")
def video(job_id: str):
    result = store.get_job(job_id)
    if not result or result["status"] != "completed" or not result.get("output_path"):
        raise HTTPException(404, "Processed video is not available.")
    path = Path(result["output_path"]).resolve()
    if not path.is_relative_to(settings.output_dir.resolve()) or not path.is_file():
        raise HTTPException(404, "Processed video is not available.")
    is_webm = path.suffix.lower() == ".webm"
    suffix = ".webm" if is_webm else ".mp4"
    media_type = "video/webm" if is_webm else "video/mp4"
    return FileResponse(path, media_type=media_type, filename=f"{job_id}-processed{suffix}")


@app.get("/api/jobs/{job_id}/preview")
def preview(job_id: str):
    result = store.get_job(job_id)
    if not result:
        raise HTTPException(404, "Job not found.")
    with preview_lock:
        frame = latest_previews.get(job_id)
    if frame is None:
        preview_path = settings.output_dir / f"{job_id}-preview.jpg"
        if preview_path.is_file():
            frame = preview_path.read_bytes()
    if frame is None:
        raise HTTPException(404, "The first tracked frame is not ready yet.")
    return Response(frame, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.get("/api/incidents")
def incidents():
    with cctv_incident_lock:
        live = list(cctv_incidents)
    with webcam_lock:
        webcam_live = list(webcam_incidents)
    return sorted([*store.list_incidents(), *live, *webcam_live], key=lambda event: event["created_at"], reverse=True)[:100]
