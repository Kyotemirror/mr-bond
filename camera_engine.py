import time
import cv2

class CameraEngine:
    def __init__(self, behavior, cam_index=0, detect_hz=10):
        self.behavior = behavior

        self.camera = cv2.VideoCapture(cam_index)
        # Optional: request smaller capture size (varies by camera/driver)
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

        self.face_cooldown = 3.0
        self.last_face_time = 0.0

        # Throttle face detection frequency
        self.detect_dt = 1.0 / float(detect_hz)
        self._next_detect_time = time.monotonic()

    def update(self):
        if not self.camera.isOpened():
            return

        now = time.monotonic()
        if now < self._next_detect_time:
            return
        self._next_detect_time = now + self.detect_dt

        ret, frame = self.camera.read()
        if not ret or frame is None:
            return

        # Downscale for speed (huge win)
        small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.2,
            minNeighbors=5,
            minSize=(60, 60)
        )

        if len(faces) > 0 and (now - self.last_face_time) > self.face_cooldown:
            # Face detected: react
            self.behavior.happy()
            self.last_face_time = now

    def release(self):
        if self.camera is not None and self.camera.isOpened():
            self.camera.release()