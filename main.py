import time

from face_engine import FaceEngine
from sound_engine import SoundEngine
from behavior_engine import BehaviorEngine
from voice_engine import VoiceEngine
from camera_engine import CameraEngine


class AIDog:
    def __init__(self):
        # Boot identity
        print("Starting Bond...")

        # Engines
        self.face = FaceEngine()
        self.sound = SoundEngine("bark.wav")
        self.behavior = BehaviorEngine(self.face, self.sound)
        self.voice = VoiceEngine(self.behavior)
        self.camera = CameraEngine(self.behavior)

    def run(self):
        try:
            while True:
                # Update engines (keeping your current style/order)
                self.face.update()
                self.behavior.update()
                self.voice.update()
                self.camera.update()

                time.sleep(0.01)  # smooth loop

        except KeyboardInterrupt:
            # Shutdown identity
            print("\nStopping Bond...")

        finally:
            # Release/cleanup safely if engines expose methods
            try:
                if hasattr(self.camera, "release"):
                    self.camera.release()
            except Exception as e:
                print("Camera release error:", e)

            try:
                # If you later add voice shutdown threads, this will work automatically
                if hasattr(self.voice, "shutdown"):
                    self.voice.shutdown()
            except Exception as e:
                print("Voice shutdown error:", e)

            try:
                # If you add stop later, no harm now
                if hasattr(self.sound, "stop"):
                    self.sound.stop()
            except Exception as e:
                print("Sound stop error:", e)

            try:
                # If you later add a clean close to FaceEngine (tk destroy), it’ll be used
                if hasattr(self.face, "shutdown"):
                    self.face.shutdown()
                elif hasattr(self.face, "close"):
                    self.face.close()
            except Exception as e:
                print("Face shutdown error:", e)

            # Final lifecycle message
            print("Bond stopped cleanly.")


if __name__ == "__main__":
    dog = AIDog()
    dog.run()