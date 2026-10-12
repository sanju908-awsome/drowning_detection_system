# Camera setup

Live CCTV/RTSP support is not implemented; `/api/health` reports `cctv_enabled: false`. Do not place camera credentials in browser settings, frontend environment variables, repository files, or logs. For future work, prefer an on-premise worker that reads a camera from a protected network or through an authenticated relay/VPN. Verify permissions and retention rules before recording pool users. Never expose a private camera directly to the public internet for this prototype.
