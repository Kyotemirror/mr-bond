import time

from face_engine import FaceEngine
from sound_engine import SoundEngine
from behavior_engine import BehaviorEngine


class AIDog:
    def __init__(self):
        print("Starting Bond (SAFE MODE)...")

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
        # Behavior (core logic)
        # -----------------------------
        self.behavior = BehaviorEngine(self.face, self.sound)

        # -----------------------------
        # TEMPORARILY DISABLED
        # -----------------------------
        self.voice = None   # VoiceEngine disabled
        self.camera = None  # CameraEngine disabled

        print("Bond running in SAFE MODE (voice/camera off).")

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

                # (voice and camera intentionally skipped)

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
