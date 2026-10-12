# CCTV screen setup

The app provides a dedicated **CCTV LIVE** screen with username and password login fields and a large live video area. The camera target must be configured locally because the login credentials alone do not identify a camera.

1. Find the camera's RTSP address and stream path in its manufacturer app, manual, or NVR settings. The computer running this app must be on the same network, and RTSP must be enabled.
2. Add the address to the ignored local `backend/.env` file:

   ```dotenv
   CCTV_RTSP_URL=rtsp://192.168.1.50:554/your-camera-stream-path
   ```

3. Restart the backend. Open **CCTV LIVE**, enter the camera account username and password, and click **SIGN IN TO CAMERA**. The URL's host, port, and path are configured on the server; the UI deliberately keeps the sign-in form to the two requested credential fields.

Credentials are sent to the local API and kept only in process memory while the RTSP capture is active. They are not persisted or returned. Do not expose an IP camera directly to the public internet. Only connect to cameras you own or are authorized to access.

The current CCTV screen displays the raw live preview. It does not yet run person tracking or drowning detection on the CCTV frames, so CCTV preview does not trigger the drowning buzzer. Uploaded-video analysis remains separate. The feed requires an RTSP-compatible camera and OpenCV's FFmpeg support; USB cameras and vendor-cloud-only feeds are not supported by this connector.
