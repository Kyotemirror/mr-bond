import time

from face_engine import FaceEngine
from sound_engine import SoundEngine
from behavior_engine import BehaviorEngine
from camera_engine import CameraEngine


class AIDog:
    def __init__(self):
        print("Starting Bond (CAMERA TEST MODE)...")

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
        # Camera (ENABLED)
        # -----------------------------
        try:
            self.camera = CameraEngine(self.behavior)
            print("CameraEngine enabled.")
        except Exception as e:
            print("CameraEngine failed to start:", e)
            self.camera = None

        # -----------------------------
        # Voice (DISABLED for now)
        # -----------------------------
        self.voice = None

        print("Bond running with CAMERA enabled, VOICE disabled.")

    # -----------------------------
    # Main loop
    # -----------------------------
    def run(self):
        try:
            while True:
                # Face UI
                if self.face:
                    self.face.update()

                # Behavior
                self.behavior.update()

                # Camera (only native-heavy subsystem enabled)
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
        try:
            if self.camera and hasattr(self.camera, "release"):
                self.camera.release()
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
    dog = AIDog()
    dog.run()
