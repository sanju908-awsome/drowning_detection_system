"""In-memory RTSP camera preview; credentials are never persisted or returned."""
from __future__ import annotations

import threading
import time
import os
from urllib.parse import quote, urlsplit, urlunsplit
from typing import Callable

import cv2

from .settings import Settings


class CameraStream:
    def __init__(self, stream_url: str, username: str, password: str,
                 settings: Settings, on_event: Callable[[dict], None] | None = None):
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
        self._settings = settings
        self._on_event = on_event
        self._analysis_error: str | None = None
        self._risk_state = "UNASSESSED"
        self._track_count = 0
        self._analyzer = None
        self._thread = threading.Thread(target=self._run, name="cctv-preview", daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)

    def snapshot(self):
        with self._lock:
            return {"status": self._status, "error": self._error, "has_frame": self._frame is not None,
                    "analysis_error": self._analysis_error, "risk_state": self._risk_state,
                    "track_count": self._track_count}

    def frame(self):
        with self._lock:
            return self._frame

    def _set(self, status: str, error: str | None = None):
        with self._lock:
            self._status, self._error = status, error

    def _run(self):
        capture = None
        try:
            try:
                from .live_analysis import LiveRiskAnalyzer
                self._analyzer = LiveRiskAnalyzer(self._settings)
            except Exception as exc:
                with self._lock:
                    self._analysis_error = f"Live analysis unavailable ({type(exc).__name__})."
            # FFmpeg honors these options for RTSP cameras, so a wrong address
            # or unreachable Wi-Fi camera does not leave the UI hanging.
            os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
            params = [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
                      cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000]
            capture = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG, params)
            if not capture.isOpened():
                self._set("error", "Could not open the RTSP stream. Check the camera IP, RTSP path, Wi-Fi network, and login.")
                return
            started_at = time.monotonic()
            while not self._stop.is_set():
                ok, image = capture.read()
                if not ok:
                    self._set("error", "The camera stream stopped sending frames. Check the camera and network.")
                    break
                if self._analyzer is not None:
                    try:
                        image, events = self._analyzer.process(image, time.monotonic() - started_at)
                        with self._lock:
                            self._track_count = self._analyzer.track_count
                            self._risk_state = self._analyzer.latest_state
                        if self._on_event:
                            for event in events:
                                self._on_event(event)
                    except Exception as exc:
                        with self._lock:
                            self._analysis_error = f"Live analysis stopped ({type(exc).__name__})."
                        self._analyzer = None
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

