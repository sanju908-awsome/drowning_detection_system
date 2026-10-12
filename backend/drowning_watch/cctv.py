"""In-memory RTSP camera preview; credentials are never persisted or returned."""
from __future__ import annotations

import threading
import time
import os
from urllib.parse import quote, urlsplit, urlunsplit

import cv2


class CameraStream:
    def __init__(self, stream_url: str, username: str, password: str):
        parts = urlsplit(stream_url.strip())
        if parts.scheme not in {"rtsp", "rtsps"} or not parts.hostname:
            raise ValueError("Camera address must be an RTSP URL with a host and stream path.")
        host = parts.hostname
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        netloc = host + (f":{parts.port}" if parts.port else "")
        if username:
            netloc = f"{quote(username, safe='')}:{quote(password, safe='')}@{netloc}"
        self.url = urlunsplit((parts.scheme, netloc, parts.path, parts.query, ""))
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._frame: bytes | None = None
        self._status = "connecting"
        self._error: str | None = None
        self._thread = threading.Thread(target=self._run, name="cctv-preview", daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)

    def snapshot(self):
        with self._lock:
            return {"status": self._status, "error": self._error, "has_frame": self._frame is not None}

    def frame(self):
        with self._lock:
            return self._frame

    def _set(self, status: str, error: str | None = None):
        with self._lock:
            self._status, self._error = status, error

    def _run(self):
        capture = None
        try:
            # FFmpeg honors these options for RTSP cameras, so a wrong address
            # or unreachable Wi-Fi camera does not leave the UI hanging.
            os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
            params = [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
                      cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000]
            capture = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG, params)
            if not capture.isOpened():
                self._set("error", "Could not open the RTSP stream. Check the camera IP, RTSP path, Wi-Fi network, and login.")
                return
            while not self._stop.is_set():
                ok, image = capture.read()
                if not ok:
                    self._set("error", "The camera stream stopped sending frames. Check the camera and network.")
                    break
                ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 82])
                if ok:
                    with self._lock:
                        self._frame = encoded.tobytes()
                        self._status, self._error = "connected", None
                time.sleep(0.01)
        except Exception as exc:
            self._set("error", f"Camera connection failed ({type(exc).__name__}). Check RTSP settings.")
        finally:
            if capture is not None:
                capture.release()
            if self._stop.is_set():
                self._set("disconnected")

