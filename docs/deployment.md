# Deployment status

No deployment has been performed. The Vite frontend now has a Vercel SPA rewrite and expects `VITE_API_URL` to point to the deployed API. It uses `http://localhost:8000` only during local development. The frontend can be deployed as a static site, but the complete monitoring service is not ready for production: it uses an in-process worker, local SQLite and local files; it lacks authentication, durable job queues, PostgreSQL migrations, object storage, retention controls, and a secured camera relay. Continuous video inference does not belong in Vercel serverless functions.

To deploy the frontend, import this Git repository into Vercel, set the project root directory to `frontend`, set `VITE_API_URL` to the HTTPS URL of the deployed API, and deploy. The rewrite in `frontend/vercel.json` supports client-side routes. The site will not analyze videos or connect to cameras until that API exists and allows the Vercel origin through CORS.

For a complete deployment, provision a persistent Python worker/API host with adequate CPU/GPU and disk, PostgreSQL, object storage, HTTPS, authentication/authorization, CORS allowlisting, secret management, health checks, worker restarts, backup and retention policies. No endpoint should be represented as online until deployed and checked. Ultralytics AGPL-3.0 and model licensing terms also need review.
