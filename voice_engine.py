import json
import queue
import threading
import time
import audioop

import sounddevice as sd
from vosk import Model, KaldiRecognizer

class VoiceEngine:
    def __init__(self, behavior, model_path="vosk-model-small-en-us-0.15"):
        self.behavior = behavior
        self.sample_rate = 16000

        # Vosk model + recognizer
        self.model = Model(model_path)

        # Two grammars (JSON lists). Grammar constrains recognition. [3](https://github.com/alphacep/vosk-api/blob/master/python/example/test_words.py)[5](https://github.com/alphacep/vosk-api/issues/878)
        self.WAKE_PHRASE = "hey husky"
        self.wake_grammar = json.dumps([self.WAKE_PHRASE, "[unk]"])
        self.cmd_grammar = json.dumps([
            "bark", "woof", "happy", "sad", "hello", "good boy", "good dog",
            "quiet", "calm", "angry", "scared", "[unk]"
        ])

        self.rec = KaldiRecognizer(self.model, self.sample_rate, self.wake_grammar)

        # Mode state
        self.mode = "SLEEP"
        self.awake_until = 0.0
        self.AWAKE_WINDOW = 4.0  # seconds after wake word to accept commands

        # Cooldowns to prevent spam
        self.last_trigger_time = 0.0
        self.cooldown = 1.0

        # Audio pipeline
        self.q = queue.Queue(maxsize=50)
        self.running = True

        # Loudness tracking (for voice→emotion intensity)
        self._utter_rms_sum = 0.0
        self._utter_rms_n = 0

        self.audio_thread = threading.Thread(target=self._audio_loop, daemon=True)
        self.asr_thread = threading.Thread(target=self._asr_loop, daemon=True)
        self.audio_thread.start()
        self.asr_thread.start()

        print("VoiceEngine: Offline wake-word + commands ready.")

    def shutdown(self):
        self.running = False

    # -----------------------------
    # Audio capture
    # -----------------------------
    def _audio_cb(self, indata, frames, time_info, status):
        if not self.running:
            return
        data = bytes(indata)
        # Track loudness from raw int16 mono audio bytes
        rms = audioop.rms(data, 2)  # width=2 bytes (int16)
        self._utter_rms_sum += rms
        self._utter_rms_n += 1

        try:
            self.q.put_nowait(data)
        except queue.Full:
            pass  # drop if overloaded

    def _audio_loop(self):
        with sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=8000,
            dtype="int16",
            channels=1,
            callback=self._audio_cb
        ):
            while self.running:
                time.sleep(0.05)

    # -----------------------------
    # ASR loop
    # -----------------------------
    def _asr_loop(self):
        while self.running:
            try:
                data = self.q.get(timeout=0.5)
            except queue.Empty:
                continue

            # Partial results are useful for fast wake-word spotting [6](https://stackoverflow.com/questions/69173800/how-to-set-a-wake-up-word-for-an-virtual-assistant-using-vosk-offline-speech-rec)
            if not self.rec.AcceptWaveform(data):
                partial = json.loads(self.rec.PartialResult()).get("partial", "").lower()
                if self.mode == "SLEEP" and self.WAKE_PHRASE in partial:
                    self._on_wake()
                continue

            # Final result for completed phrase
            text = json.loads(self.rec.Result()).get("text", "").lower().strip()
            if not text:
                # reset loudness accumulation for the next utterance
                self._utter_rms_sum = 0.0
                self._utter_rms_n = 0
                continue

            avg_rms = (self._utter_rms_sum / max(1, self._utter_rms_n))
            self._utter_rms_sum = 0.0
            self._utter_rms_n = 0

            if self.mode == "SLEEP":
                # Sometimes wake phrase lands in final result too
                if self.WAKE_PHRASE in text:
                    self._on_wake()
                continue

            # Command mode
            self._route_command(text, avg_rms)

    def _on_wake(self):
        now = time.monotonic()
        if now - self.last_trigger_time < self.cooldown:
            return
        self.last_trigger_time = now

        self.mode = "AWAKE"
        self.awake_until = now + self.AWAKE_WINDOW

        # Switch recognizer grammar to command set at runtime [3](https://github.com/alphacep/vosk-api/blob/master/python/example/test_words.py)[4](https://deepwiki.com/alphacep/vosk-api/5-usage-examples)
        self.rec.SetGrammar(self.cmd_grammar)

        # Little “I’m listening” response
        self.behavior.happy()

    # -----------------------------
    # Voice → emotion mapping (text + intensity)
    # -----------------------------
    def _route_command(self, text, avg_rms):
        now = time.monotonic()
        if now > self.awake_until:
            self._sleep_mode()
            return

        # Intensity buckets from mic loudness (tweak thresholds to taste)
        # avg_rms varies by mic; these are simple starter thresholds.
        if avg_rms > 2500:
            intensity = "high"
        elif avg_rms > 1200:
            intensity = "mid"
        else:
            intensity = "low"

        print(f"Heard: '{text}' (intensity={intensity})")

        # --- Command keywords (explicit mapping) ---
        if "bark" in text or "woof" in text:
            self.behavior.bark()
        elif "happy" in text or "hello" in text or "good boy" in text or "good dog" in text:
            self.behavior.happy()
        elif "sad" in text or "scared" in text:
            self.behavior.sad()
        elif "angry" in text:
            self.behavior.bark()  # or add a dedicated angry action later
        elif "quiet" in text or "calm" in text:
            self.behavior.idle()
        else:
            # --- Intensity-only fallback (voice→emotion) ---
            if intensity == "high":
                self.behavior.bark()
            elif intensity == "mid":
                self.behavior.happy()
            else:
                self.behavior.sad()

        # After one command, go back to sleep quickly (optional)
        self._sleep_mode()

    def _sleep_mode(self):
        self.mode = "SLEEP"
        self.rec.SetGrammar(self.wake_grammar)  # grammar swap supported [3](https://github.com/alphacep/vosk-api/blob/master/python/example/test_words.py)[4](https://deepwiki.com/alphacep/vosk-api/5-usage-examples)

    # Update loop is non-blocking
    def update(self):
        pass