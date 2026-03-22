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
    Offline wake-word + command recognition using Vosk.

    Stability design:
      - NO runtime SetGrammar() calls (avoids native aborts on some systems)
      - Two recognizers:
          * wake_rec: constrained to wake phrase
          * cmd_rec: constrained to command phrases
        We switch which recognizer receives audio after wake is detected.

    Python 3.13 compatible:
      - RMS uses NumPy (no audioop)
    """

    def __init__(
        self,
        behavior,
        config_path="config.json",
        model_path="vosk-model-small-en-us-0.15",
        sample_rate=16000,
        input_device=3,          # set to 3 for your USB Webcam: Audio (1 in, 0 out)
        blocksize=4096,
        awake_window=4.0,
        cooldown=1.0,
        enable_logs=True,
        vosk_log_level=-1,       # -1 quiet; 0+ more logs
    ):
        self.behavior = behavior
        self.sample_rate = int(sample_rate)
        self.blocksize = int(blocksize)
        self.enable_logs = enable_logs

        # Quiet Kaldi/Vosk logs unless debugging
        try:
            SetLogLevel(vosk_log_level)
        except Exception:
            pass

        # Runtime flags
        self.running = True
        self.enabled = True
        self._stop_event = threading.Event()

        # Timing/cooldowns
        self.mode = "SLEEP"
        self.awake_until = 0.0
        self.AWAKE_WINDOW = float(awake_window)
        self.last_trigger_time = 0.0
        self.cooldown = float(cooldown)

