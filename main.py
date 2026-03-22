import time
import os

from face_engine import FaceEngine
from sound_engine import SoundEngine
from behavior_engine import BehaviorEngine
from voice_engine import VoiceEngine
from camera_engine import CameraEngine


class AIDog:
    def __init__(self):
        print("Starting Bond...")

        # -----------------------------
        # Face (GUI)
        # -----------------------------
        # Assumes you are running locally in a GUI session
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
        # Behavior (central brain)
        # -----------------------------
        self.behavior = BehaviorEngine(self.face, self.sound)

        # -----------------------------
        # Voice (safe initialization)
        # -----------------------------
        try:
            self.voice = VoiceEngine(self.behavior)
            if not getattr(self.voice, "enabled", True):
                print("VoiceEngine disabled (no mic or model issue).")
                self.voice = None
        except Exception as e:
            print("VoiceEngine failed to start:", e)
            self.voice = None

        # -----------------------------
        # Camera (optional)
        # -----------------------------
        try:
            self.camera = CameraEngine(self.behavior)
        except Exception as e:
            print("CameraEngine failed to start:", e)
            self.camera = None

    # -----------------------------
    # Main loop
    # -----------------------------
    def run(self):
        try:
            while True:
                # Face update (GUI)
                if self.face:
                    self.face.update()

                # Behavior update
                self.behavior.update()

                # Voice update (non-blocking; may be None)
                if self.voice:
                    self.voice.update()

                # Camera update (optional)
                if self.camera:
                    self.camera.update()

                time.sleep(0.01)

        except KeyboardInterrupt:
            print("\nStopping Bond...")

        finally:
            self.shutdown()

    # -----------------------------
    # Shutdown sequence
    # -----------------------------
    def shutdown(self):
        # Camera cleanup
        try:
            if self.camera and hasattr(self.camera, "release"):
                self.camera.release()
        except Exception as e:
            print("Camera shutdown error:", e)

        # Voice cleanup
        try:
            if self.voice and hasattr(self.voice, "shutdown"):
                self.voice.shutdown()
        except Exception as e:
            print("Voice shutdown error:", e)

        # Sound cleanup
        try:
            if self.sound and hasattr(self.sound, "stop"):
                self.sound.stop()
        except Exception as e:
            print("Sound shutdown error:", e)

        # Face cleanup
        try:
            if self.face and hasattr(self.face, "shutdown"):
                self.face.shutdown()
        except Exception as e:
            print("Face shutdown error:", e)

        print("Bond stopped cleanly.")


# -----------------------------
# Entry point
# -----------------------------
if __name__ == "__main__":
    dog = AIDog()
    dog.run()
