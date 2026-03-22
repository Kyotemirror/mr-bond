import json
import os
import queue
import threading
import time

import numpy as np
import sounddevice as sd
from vosk import Model, KaldiRecognizer, SetLogLevel


class VoiceEngine:
    """
    Stable offline wake-word + command recognition using Vosk.

    Key change vs earlier versions:
      - NO runtime SetGrammar() calls (avoids Kaldi abort on some systems)
      - Two recognizers:
          * wake_rec: constrained to wake phrase
          * cmd_rec: constrained to command phrases
      - We switch which recognizer receives audio after wake is detected.

    Python 3.13 safe:
      - Uses NumPy for RMS (no audioop)
    """

    def __init__(
        self,
        behavior,
        model_path="vosk-model-small-en-us-0.15",
        sample_rate=16000,
        input_device=3,           # ✅ your USB webcam mic
        blocksize=4096,
        wake_phrase="hey husky",
        awake_window=4.0,
        cooldown=1.0,
        enable_logs=True,
        vosk_log_level=-1,        # -1 quiet, 0.. higher = more logs
    ):
        self.behavior = behavior
        self.sample_rate = int(sample_rate)
        self.input_device = input_device
        self.blocksize = int(blocksize)
        self.enable_logs = enable_logs

        # Quiet Vosk/Kaldi logs unless debugging
        try:
            SetLogLevel(vosk_log_level)
        except Exception:
            pass

        # Paths
        self.model_path = os.path.abspath(model_path)

        # Mode state
        self.WAKE_PHRASE = wake_phrase.lower().strip()
        self.mode = "SLEEP"
        self.awake_until = 0.0
        self.AWAKE_WINDOW = float(awake_window)
        self.last_trigger_time = 0.0
        self.cooldown = float(cooldown)

        # Grammars (JSON arrays)
        self.wake_grammar = json.dumps([self.WAKE_PHRASE, "[unk]"])
        self.cmd_grammar = json.dumps([
            "bark", "woof", "happy", "sad", "hello", "good boy", "good dog",
            "quiet", "calm", "angry", "scared", "[unk]"
        ])

        # Runtime
        self.running = True
        self.enabled = True
        self._stop_event = threading.Event()

        # Audio queue
        self.q = queue.Queue(maxsize=120)

        # RMS tracking
        self._utter_rms_sum = 0.0
        self._utter_rms_n = 0

        # Load model
        if not os.path.isdir(self.model_path):
            self._log(f"VoiceEngine: model folder not found: {self.model_path}")
            self.enabled = False
            return

        try:
            self.model = Model(self.model_path)
        except Exception as e:
            self._log(f"VoiceEngine: failed to load model: {e}")
            self.enabled = False
            return

        # Two recognizers (created once; we can recreate cmd_rec on wake to reset state)
        self.wake_rec = KaldiRecognizer(self.model, self.sample_rate, self.wake_grammar)
        self.cmd_rec = None  # created on wake
        self.active_rec = self.wake_rec

        # Stream handle
        self._stream = None

        # Threads
        self.audio_thread = threading.Thread(target=self._audio_loop, daemon=True)
        self.asr_thread = threading.Thread(target=self._asr_loop, daemon=True)
        self.audio_thread.start()
        self.asr_thread.start()

        self._log("VoiceEngine: Ready (wake-word + commands).")

    # -----------------------------
    # helpers
    # -----------------------------
    def _log(self, msg):
        if self.enable_logs:
            print(msg)

    def shutdown(self):
        self.running = False
        self._stop_event.set()
        try:
            if self._stream is not None:
                self._stream.close()
        except Exception:
            pass
        # Unblock ASR thread
        try:
            self.q.put_nowait(b"")
        except Exception:
            pass

    def update(self):
        # Non-blocking; work happens on threads
        pass

    def _drain_queue(self):
        """Drop queued audio so command mode starts cleanly."""
        try:
            while True:
                self.q.get_nowait()
        except queue.Empty:
            return

    # -----------------------------
    # audio
    # -----------------------------
    def _audio_cb(self, indata, frames, time_info, status):
        if not self.running or not self.enabled:
            return

        data = bytes(indata)

        # RMS using numpy (Python 3.13 compatible)
        samples = np.frombuffer(data, dtype=np.int16)
        if samples.size:
            rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
            self._utter_rms_sum += rms
            self._utter_rms_n += 1

        try:
            self.q.put_nowait(data)
        except queue.Full:
            pass

    def _audio_loop(self):
        if not self.enabled:
            return

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
            self._log(f"VoiceEngine audio error: {e}")
            self.enabled = False

        finally:
            try:
                if self._stream is not None:
                    self._stream.close()
            except Exception:
                pass
            self._stream = None

    # -----------------------------
    # recognition
    # -----------------------------
    def _asr_loop(self):
        # If audio died, just exit
        if not self.enabled:
            return

        while self.running and not self._stop_event.is_set() and self.enabled:
            # If we’re awake and the window expires, go back to sleep
            if self.mode == "AWAKE" and time.monotonic() > self.awake_until:
                self._sleep_mode()

            try:
                data = self.q.get(timeout=0.5)
            except queue.Empty:
                continue

            if not data:
                continue

            rec = self.active_rec

            # Partial path (fast wake-word spotting)
            if not rec.AcceptWaveform(data):
                try:
                    partial = json.loads(rec.PartialResult()).get("partial", "").lower()
                except Exception:
                    partial = ""

                if self.mode == "SLEEP" and self.WAKE_PHRASE in partial:
                    self._on_wake()
                continue

            # Final result
            try:
                text = json.loads(rec.Result()).get("text", "").lower().strip()
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
                # Wake phrase sometimes lands in final result
                if self.WAKE_PHRASE in text:
                    self._on_wake()
                continue

            # Command mode
            self._route_command(text, avg_rms)

    # -----------------------------
    # mode transitions (NO SetGrammar)
    # -----------------------------
    def _on_wake(self):
        now = time.monotonic()
        if now - self.last_trigger_time < self.cooldown:
            return
        self.last_trigger_time = now

        self.mode = "AWAKE"
        self.awake_until = now + self.AWAKE_WINDOW

        # Reset command recognizer fresh on every wake (clean state)
        self.cmd_rec = KaldiRecognizer(self.model, self.sample_rate, self.cmd_grammar)
        self.active_rec = self.cmd_rec

        # Drop buffered audio so the command recognizer starts cleanly
        self._drain_queue()

        # “I’m listening”
        try:
            self.behavior.happy()
        except Exception:
            pass

    def _sleep_mode(self):
        self.mode = "SLEEP"
        # Reset wake recognizer too (clean state)
        self.wake_rec = KaldiRecognizer(self.model, self.sample_rate, self.wake_grammar)
        self.active_rec = self.wake_rec
        self.cmd_rec = None
        self._drain_queue()

    # -----------------------------
    # command routing
    # -----------------------------
    def _route_command(self, text, avg_rms):
        # Intensity buckets
        if avg_rms > 2500:
            intensity = "high"
        elif avg_rms > 1200:
            intensity = "mid"
        else:
            intensity = "low"

        self._log(f"Heard: '{text}' (intensity={intensity})")

        try:
            if "bark" in text or "woof" in text:
                self.behavior.bark()
            elif "happy" in text or "hello" in text or "good boy" in text or "good dog" in text:
                self.behavior.happy()
            elif "sad" in text or "scared" in text:
                self.behavior.sad()
            elif "angry" in text:
                self.behavior.bark()
            elif "quiet" in text or "calm" in text:
                self.behavior.idle()
            else:
                # Intensity fallback
                if intensity == "high":
                    self.behavior.bark()
                elif intensity == "mid":
                    self.behavior.happy()
                else:
                    self.behavior.sad()
        except Exception:
            pass

        # Return to sleep after one command
        self._sleep_mode()
