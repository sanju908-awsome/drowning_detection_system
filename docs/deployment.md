# Deployment configuration

## Render API

The root `render.yaml` defines the FastAPI backend on Render Free. Free services can sleep when idle and use an ephemeral filesystem; local SQLite records, uploads, and processed results can disappear after restarts or redeploys. The bundled detector weights are in `backend/drowning_watch/assets/best.pt`. The free instance has limited memory and CPU, so real-time video inference may be slow or the process may restart under load. The API health endpoint is public; all other API routes require the shared `API_ACCESS_CODE`.

Set these Render environment values:

- `API_ACCESS_CODE`: a strong shared secret entered on the app's access-code screen. Keep it private and do not commit it.
- `FRONTEND_ORIGINS`: exact Vercel origin, e.g. `https://drowning-detection-system-mauve.vercel.app`.
- The Render Free configuration disables pose estimation and does not include a validated temporal risk classifier. The bundled detector is the user's 6 MB YOLO model. Check `/api/health` after deployment and understand that a healthy API response does not mean drowning risk classification is available. This prototype must not be used as the sole drowning-safety measure.

## Vercel frontend

Set `VITE_API_URL` to the public HTTPS backend URL (Render or the authorized Tailscale Funnel endpoint) in Vercel. Redeploy after changing it. The app asks for the shared access code and sends it over HTTPS in the authorization header; use the same private code on the backend and share it only with people you trust.

The webcam feature sends sampled frames from the browser to the configured API for analysis. Tell users where the backend runs and obtain appropriate consent before using cameras.

## Operational limitations

This prototype uses an in-process video worker, SQLite, and temporary local files on Render Free. It does not provide a durable distributed queue, PostgreSQL migrations, object storage, retention controls, or production-grade availability. Validate model availability, resource use, authorization, backups, and alert behavior before any real-world use. Keep trained human supervision and emergency procedures in place.
