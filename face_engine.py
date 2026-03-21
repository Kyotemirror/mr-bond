import tkinter as tk
import time
import random


class FaceEngine:
    def __init__(self, width=480, height=320, fullscreen=True):
        self.width = width
        self.height = height

        self.window = tk.Tk()
        self.window.configure(bg="black")

        if fullscreen:
            # True fullscreen (no borders, no title bar)
            self.window.overrideredirect(True)
            self.window.geometry(f"{width}x{height}+0+0")
        else:
            # Windowed fallback (for debugging on desktop)
            self.window.title("AI Dog Face")
            self.window.geometry(f"{width}x{height}")

        # Canvas fills entire screen
        self.canvas = tk.Canvas(
            self.window,
            width=width,
            height=height,
            bg="black",
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)

        # Expression state
        self.current_expression = "neutral"
        self.pending_expression = None

        # Blink state
        self.blinking = False
        self.blink_end_time = 0.0
        self.next_blink_time = 0.0

        self._schedule_next_blink()

        # Draw face scaled to screen
        self._draw_face()
        self._apply_expression(self.current_expression)

        # Initial draw
        self.window.update_idletasks()
        self.window.update()

    # -----------------------------
    # Timing helpers
    # -----------------------------
    def _now(self):
        return time.monotonic()

    def _schedule_next_blink(self):
        self.next_blink_time = self._now() + random.uniform(3.0, 6.0)

    # -----------------------------
    # Drawing (scaled)
    # -----------------------------
    def _draw_face(self):
        self.canvas.delete("all")

        w = self.width
        h = self.height

        # Eye positions (relative scaling)
        eye_w = w * 0.10
        eye_h = h * 0.18
        eye_y = h * 0.30

        left_eye_x = w * 0.30
        right_eye_x = w * 0.60

        # Eyes
        self.left_eye = self.canvas.create_oval(
            left_eye_x, eye_y,
            left_eye_x + eye_w, eye_y + eye_h,
            fill="white", outline=""
        )
        self.right_eye = self.canvas.create_oval(
            right_eye_x, eye_y,
            right_eye_x + eye_w, eye_y + eye_h,
            fill="white", outline=""
        )

        # Pupils
        pupil_w = eye_w * 0.35
        pupil_h = eye_h * 0.35

        self.left_pupil = self.canvas.create_oval(
            left_eye_x + eye_w * 0.35,
            eye_y + eye_h * 0.35,
            left_eye_x + eye_w * 0.35 + pupil_w,
            eye_y + eye_h * 0.35 + pupil_h,
            fill="black", outline=""
        )
        self.right_pupil = self.canvas.create_oval(
            right_eye_x + eye_w * 0.35,
            eye_y + eye_h * 0.35,
            right_eye_x + eye_w * 0.35 + pupil_w,
            eye_y + eye_h * 0.35 + pupil_h,
            fill="black", outline=""
        )

        # Eyebrows
        brow_y = eye_y - h * 0.05
        brow_len = eye_w * 1.1

        self.left_brow = self.canvas.create_line(
            left_eye_x, brow_y,
            left_eye_x + brow_len, brow_y + h * 0.02,
            width=5, fill="white"
        )
        self.right_brow = self.canvas.create_line(
            right_eye_x, brow_y + h * 0.02,
            right_eye_x + brow_len, brow_y,
            width=5, fill="white"
        )

        # Mouth
        self.mouth = self.canvas.create_line(
            w * 0.35, h * 0.70,
            w * 0.65, h * 0.70,
            width=5, fill="white", smooth=True
        )

    # -----------------------------
    # Expressions
    # -----------------------------
    def _apply_expression(self, expression):
        self.current_expression = expression
        w = self.width
        h = self.height

        if expression == "neutral":
            self.canvas.coords(self.mouth, w * 0.35, h * 0.70, w * 0.65, h * 0.70)

        elif expression == "happy":
            self.canvas.coords(
                self.mouth,
                w * 0.30, h * 0.68,
                w * 0.50, h * 0.78,
                w * 0.70, h * 0.68
            )

        elif expression == "sad":
            self.canvas.coords(
                self.mouth,
                w * 0.30, h * 0.75,
                w * 0.50, h * 0.65,
                w * 0.70, h * 0.75
            )

        elif expression == "angry":
            self.canvas.coords(self.mouth, w * 0.35, h * 0.72, w * 0.65, h * 0.72)

    # -----------------------------
    # Blink
    # -----------------------------
    def _close_eyes(self):
        self.canvas.itemconfig(self.left_eye, fill="black")
        self.canvas.itemconfig(self.right_eye, fill="black")
        self.canvas.itemconfig(self.left_pupil, state="hidden")
        self.canvas.itemconfig(self.right_pupil, state="hidden")

    def _open_eyes(self):
        self.canvas.itemconfig(self.left_eye, fill="white")
        self.canvas.itemconfig(self.right_eye, fill="white")
        self.canvas.itemconfig(self.left_pupil, state="normal")
        self.canvas.itemconfig(self.right_pupil, state="normal")

    # -----------------------------
    # Update loop
    # -----------------------------
    def update(self):
        now = self._now()

        if self.pending_expression:
            self._apply_expression(self.pending_expression)
            self.pending_expression = None

        if self.blinking:
            if now >= self.blink_end_time:
                self._open_eyes()
                self.blinking = False
                self._schedule_next_blink()
        else:
            if now >= self.next_blink_time:
                self._close_eyes()
                self.blinking = True
                self.blink_end_time = now + 0.12

        self.window.update_idletasks()
        self.window.update()

    # -----------------------------
    # Public API
    # -----------------------------
    def set_expression(self, expression):
        self.pending_expression = expression

    def shutdown(self):
        try:
            self.window.destroy()
        except Exception:
            pass
