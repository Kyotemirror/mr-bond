import json
import os
import queue
import threading
import time

import numpy as np
import sounddevice as sd
from vosk import Model, KaldiRecognizer


class VoiceEngine:
    """
    Offline wake-word + command recognition using Vosk + sounddevice.

    Key stability features:
      - Python 3.13 compatible (no audioop)
      - Delays KaldiRecognizer creation until AFTER audio stream starts
        (prevents native Kaldi aborts on some systems)
      - Auto-selects a usable input device if default is invalid
      - Fails gracefully (disables voice) instead of crashing the whole app
      - Provides update() for engine interface compatibility
    """

    def __init__(
        self,
        behavior,
        model_path="vosk-model-small-en-us-0.15",
        sample_rate=16000,
        input_device=None,          # None = auto
        blocksize=8000,
        wake_phrase="hey husky",
        awake_window=4.0,
        cooldown=1.0,
        enable_logs=True,
    ):
        self.behavior = behavior
        self.sample_rate = int(sample_rate)
        self.blocksize = int(blocksize)
        self.enable_logs = enable_logs

        # ---- Mode state ----
        self.mode = "SLEEP"
        self.awake_until = 0.0
        self.AWAKE_WINDOW = float(awake_window)

        # Cooldown to prevent repeated wake spam
        self.last_trigger_time = 0.0
        self.cooldown = float(cooldown)

        # Grammars
        self.WAKE_PHRASE = wake_phrase.lower().strip()
        self.wake_grammar = json.dumps([self.WAKE_PHRASE, "[unk]"])
        self.cmd_grammar = json.dumps([
            "bark", "woof", "happy", "sad", "hello", "good boy", "good dog",
            "quiet", "calm", "angry", "scared", "[unk]"
        ])

        # Audio pipeline
        self.q = queue.Queue(maxsize=80)
        self.running = True
        self._stop_event = threading.Event()

        # Loudness tracking (RMS)
        self._utter_rms_sum = 0.0
        self._utter_rms_n = 0

        # Device selection
        self.input_device = input_device  # may be None; we'll resolve it safely
        self._stream = None

        # Vosk objects (model can be created now; recognizer is delayed)
        self.model = None
        self.rec = None

        # Resolve and validate model path early (absolute path avoids surprises)
        self.model_path = os.path.abspath(model_path)

        # If model folder is missing, disable voice safely
        if not os.path.isdir(self.model_path):
            self._log(f"VoiceEngine: model folder not found: {self.model_path}")
            self.enabled = False
            return

        # Load model (this can be heavy, but shouldn't abort)
        try:
            self.model = Model(self.model_path)
        except Exception as e:
            self._log(f"VoiceEngine: failed to load model: {e}")
            self.enabled = False
            return

        # Engine enabled unless audio init fails
        self.enabled = True

        # Start threads
        self.audio_thread = threading.Thread(target=self._audio_loop, daemon=True)
        self.asr_thread = threading.Thread(target=self._asr_loop, daemon=True)
        self.audio_thread.start()
        self.asr_thread.start()

        self._log("VoiceEngine: Offline wake-word + commands ready.")

    # -----------------------------
    # Logging helper
    # -----------------------------
    def _log(self, msg):
        if self.enable_logs:
            print(msg)

    # -----------------------------
    # Device selection
    # -----------------------------
    def _select_input_device(self):
        """
        Return a valid input device index or None.
        If input_device was provided, try it first.
        Otherwise, try default; if invalid, choose the first device with input channels.
        """
        try:
            devices = sd.query_devices()
        except Exception as e:
            self._log(f"VoiceEngine: cannot query audio devices: {e}")
            return None

        if not devices:
            self._log("VoiceEngine: no audio devices found.")
            return None

        # If user provided a device index, validate it
        if self.input_device is not None:
            try:
                info = sd.query_devices(self.input_device)
                if info and info.get("max_input_channels", 0) > 0:
                    return self.input_device
                self._log(f"VoiceEngine: selected device {self.input_device} has no input channels.")
            except Exception as e:
                self._log(f"VoiceEngine: invalid input_device={self.input_device}: {e}")

        # Try default input device
        try:
            default_in = sd.default.device[0]  # (input, output)
            if default_in is not None and default_in >= 0:
                info = sd.query_devices(default_in)
                if info and info.get("max_input_channels", 0) > 0:
                    return default_in
        except Exception:
            pass

        # Fallback: first device with input channels
        for idx, info in enumerate(devices):
            try:
                if info.get("max_input_channels", 0) > 0:
                    return idx
            except Exception:
                continue

        self._log("VoiceEngine: no usable input device found.")
        return None

    # -----------------------------
    # Lifecycle
    # -----------------------------
    def shutdown(self):
        self.running = False
        self._stop_event.set()

        try:
            if self._stream is not None:
                self._stream.close()
        except Exception:
            pass

        # Unblock ASR thread if waiting
        try:
            self.q.put_nowait(b"")
        except Exception:
            pass

    # -----------------------------
    # Audio capture
    # -----------------------------
    def _audio_cb(self, indata, frames, time_info, status):
        if not self.running or not self.enabled:
            return

        data = bytes(indata)

        # RMS using NumPy (Python 3.13 compatible)
        samples = np.frombuffer(data, dtype=np.int16)
        if samples.size:
            rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
            self._utter_rms_sum += rms
            self._utter_rms_n += 1

        try:
            self.q.put_nowait(data)
        except queue.Full:
            pass  # drop if overloaded

    def _audio_loop(self):
        if not self.enabled:
            return

        dev = self._select_input_device()
        if dev is None:
            self._log("VoiceEngine: disabling voice (no input device).")
            self.enabled = False
            return

        try:
            self._stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.blocksize,
                dtype="int16",
                channels=1,
                device=dev,
                callback=self._audio_cb
            )
            self._stream.start()

            # ✅ CRITICAL: Create recognizer only AFTER stream starts
            # This avoids certain native abort paths on some systems.
            try:
                self.rec = KaldiRecognizer(self.model, self.sample_rate, self.wake_grammar)
            except Exception as e:
                self._log(f"VoiceEngine: failed to create recognizer: {e}")
                self.enabled = False
                return

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
    # ASR loop
    # -----------------------------
    def _asr_loop(self):
        # Wait until recognizer is ready or engine is disabled
        while self.running and not self._stop_event.is_set():
            if not self.enabled:
                return
            if self.rec is not None:
                break
            time.sleep(0.05)

        while self.running and not self._stop_event.is_set() and self.enabled:
            # Auto-sleep if awake window expired
            if self.mode == "AWAKE" and time.monotonic() > self.awake_until:
                self._sleep_mode()

            try:
                data = self.q.get(timeout=0.5)
            except queue.Empty:
                continue

            if not data:
                continue

            # Partial results for fast wake spotting
            if not self.rec.AcceptWaveform(data):
                try:
                    partial = json.loads(self.rec.PartialResult()).get("partial", "").lower()
                except Exception:
                    partial = ""

                if self.mode == "SLEEP" and self.WAKE_PHRASE in partial:
                    self._on_wake()
                continue

            # Final result
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
        self.mode = "AWAKE"
        self.awake_until = now + self.AWAKE_WINDOW

        # Switch grammar to command set
        try:
            self.rec.SetGrammar(self.cmd_grammar)
        except Exception as e:
            self._log(f"VoiceEngine: grammar switch error: {e}")

        # “I’m listening”
        try:
            self.behavior.happy()
        except Exception:
            pass

    def _sleep_mode(self):
        self.mode = "SLEEP"
        try:
            self.rec.SetGrammar(self.wake_grammar)
        except Exception as e:
            self._log(f"VoiceEngine: grammar switch error: {e}")

    # -----------------------------
    # Command routing
    # -----------------------------
    def _route_command(self, text, avg_rms):
        # Intensity buckets (tune these after you see live RMS values)
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
                self.behavior.bark()  # or add dedicated angry later
            elif "quiet" in text or "calm" in text:
                self.behavior.idle()
            else:
                # fallback based on intensity only
                if intensity == "high":
                    self.behavior.bark()
                elif intensity == "mid":
                    self.behavior.happy()
                else:
                    self.behavior.sad()
        except Exception:
            pass

        # After one command, go back to sleep
        self._sleep_mode()

    # -----------------------------
    # Engine interface (main loop compatibility)
    # -----------------------------
    def update(self):
        # Non-blocking: runs in background threads
        pass
