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
            # SAFE fullscreen (preferred on small HDMI / SPI displays)
            self.window.title("")
            self.window.attributes("-fullscreen", True)
            self.window.configure(cursor="none")  # hide mouse cursor
            self.window.bind("<Escape>", lambda e: self.shutdown())  # emergency exit
        else:
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

        # Draw face
        self._draw_face()
        self._apply_expression(self.current_expression)

        # Initial render
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

        # Eyes
        eye_w = w * 0.12
        eye_h = h * 0.22
        eye_y = h * 0.30

        left_eye_x = w * 0.28
        right_eye_x = w * 0.60

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
        brow_y = eye_y - h * 0.06
        brow_len = eye_w * 1.2

