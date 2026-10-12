import json
import mimetypes
import uuid
import threading
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

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
@asynccontextmanager
async def lifespan(_app):
    store.initialize()
    yield


app = FastAPI(title="Drowning Watch Research Prototype", version="0.1.0", lifespan=lifespan,
              description="Safety-support research prototype. Never use as a substitute for a lifeguard.")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


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
            "cctv_enabled": False, "warning": "This prototype is not a substitute for trained lifeguards or emergency procedures."}


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
    if not store.get_job(job_id):
        raise HTTPException(404, "Job not found.")
    with preview_lock:
        frame = latest_previews.get(job_id)
    if frame is None:
        raise HTTPException(404, "The first tracked frame is not ready yet.")
    return Response(frame, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.get("/api/incidents")
def incidents():
    return store.list_incidents()
