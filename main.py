import time
import sys
import threading
import os

from face_engine import FaceEngine
from sound_engine import SoundEngine
from behavior_engine import BehaviorEngine
from camera_engine import CameraEngine
from bond_ipc_server import BondIPCServer


class AIDog:
    def __init__(self):
        print("Starting Bond (CORE MODE — NO VOICE)...")
        print("Press Ctrl+Q to quit Bond")

        # -----------------------------
        # Face (fullscreen UI)
        # -----------------------------
        self.face = FaceEngine(
            width=480,
            height=320,
            fullscreen=True
        )

        # -----------------------------
        # Sound
        # -----------------------------
        self.sound = SoundEngine("bark.wav")

        # -----------------------------
        # Behavior (core brain)
        # -----------------------------
        self.behavior = BehaviorEngine(self.face, self.sound)

        # -----------------------------
        # Camera (USB webcam)
        # -----------------------------
        try:
            self.camera = CameraEngine(self.behavior)
            print("CameraEngine enabled.")
        except Exception as e:
            print("CameraEngine failed to start:", e)
            self.camera = None

        # -----------------------------
        # IPC (external voice)
        # -----------------------------
        self.ipc = BondIPCServer(self.handle_voice_message)
        self.ipc.start()

        # -----------------------------
        # Keyboard kill listener
        # -----------------------------
        threading.Thread(
            target=self._keyboard_kill_listener,
            daemon=True
        ).start()

        print("Bond running with FACE + CAMERA (VOICE EXTERNAL).")

    # -----------------------------
    # IPC handler
    # -----------------------------
    def handle_voice_message(self, msg: dict):
        msg_type = msg.get("type")

        if msg_type == "wake":
            self.behavior.happy()

        elif msg_type == "cmd":
            cmd = (msg.get("cmd") or "").lower()

            if cmd in ("bark", "woof"):
                self.behavior.bark()
            elif cmd in ("happy", "hello", "good boy", "good dog"):
                self.behavior.happy()
            elif cmd in ("sad", "scared"):
                self.behavior.sad()
            elif cmd in ("quiet", "calm"):
                self.behavior.idle()

    # -----------------------------
    # Keyboard kill (Ctrl+Q)
    # -----------------------------
    def _keyboard_kill_listener(self):
        while True:
            ch = sys.stdin.read(1)
            if ch == "\x11":  # Ctrl+Q
                print("\nCtrl+Q pressed — shutting down Bond")
                self.shutdown()
                os._exit(0)

    # -----------------------------
    # Main loop
    # -----------------------------
    def run(self):
        try:
            while True:
                if self.face:
                    self.face.update()

                self.behavior.update()

                if self.camera:
                    self.camera.update()

                time.sleep(0.01)

        except KeyboardInterrupt:
            print("\nStopping Bond...")

        finally:
            self.shutdown()

    # -----------------------------
    # Shutdown
    # -----------------------------
    def shutdown(self):
        # Kill voice service if running
        try:
            os.system("pkill -f voice_service.py")
        except Exception:
            pass

        try:
            if self.camera and hasattr(self.camera, "release"):
                self.camera.release()
        except Exception:
            pass

        try:
            if hasattr(self, "ipc"):
                self.ipc.stop()
        except Exception:
            pass

        try:
            if self.sound and hasattr(self.sound, "stop"):
                self.sound.stop()
        except Exception:
            pass

        try:
            if self.face and hasattr(self.face, "shutdown"):
                self.face.shutdown()
        except Exception:
            pass

        print("Bond stopped cleanly.")


if __name__ == "__main__":
