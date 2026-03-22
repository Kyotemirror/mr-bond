import time

from face_engine import FaceEngine
from sound_engine import SoundEngine
from behavior_engine import BehaviorEngine
from voice_engine import VoiceEngine


class AIDog:
    def __init__(self):
        print("Starting Bond (VOICE TEST MODE)...")

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
        # Voice (ENABLED)
        # IMPORTANT: pass a real mic index if you know it
        # -----------------------------
        try:
            self.voice = VoiceEngine(
                self.behavior,
                # input_device=2,   # <-- uncomment & set if needed
            )
            if not getattr(self.voice, "enabled", True):
                print("VoiceEngine disabled itself (no mic or model issue).")
                self.voice = None
            else:
                print("VoiceEngine enabled.")
        except Exception as e:
            print("VoiceEngine failed to start:", e)
            self.voice = None

        # -----------------------------
        # Camera (DISABLED for voice test)
        # -----------------------------
        self.camera = None

        print("Bond running with VOICE enabled, CAMERA disabled.")

    # -----------------------------
    # Main loop
    # -----------------------------
    def run(self):
        try:
            while True:
                if self.face:
                    self.face.update()

                self.behavior.update()

                if self.voice:
                    self.voice.update()

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
            if self.voice and hasattr(self.voice, "shutdown"):
                self.voice.shutdown()
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
