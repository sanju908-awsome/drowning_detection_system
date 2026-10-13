# Deployment configuration

## Render API

The root `render.yaml` defines the FastAPI backend on Render Free. Free services can sleep when idle and use an ephemeral filesystem; local SQLite records, uploads, and processed results can disappear after restarts or redeploys. The bundled detector weights are in `backend/drowning_watch/assets/best.pt`. The free instance has limited memory and CPU, so real-time video inference may be slow or the process may restart under load. The API health endpoint is public; all other API routes require a valid Firebase Authentication ID token.

Set these Render environment values:

- `FIREBASE_PROJECT_ID`: Firebase project ID used by the web app. The backend verifies Firebase ID tokens against this project; never commit a service-account private key.
- `FIREBASE_ALLOWED_EMAILS`: comma-separated allowlist of email addresses permitted to use the API. Keep it empty until specific users are approved; empty means protected routes deny everyone.
- `FRONTEND_ORIGINS`: exact Vercel origin, e.g. `https://drowning-detection-system-mauve.vercel.app`.
- The Render Free configuration disables pose estimation and does not include a validated temporal risk classifier. The bundled detector is the user's 6 MB YOLO model. Check `/api/health` after deployment and understand that a healthy API response does not mean drowning risk classification is available. This prototype must not be used as the sole drowning-safety measure.

## Firebase and Vercel

In Firebase Console, enable **Authentication → Email/Password**. People can register through the web app, but registration alone does not grant monitoring access. An unapproved account sees a request-access screen; the account owner reviews the request and adds approved addresses to `FIREBASE_ALLOWED_EMAILS` in Render. Do not distribute a shared access code. Add the Vercel hostname to Authentication's authorized domains if required for your Firebase sign-in settings. The client needs the Firebase web app values in Vercel:

- `VITE_FIREBASE_API_KEY`
- `VITE_FIREBASE_AUTH_DOMAIN`
- `VITE_FIREBASE_PROJECT_ID`
- `VITE_FIREBASE_APP_ID`
- `VITE_API_URL`: the Render service's HTTPS URL

The Firebase web config is public client configuration; never put a Firebase service-account key in Vercel or frontend code. Set `VITE_API_URL` to the Render API URL only after the service exists. Redeploy the Vercel frontend after changing any `VITE_` variables.

The webcam feature sends sampled frames from the browser to the configured API for analysis. Tell users where the backend runs and obtain appropriate consent before using cameras.

## Operational limitations

This prototype uses an in-process video worker, SQLite, and temporary local files on Render Free. It does not provide a durable distributed queue, PostgreSQL migrations, object storage, retention controls, or production-grade availability. Validate model availability, resource use, authorization, backups, and alert behavior before any real-world use. Keep trained human supervision and emergency procedures in place.
