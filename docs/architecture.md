# Architecture

## Implemented local flow

`video upload → FastAPI job queue → OpenCV frame reader → Ultralytics YOLO detector → DeepSORT adapter → optional MediaPipe pose → per-track motion-v1 features → optional Random Forest → annotated WebM + SQLite job/incident rows`

The React/Vite dashboard uploads video, polls jobs, previews completed output, and lists persisted jobs and model-generated warning/emergency incidents. Inference runs in a single in-process worker thread. The flow and UI explicitly show **UNASSESSED** if the temporal classifier is missing or incompatible.

## Current limits

This is a local research prototype, not a production deployment. CCTV stream intake, user authentication/authorization, PostgreSQL, migrations, object storage, notifications, sound alerts, and Vercel/worker deployment are not implemented. SQLite is the only database adapter. The in-process worker loses queued work on restart. Upload/output storage is local and has no retention scheduler. Large files are size-capped but video duration and decoded pixel limits are not yet capped. Put the service behind a trusted local network; do not expose it publicly as-is.

## Safety boundary

Frame-level classes and motion features do not establish a drowning event. No RF model or temporal labels are provided, so all analyzed tracks report UNASSESSED by default. The interface and overlay state that the system does not replace trained lifeguards or emergency response.
