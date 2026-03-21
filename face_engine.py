import tkinter as tk
import time
import random


class FaceEngine:
    def __init__(self, config=None):
        self.window = tk.Tk()
        self.window.title("AI Dog Face")
        self.window.geometry("400x400")
        self.window.configure(bg="black")

        self.canvas = tk.Canvas(
            self.window,
            width=400,
            height=400,
            bg="black",
            highlightthickness=0
        )
        self.canvas.pack()

        # Expression state
        self.current_expression = "neutral"
        self.pending_expression = None  # set by set_expression()

        # Blink state (non-blocking)
        self.blinking = False
        self.blink_end_time = 0.0
        self.next_blink_time = 0.0

        # Timing
        self._t0 = time.monotonic()
        self._schedule_next_blink()

        # Draw initial face
        self._draw_face()
        self._apply_expression(self.current_expression)

        # Initial window pump
        self.window.update_idletasks()
        self.window.update()

    # -----------------------------
    # Timing helpers
    # -----------------------------
    def _now(self):
        return time.monotonic()

    def _schedule_next_blink(self):
        # Blink randomly every 3–6 seconds
        self.next_blink_time = self._now() + random.uniform(3.0, 6.0)

    # -----------------------------
    # Drawing
    # -----------------------------
    def _draw_face(self):
        self.canvas.delete("all")

        # Eyes
        self.left_eye = self.canvas.create_oval(120, 140, 170, 190, fill="white", outline="")
        self.right_eye = self.canvas.create_oval(230, 140, 280, 190, fill="white", outline="")

        # Pupils
        self.left_pupil = self.canvas.create_oval(140, 160, 155, 175, fill="black", outline="")
        self.right_pupil = self.canvas.create_oval(250, 160, 265, 175, fill="black", outline="")

        # Eyebrows
        self.left_brow = self.canvas.create_line(120, 130, 170, 135, width=5, fill="white")
        self.right_brow = self.canvas.create_line(230, 135, 280, 130, width=5, fill="white")

        # Mouth
        self.mouth = self.canvas.create_line(
            170, 250, 230, 250,
            width=5, fill="white", smooth=True
        )

    # -----------------------------
    # Expression logic
    # -----------------------------
    def _apply_expression(self, expression):
        self.current_expression = expression

        if expression == "neutral":
            self.canvas.coords(self.left_brow, 120, 130, 170, 135)
            self.canvas.coords(self.right_brow, 230, 135, 280, 130)
            self.canvas.coords(self.mouth, 170, 250, 230, 250)

        elif expression == "happy":
            self.canvas.coords(self.left_brow, 120, 125, 170, 130)
            self.canvas.coords(self.right_brow, 230, 130, 280, 125)
            self.canvas.coords(self.mouth, 160, 250, 200, 270, 240, 250)

        elif expression == "sad":
            self.canvas.coords(self.left_brow, 120, 140, 170, 135)
            self.canvas.coords(self.right_brow, 230, 135, 280, 140)
            self.canvas.coords(self.mouth, 160, 260, 200, 240, 240, 260)

        elif expression == "angry":
            self.canvas.coords(self.left_brow, 120, 140, 170, 130)
            self.canvas.coords(self.right_brow, 230, 130, 280, 140)
            self.canvas.coords(self.mouth, 170, 250, 230, 250)

    # -----------------------------
    # Blink animation (non-blocking)
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

        # Apply queued expression changes
        if self.pending_expression is not None:
            self._apply_expression(self.pending_expression)
            self.pending_expression = None

        # Blink state machine
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

        # Keep Tk responsive
        self.window.update_idletasks()
        self.window.update()

    # -----------------------------
    # Public API
    # -----------------------------
    def set_expression(self, expression):
        # Queue expression change (cheap, non-blocking)
        self.pending_expression = expression

    def shutdown(self):
        try:
            self.window.destroy()
        except Exception:
            pass


    # -----------------------------
    # Public API
    # -----------------------------
    def set_expression(self, expression):
        # Don’t redraw immediately; queue it for the next update tick
        self.pending_expression = expression
