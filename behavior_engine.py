import time
import random


class BehaviorEngine:
    """
    Simple finite-state behavior controller.

    States:
      - idle
      - happy
      - sad
      - barking

    Design goals:
      - Non-blocking updates (no sleep in update)
      - Stable timing using time.monotonic()
      - Natural idle micro-behaviors
    """

    def __init__(self, face, sound):
        self.face = face
        self.sound = sound

        # Core state
        self.current_state = "idle"
        self.last_state_change = time.monotonic()

        # Tunables
        self.BARK_DURATION = 1.0
        self.HAPPY_DURATION = 3.0
        self.SAD_DURATION = 3.0
        self.MICRO_DURATION = 0.2
        self.MICRO_MEAN_INTERVAL = 8.0  # average seconds between idle micro-smiles

        # Idle micro-behavior tracking
        self.micro_active = False
        self.micro_end_time = 0.0
        self.next_micro_time = self._now() + self._sample_next_micro_delay()

        # Initial expression
        self.face.set_expression("neutral")

    # -----------------------------
    # Timing helpers
    # -----------------------------
    def _now(self):
        return time.monotonic()

    def _elapsed(self):
        return self._now() - self.last_state_change

    def _sample_next_micro_delay(self):
        """
        Exponential distribution gives natural randomness:
        sometimes quick, sometimes longer.
        """
        return random.expovariate(1.0 / self.MICRO_MEAN_INTERVAL)

    # -----------------------------
    # State helper
    # -----------------------------
    def _set_state(self, state, expression=None):
        if self.current_state == state:
            return

        if expression is not None:
            self.face.set_expression(expression)

        self.current_state = state
        self.last_state_change = self._now()

    # -----------------------------
    # Public actions
    # -----------------------------
    def bark(self):
        self.face.set_expression("angry")
        self.sound.play()
        self._set_state("barking")

        # Disable micro behaviors while barking
        self.micro_active = False

    def happy(self):
        self._set_state("happy", "happy")
        self.micro_active = False

    def sad(self):
        self._set_state("sad", "sad")
        self.micro_active = False

    def idle(self):
        self._set_state("idle", "neutral")
        self.micro_active = False
        self.next_micro_time = self._now() + self._sample_next_micro_delay()

    # -----------------------------
    # Update loop (non-blocking)
    # -----------------------------
    def update(self):
        now = self._now()

        # --- Timed states ---
        if self.current_state == "barking":
            if self._elapsed() > self.BARK_DURATION:
                self.idle()
            return

        if self.current_state == "happy":
            if self._elapsed() > self.HAPPY_DURATION:
                self.idle()
            return

        if self.current_state == "sad":
            if self._elapsed() > self.SAD_DURATION:
                self.idle()
            return

        # --- Idle micro-behaviors ---
        if self.current_state == "idle":
            if self.micro_active:
                if now >= self.micro_end_time:
                    self.face.set_expression("neutral")
                    self.micro_active = False
                    self.next_micro_time = now + self._sample_next_micro_delay()
            else:
                if now >= self.next_micro_time:
                    self.face.set_expression("happy")
