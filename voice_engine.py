import json
import queue
import threading
import time

import numpy as np
import sounddevice as sd
from vosk import Model, KaldiRecognizer


class VoiceEngine:
    def __init__(
        self,
        behavior,
        model_path="vosk-model-small-en-us-0.15",
        sample_rate=16000,
        input_device=None,
        blocksize=8000,
        wake_phrase="hey husky",
    ):
        self.behavior = behavior
        self.sample_rate = int(sample_rate)

        # ---- Vosk model ----
        self.model = Model(model_path)

        self.WAKE_PHRASE = wake_phrase.lower().strip()
        self.wake_grammar = json.dumps([self.WAKE_PHRASE, "[unk]"])
        self.cmd_grammar = json.dumps([
            "bark", "woof", "happy", "sad", "hello",
            "good boy", "good dog",
            "quiet", "calm", "angry", "scared", "[unk]"
        ])

        self.rec = KaldiRecognizer(self.model, self.sample_rate, self.wake_grammar)

        # ---- Mode state ----
        self.mode = "SLEEP"
        self.awake_until = 0.0
        self.AWAKE_WINDOW = 4.0

        # Cooldown
        self.last_trigger_time = 0.0
        self.cooldown = 1.0

        # ---- Audio pipeline ----
        self.q = queue.Queue(maxsize=50)
        self.running = True
        self._stop_event = threading.Event()

        # Loudness tracking
        self._utter_rms_sum = 0.0
        self._utter_rms_n = 0

        self.input_device = input_device
        self.blocksize = int(blocksize)
        self._stream = None

        self.audio_thread = threading.Thread(target=self._audio_loop, daemon=True)
        self.asr_thread = threading.Thread(target=self._asr_loop, daemon=True)
        self.audio_thread.start()
        self.asr_thread.start()

        print("VoiceEngine: Offline wake-word + commands ready.")

    # -----------------------------
    # Lifecycle
    # -----------------------------
    def shutdown(self):
        self.running = False
        self._stop_event.set()

        try:
            if self._stream:
                self._stream.close()
        except Exception:
            pass

        try:
            self.q.put_nowait(b"")
        except Exception:
            pass

    # -----------------------------
    # Audio capture
    # -----------------------------
    def _audio_cb(self, indata, frames, time_info, status):
        if not self.running:
            return

        data = bytes(indata)

        # RMS using NumPy (audioop replacement)
        samples = np.frombuffer(data, dtype=np.int16)
        if samples.size:
            rms = np.sqrt(np.mean(samples.astype(np.float32) ** 2))
            self._utter_rms_sum += rms
            self._utter_rms_n += 1

        try:
            self.q.put_nowait(data)
        except queue.Full:
            pass

    def _audio_loop(self):
        try:
            self._stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.blocksize,
                dtype="int16",
                channels=1,
                device=self.input_device,
                callback=self._audio_cb
            )
            self._stream.start()

            while self.running and not self._stop_event.is_set():
                time.sleep(0.05)

        except Exception as e:
            print("VoiceEngine audio error:", e)

        finally:
            try:
                if self._stream:
                    self._stream.close()
            except Exception:
                pass
            self._stream = None

    # -----------------------------
    # ASR loop
    # -----------------------------
    def _asr_loop(self):
        while self.running and not self._stop_event.is_set():
            if self.mode == "AWAKE" and time.monotonic() > self.awake_until:
                self._sleep_mode()

            try:
                data = self.q.get(timeout=0.5)
            except queue.Empty:
                continue

            if not data:
                continue

            if not self.rec.AcceptWaveform(data):
                try:
                    partial = json.loads(self.rec.PartialResult()).get("partial", "").lower()
                except Exception:
                    partial = ""

                if self.mode == "SLEEP" and self.WAKE_PHRASE in partial:
                    self._on_wake()
                continue

            try:
                text = json.loads(self.rec.Result()).get("text", "").lower().strip()
            except Exception:
                text = ""

            if not text:
                self._utter_rms_sum = 0.0
                self._utter_rms_n = 0
                continue

            avg_rms = self._utter_rms_sum / max(1, self._utter_rms_n)
            self._utter_rms_sum = 0.0
            self._utter_rms_n = 0

            if self.mode == "SLEEP":
                if self.WAKE_PHRASE in text:
                    self._on_wake()
                continue

            self._route_command(text, avg_rms)

    # -----------------------------
    # Wake / sleep
    # -----------------------------
    def _on_wake(self):
        now = time.monotonic()
        if now - self.last_trigger_time < self.cooldown:
            return

        self.last_trigger_time = now
        def update(self):
    pass
