import json
import os
import queue
import threading
import time

import numpy as np
import sounddevice as sd
from vosk import Model, KaldiRecognizer, SetLogLevel


class VoiceEngine:
    def __init__(
        self,
        behavior,
        config_path="config.json",
        model_path="vosk-model-small-en-us-0.15",
        sample_rate=16000,
        input_device=3,      # ✅ USB Webcam mic
        blocksize=4096,
        awake_window=4.0,
        cooldown=1.0,
        enable_logs=True,
        vosk_log_level=-1
    ):
        self.behavior = behavior
        self.sample_rate = int(sample_rate)
        self.blocksize = int(blocksize)
        self.input_device = input_device
        self.enable_logs = enable_logs

        # Required attributes for main loop compatibility
        self.enabled = True
        self.running = True
        self._stop_event = threading.Event()

        try:
            SetLogLevel(vosk_log_level)
        except Exception:
            pass

        # -----------------------------
        # Load config.json
        # -----------------------------
        cfg = {}
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
        except Exception:
            pass

        self.WAKE_PHRASE = str(cfg.get("wake_word", "hey bond")).lower().strip()

        self.commands = [
            "bark", "woof", "happy", "sad", "hello",
            "good boy", "good dog", "quiet", "calm",
            "angry", "scared"
        ]

        self.wake_grammar = json.dumps([self.WAKE_PHRASE, "[unk]"])
        self.cmd_grammar = json.dumps(self.commands + ["[unk]"])

        # -----------------------------
        # State
        # -----------------------------
        self.mode = "SLEEP"
        self.awake_until = 0.0
        self.AWAKE_WINDOW = float(awake_window)
        self.last_trigger_time = 0.0
        self.cooldown = float(cooldown)

        self.q = queue.Queue(maxsize=120)

        self._utter_rms_sum = 0.0
        self._utter_rms_n = 0

        # -----------------------------
        # Load model
        # -----------------------------
        self.model_path = os.path.abspath(model_path)
        if not os.path.isdir(self.model_path):
            self._log(f"VoiceEngine: model not found: {self.model_path}")
            self.enabled = False
            return

        try:
            self.model = Model(self.model_path)
        except Exception as e:
            self._log(f"VoiceEngine: failed to load model: {e}")
            self.enabled = False
            return

        # -----------------------------
        # Recognizers
        # -----------------------------
        self.wake_rec = KaldiRecognizer(
            self.model, self.sample_rate, self.wake_grammar
        )
        self.cmd_rec = None
