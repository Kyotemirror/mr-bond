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

    Key improvements over the original:
      - Uses time.monotonic() for stable timing
      - No time.sleep() inside update() (non-blocking)
      - Idle micro-behaviors are time-based (not tied to FPS)
    """

    def __init__(self, face, sound):
        self.face = face
        self.sound = sound

        # Core state
        self.current_state = "idle"
        self.last_state_change = time.monotonic()

        # Idle micro-behavior (non-blocking) tracking
        self.micro_active = False
        self.micro_end_time = 0.0
        self.MICRO_DURATION = 0.2 
        self.MICRO_MEAN_INTERVAL = 8.0   # average time between idle micro-smile
        self.next_micro_time = self.last_state_change + self._sample_next_micro_delay()

        # Tunables
        self.BARK_DURATION = 1.0
        self.HAPPY_DURATION = 3.0
        self.SAD_DURATION = 3.0
        self.MICRO_DURATION = 0.2
        self.MICRO_MEAN_INTERVAL = 8.0  # average time between idle micro-smiles
        

        # Set initial expression
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
        Returns the delay (seconds) until the next micro-behavior while idle.
        Exponential distribution gives a natural randomness (sometimes quick, sometimes longer).
        """
        return random.expovariate(1.0 / self.MICRO_MEAN_INTERVAL)

    # -----------------------------
    # State helper
    # -----------------------------
    def _set_state(self, state, expression=None):
        if expression is not None:
            self.face.set_expression(expression)
        self.current_state = state
        self.last_state_change = self._now()

    # -----------------------------
    # Public actions
    # -----------------------------
    def bark(self):
        # You can optionally guard against bark spam here if needed
        self.face.set_expression("angry")
        self.sound.play()
        self._set_state("barking")

        # While barking, disable micro behaviors
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
    # Update loop
    # -----------------------------
    def update(self):
        now = self._now()

        # --- Timed states (non-blocking) ---
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

        # --- Idle micro-behaviors (non-blocking) ---
        if self.current_state == "idle":
            # If a micro expression is currently active, end it when time is up
            if self.micro_active:
                if now >= self.micro_end_time:
                    self.face.set_expression("neutral")
                    self.micro_active = False
                    self.next_micro_time = now + self._sample_next_micro_delay()
            else:
                # Start a micro expression when its scheduled time arrives
                if now >= self.next_micro_time:
                    self.face.set_expression("happy")
                    self.micro_active = True
                    self.micro_end_time = now + self.MICRO_DURATION
