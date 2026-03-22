import json
import os
import queue
import socket
import time

import sounddevice as sd
from vosk import Model, KaldiRecognizer, SetLogLevel

SOCK_PATH = "/tmp/bond.sock"


def load_config(path="config.json"):
    try:
        with open(path, "r") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def uds_send(message: dict):
    """
    Send one newline-delimited JSON message to Bond Core via UDS.
    """
    payload = (json.dumps(message) + "\n").encode("utf-8")
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(SOCK_PATH)
    s.sendall(payload)
    s.close()


def safe_send(message: dict, retries=10, delay=0.2):
    """
    Try sending even if Bond Core isn't up yet.
    """
    last_err = None
    for _ in range(retries):
        try:
            uds_send(message)
            return True
        except Exception as e:
            last_err = e
            time.sleep(delay)
    print("voice_service: failed to send message to Bond Core:", last_err)
    return False


def main():
    # Reduce Vosk/Kaldi console spam
    SetLogLevel(-1)

    cfg = load_config("config.json")
    wake_word = str(cfg.get("wake_word", "hey bond")).lower().strip()

    # You can change these defaults if you want later
    model_path = os.path.abspath(cfg.get("vosk_model_path", "vosk-model-small-en-us-0.15"))
    sample_rate = int(cfg.get("sample_rate", 16000))
    input_device = cfg.get("input_device", 3)  # your USB webcam mic device index
    blocksize = int(cfg.get("blocksize", 8000))

    # Commands we care about (we parse these from recognized text)
    commands = {
        "bark": "bark",
        "woof": "bark",
        "happy": "happy",
        "hello": "happy",
        "good boy": "happy",
        "good dog": "happy",
        "sad": "sad",
        "scared": "sad",
        "quiet": "idle",
        "calm": "idle",
    }

    if not os.path.isdir(model_path):
        print(f"voice_service: model folder not found: {model_path}")
        return

    print("voice_service: loading model...")
    model = Model(model_path)
    print("voice_service: model loaded.")
    print(f"voice_service: wake word = '{wake_word}'")
    print(f"voice_service: input_device = {input_device}, sample_rate = {sample_rate}")

    # One recognizer, open vocabulary.
    # (More stable than swapping grammars at runtime.)
    rec = KaldiRecognizer(model, sample_rate)

    audio_q = queue.Queue(maxsize=50)

    def callback(indata, frames, time_info, status):
        # Called from sounddevice audio thread
        if status:
            # Not fatal; just prints warnings like overflows
            # print(status)
            pass
        try:
            audio_q.put_nowait(bytes(indata))
        except queue.Full:
            pass

    # Tell Bond Core we’re alive (optional)
    safe_send({"v": 1, "type": "status", "status": "voice_ready", "ts": time.time()})

    mode = "SLEEP"
    awake_until = 0.0
    AWAKE_WINDOW = float(cfg.get("awake_window", 4.0))
    COOLDOWN = float(cfg.get("cooldown", 1.0))
    last_wake = 0.0

    print("voice_service: listening (Ctrl+C to stop)")

    with sd.RawInputStream(
        samplerate=sample_rate,
        blocksize=blocksize,
        dtype="int16",
        channels=1,
        device=input_device,
        callback=callback,
    ):
        while True:
            data = audio_q.get()

            # Feed audio to recognizer
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = (result.get("text") or "").lower().strip()

                if not text:
                    continue

                now = time.monotonic()

                # Wake detection (simple + robust)
                if mode == "SLEEP":
                    if wake_word in text and (now - last_wake) >= COOLDOWN:
                        last_wake = now
                        mode = "AWAKE"
                        awake_until = now + AWAKE_WINDOW
                        safe_send({"v": 1, "type": "wake", "ts": time.time()})
                    continue

                # Command mode
                if mode == "AWAKE":
                    if now > awake_until:
                        mode = "SLEEP"
                        continue

                    # Find first matching command phrase
                    cmd_out = None
                    for phrase, mapped in commands.items():
                        if phrase in text:
                            cmd_out = mapped
                            break

                    # Send command if recognized
                    if cmd_out:
                        safe_send({"v": 1, "type": "cmd", "cmd": cmd_out, "raw": text, "ts": time.time()})
                        mode = "SLEEP"
                    else:
                        # If it's not a known command, just go back to sleep
                        mode = "SLEEP"
            else:
                # Partial results can optionally be used for faster wake detection.
                # Keeping it simple + stable: do nothing here.
                pass


if __name__ == "__main__":
    main()
