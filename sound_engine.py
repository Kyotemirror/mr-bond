import time
import threading
from playsound import playsound

class SoundEngine:
    def __init__(self, sound_file="bark.wav", cooldown=0.6, allow_overlap=False):
        self.sound_file = sound_file
        self.cooldown = cooldown
        self.allow_overlap = allow_overlap

        self._last_play = 0.0
        self._lock = threading.Lock()
        self._playing = False

    def play(self):
        now = time.monotonic()

        with self._lock:
            # Cooldown guard
            if now - self._last_play < self.cooldown:
                return

            # Overlap guard
            if (not self.allow_overlap) and self._playing:
                return

            self._last_play = now
            self._playing = True

        # Always play in a thread so the dog loop never blocks
        t = threading.Thread(target=self._play_worker, daemon=True)
        t.start()

    def _play_worker(self):
        try:
            # Some playsound builds ignore block=False; thread makes it safe either way
            try:
                playsound(self.sound_file, block=True)
            except TypeError:
                # If block arg isn’t supported in this environment
                playsound(self.sound_file)
        except Exception as e:
            print("Sound error:", e)
        finally:
            with self._lock:
                self._playing = False

    def stop(self):
        # playsound generally can't stop mid-playback.
        # We keep this for API compatibility.
        pass