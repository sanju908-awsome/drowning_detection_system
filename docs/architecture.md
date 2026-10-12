# Architecture

## Implemented local flow

`uploaded video or RTSP stream → OpenCV frames → Ultralytics YOLO detector → DeepSORT tracker → per-track motion-v2 features → experimental Random Forest → annotated video/live CCTV frame + alert events`

The React/Vite dashboard uploads video, previews completed output, displays the analyzed RTSP camera stream, and polls for alert events. CCTV analysis runs in the camera stream worker; uploaded-video analysis runs in the video worker. A missing or incompatible classifier yields **UNASSESSED**.

## Current limits

This is a local research prototype, not a production deployment. CCTV stream intake, user authentication/authorization, PostgreSQL, migrations, object storage, notifications, sound alerts, and Vercel/worker deployment are not implemented. SQLite is the only database adapter. The in-process worker loses queued work on restart. Upload/output storage is local and has no retention scheduler. Large files are size-capped but video duration and decoded pixel limits are not yet capped. Put the service behind a trusted local network; do not expose it publicly as-is.

## Safety boundary

The installed experimental RF model classifies per-track motion windows as SAFE or EMERGENCY in uploaded-video and RTSP CCTV analysis. Its training labels came from public CVAT box annotations, not detector output; evaluation is source-video-grouped but shows low EMERGENCY precision. It does not predict WARNING. The interface and overlay state that the system does not replace trained lifeguards or emergency response.
