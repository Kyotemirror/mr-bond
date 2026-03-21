import json
import queue
import threading
import time
import audioop

import sounddevice as sd
from vosk import Model, KaldiRecognizer


class VoiceEngine:
    def __init__(
        self,
        behavior,
        model_path="vosk-model-small-en-us-0.15",
        sample_rate=16000,
        input_device=None,          # None = default input device
        detect_blocksize=8000,
        wake_phrase="hey husky",
    ):
        self.behavior = behavior
        self.sample_rate = int(sample_rate)

        # ---- Vosk model + recognizer ----
        self.model = Model(model_path)

        # Grammars constrain recognition
        self.WAKE_PHRASE = wake_phrase.lower().strip()
        self.wake_grammar = json.dumps([self.WAKE_PHRASE, "[unk]"])
        self.cmd_grammar = json.dumps([
            "bark", "woof", "happy", "sad", "hello", "good boy", "good dog",
            "quiet", "calm", "angry", "scared", "[unk]"
        ])

        self.rec = KaldiRecognizer(self.model, self.sample_rate, self.wake_grammar)

        # ---- Mode state ----
        self.mode = "SLEEP"
        self.awake_until = 0.0
        self.AWAKE_WINDOW = 4.0  # seconds after wake word to accept commands

        # ---- Cooldowns ----
        self.last_trigger_time = 0.0
        self.cooldown = 1.0

        # ---- Audio pipeline ----
        self.q = queue.Queue(maxsize=50)
        self.running = True
        self._stop_event = threading.Event()

        # Loudness tracking (voice→emotion intensity)
        self._utter_rms_sum = 0.0
        self._utter_rms_n = 0

        # Audio config
        self.input_device = input_device
        self.detect_blocksize = int(detect_blocksize)

        # Stream handle (so shutdown can close it)
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

        # Closing the stream helps unblock audio thread immediately
        try:
            if self._stream is not None:
                self._stream.close()
        except Exception:
            pass

        # Best-effort: unblock ASR thread if waiting on queue
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

        # RawInputStream provides bytes-like buffers
        data = bytes(indata)

        # Track loudness from raw int16 mono audio bytes
        try:
            rms = audioop.rms(data, 2)  # width=2 bytes (int16)
            self._utter_rms_sum += rms
            self._utter_rms_n += 1
        except Exception:
            pass

        try:
            self.q.put_nowait(data)
        except queue.Full:
            pass  # drop if overloaded

    def _audio_loop(self):
        try:
            self._stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.detect_blocksize,
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
                if self._stream is not None:
                    self._stream.close()
            except Exception:
                pass
            self._stream = None

    # -----------------------------
    # ASR loop
    # -----------------------------
    def _asr_loop(self):
        while self.running and not self._stop_event.is_set():
            # If we're awake but time window passed without a final command, sleep again
            if self.mode == "AWAKE" and time.monotonic() > self.awake_until:
                self._sleep_mode()

            try:
                data = self.q.get(timeout=0.5)
            except queue.Empty:
                continue

            if not data:
                continue

            # Partial results are useful for fast wake-word spotting
            if not self.rec.AcceptWaveform(data):
                try:
                    partial = json.loads(self.rec.PartialResult()).get("partial", "").lower()
                except Exception:
                    partial = ""

                if self.mode == "SLEEP" and self.WAKE_PHRASE in partial:
                    self._on_wake()
                continue

            # Final result for completed phrase
            try:
                text = json.loads(self.rec.Result()).get("text", "").lower().strip()
            except Exception:
                text = ""

            if not text:
                # reset loudness accumulation for the next utterance
                self._utter_rms_sum = 0.0
                self._utter_rms_n = 0
                continue

            avg_rms = (self._utter_rms_sum / max(1, self._utter_rms_n))
            self._utter_rms_sum = 0.0
            self._utter_rms_n = 0

            if self.mode == "SLEEP":
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

        # Switch recognizer grammar to command set
        try:
            self.rec.SetGrammar(self.cmd_grammar)
        except Exception as e:
            print("VoiceEngine grammar switch error:", e)

        # “I’m listening” response
        self.behavior.happy()

    # -----------------------------
    # Voice → emotion mapping
    # -----------------------------
    def _route_command(self, text, avg_rms):
        now = time.monotonic()
        if now > self.awake_until:
            self._sleep_mode()
            return

        # Intensity buckets from mic loudness
        if avg_rms > 2500:
            intensity = "high"
        elif avg_rms > 1200:
            intensity = "mid"
        else:
            intensity = "low"

        print(f"Heard: '{text}' (intensity={intensity})")

        # Commands
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
            # Intensity-only fallback
            if intensity == "high":
                self.behavior.bark()
            elif intensity == "mid":
                self.behavior.happy()
            else:
                self.behavior.sad()

        # After one command, sleep again (your original behavior)
        self._sleep_mode()

    def _sleep_mode(self):
        self.mode = "SLEEP"
        try:
            self.rec.SetGrammar(self.wake_grammar)
        except Exception as e:
            print("VoiceEngine grammar switch error:", e)

    # Update loop is non-blocking (threads do the work)
    def update(self):
        pass
