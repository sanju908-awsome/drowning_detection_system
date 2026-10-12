# Deployment status

No deployment has been performed. This build runs locally. The frontend is a Vite/React project and can be built for static hosting, but production backend deployment is not ready: it uses an in-process worker, local SQLite and local files; it lacks authentication, durable job queues, PostgreSQL migrations, object storage, retention controls, and a secured camera relay. Continuous video inference does not belong in Vercel serverless functions.

For a later deployment, provision a persistent Python worker/API host with adequate CPU/GPU and disk, PostgreSQL, object storage, HTTPS, authentication/authorization, CORS allowlisting, secret management, health checks, worker restarts, backup and retention policies. Deploy the frontend to Vercel only after API access controls and CORS are configured. No endpoint should be represented as online until deployed and checked. Ultralytics AGPL-3.0 and model licensing terms also need review.
