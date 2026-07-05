"""VRTwin control panel - a GUI for configuring and running the VRChat AI avatar.

Renders every setting from settings_schema.py as a labelled control with a
plain-language explanation, saves to `.env`, offers a one-click reset to
defaults, and starts/stops the avatar (main.py) as a subprocess with its
output streamed into a log panel.

Run with:  python gui.py
"""

import json
import queue
import subprocess
import sys
import threading
import tkinter.messagebox as messagebox
from pathlib import Path

import customtkinter as ctk

import settings_schema as schema

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_DIR = Path(__file__).parent
HELP_COLOR = ("gray35", "gray60")


def scan_audio_devices():
    """Returns (input_names, output_names); empty lists when audio is unavailable."""
    try:
        import pyaudio

        p = pyaudio.PyAudio()
        inputs, outputs = [], []
        for i in range(p.get_device_count()):
            d = p.get_device_info_by_index(i)
            if d.get("maxInputChannels", 0) > 0:
                inputs.append(d["name"])
            if d.get("maxOutputChannels", 0) > 0:
                outputs.append(d["name"])
        p.terminate()
        return inputs, outputs
    except Exception:
        return [], []


class SettingRow:
    """One setting: bold label, the control, and an always-visible explanation."""

    def __init__(self, parent, setting: schema.Setting, initial: str):
        self.setting = setting
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frame.pack(fill="x", padx=12, pady=(10, 2))
        self.frame.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self.frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(header, text=setting.label, font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").pack(side="left")
        self.value_label = None
        if setting.kind == "slider":
            self.value_label = ctk.CTkLabel(header, text="", font=ctk.CTkFont(size=13), anchor="e")
            self.value_label.pack(side="right")

        self._build_control(initial)

        ctk.CTkLabel(self.frame, text=setting.help, font=ctk.CTkFont(size=11),
                     text_color=HELP_COLOR, anchor="w", justify="left",
                     wraplength=760).grid(row=2, column=0, sticky="ew", pady=(2, 0))

    def _build_control(self, initial: str):
        s = self.setting
        if s.kind == "bool":
            self.var = ctk.StringVar(value=initial)
            control = ctk.CTkSwitch(self.frame, text="", variable=self.var,
                                    onvalue="true", offvalue="false")
        elif s.kind == "slider":
            self.var = ctk.DoubleVar(value=float(initial))
            steps = int(round((s.max - s.min) / s.step))
            control = ctk.CTkSlider(self.frame, from_=s.min, to=s.max,
                                    number_of_steps=steps, variable=self.var,
                                    command=lambda _v: self._update_slider_label())
            self._update_slider_label()
        elif s.kind == "choice":
            self.var = ctk.StringVar(value=initial)
            control = ctk.CTkComboBox(self.frame, values=s.choices, variable=self.var, width=280)
        elif s.kind in ("device_in", "device_out"):
            self.var = ctk.StringVar(value=initial)
            control = ctk.CTkComboBox(self.frame, values=[initial], variable=self.var, width=420)
            self.device_box = control
        elif s.kind in ("multiline", "json"):
            control = ctk.CTkTextbox(self.frame, height=88 if s.kind == "multiline" else 64,
                                     wrap="word")
            control.insert("1.0", initial)
            self.textbox = control
        else:  # text, secret, int, float, float_optional
            self.var = ctk.StringVar(value=initial)
            control = ctk.CTkEntry(self.frame, textvariable=self.var, width=420,
                                   placeholder_text=s.placeholder,
                                   show="•" if s.kind == "secret" else "")
        control.grid(row=1, column=0, sticky="ew" if s.kind in ("multiline", "json", "slider") else "w",
                     pady=(4, 0))
        self.control = control

    def _update_slider_label(self):
        if self.value_label is not None:
            self.value_label.configure(text=f"{self._format_slider()} {self.setting.unit}".strip())

    def _format_slider(self) -> str:
        value = self.var.get()
        return str(int(round(value))) if self.setting.step >= 1 else f"{value:.1f}"

    def get(self) -> str:
        if self.setting.kind in ("multiline", "json"):
            return self.textbox.get("1.0", "end").strip()
        if self.setting.kind == "slider":
            return self._format_slider()
        return self.var.get().strip() if isinstance(self.var, ctk.StringVar) else str(self.var.get())

    def set(self, value: str):
        if self.setting.kind in ("multiline", "json"):
            self.textbox.delete("1.0", "end")
            self.textbox.insert("1.0", value)
        elif self.setting.kind == "slider":
            self.var.set(float(value))
            self._update_slider_label()
        else:
            self.var.set(value)

    def set_device_choices(self, names):
        if hasattr(self, "device_box") and names:
            self.device_box.configure(values=names)


class VRTwinApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("VRTwin - VRChat AI avatar")
        self.geometry("1020x820")
        self.minsize(860, 640)

        self.process = None
        self.log_queue = queue.Queue()
        self.rows: dict[str, SettingRow] = {}

        self._build_layout()
        self._refresh_devices()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(150, self._poll_log_queue)

    # ---------- layout ----------

    def _build_layout(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=3)
        self.grid_rowconfigure(3, weight=1)

        # Top bar: run control + status
        top = ctk.CTkFrame(self)
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        self.start_button = ctk.CTkButton(top, text="▶  Start avatar", width=150,
                                          command=self._toggle_avatar)
        self.start_button.pack(side="left", padx=8, pady=8)
        self.status_label = ctk.CTkLabel(top, text="Stopped", anchor="w")
        self.status_label.pack(side="left", padx=8)

        # Settings tabs
        values = schema.load_values()
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
        for section in schema.SECTIONS:
            tab = self.tabview.add(section)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)
            scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
            scroll.grid(row=0, column=0, sticky="nsew")
            for setting in (s for s in schema.SETTINGS if s.section == section):
                self.rows[setting.key] = SettingRow(scroll, setting, values[setting.key])
            if section == "Audio Devices":
                ctk.CTkButton(scroll, text="↻  Refresh device lists", width=180,
                              command=self._refresh_devices).pack(anchor="w", padx=12, pady=12)

        # Bottom bar: save / reset
        bottom = ctk.CTkFrame(self)
        bottom.grid(row=2, column=0, sticky="ew", padx=10, pady=4)
        ctk.CTkButton(bottom, text="\U0001f4be  Save settings", width=150,
                      command=self._save).pack(side="left", padx=8, pady=8)
        ctk.CTkButton(bottom, text="↩  Reset to defaults", width=160,
                      fg_color=("gray70", "gray30"), hover_color=("gray60", "gray25"),
                      command=self._reset_to_defaults).pack(side="left", padx=8)
        self.save_label = ctk.CTkLabel(bottom, text="", anchor="w")
        self.save_label.pack(side="left", padx=8)

        # Log panel
        log_frame = ctk.CTkFrame(self)
        log_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=(4, 10))
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(log_frame, text="Avatar log", font=ctk.CTkFont(size=12, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 0))
        self.log_box = ctk.CTkTextbox(log_frame, wrap="word", font=ctk.CTkFont(family="Consolas", size=11))
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        self.log_box.configure(state="disabled")

    # ---------- settings ----------

    def _collect(self) -> dict:
        return {key: row.get() for key, row in self.rows.items()}

    def _save(self) -> bool:
        values = self._collect()
        errors = schema.validate_all(values)
        if errors:
            messagebox.showerror("Invalid settings", "\n".join(errors), parent=self)
            return False
        schema.save_values(values)
        note = " Restart the avatar to apply." if self.process else ""
        self.save_label.configure(text=f"Saved to .env.{note}")
        return True

    def _reset_to_defaults(self):
        if not messagebox.askyesno(
            "Reset to defaults",
            "Set every option back to its default value?\n\n"
            "Your API key is cleared too. Nothing is saved until you click 'Save settings'.",
            parent=self,
        ):
            return
        for key, row in self.rows.items():
            row.set(row.setting.default)
        self.save_label.configure(text="Defaults restored - click 'Save settings' to keep them.")

    def _refresh_devices(self):
        inputs, outputs = scan_audio_devices()
        self.rows["INPUT_DEVICE"].set_device_choices(inputs)
        self.rows["OUTPUT_DEVICE"].set_device_choices(outputs)

    # ---------- run control ----------

    def _toggle_avatar(self):
        if self.process is None:
            self._start_avatar()
        else:
            self._stop_avatar()

    def _start_avatar(self):
        if not self._save():  # settings are read at process start
            return
        if not self._collect()["OPENROUTER_API_KEY"]:
            messagebox.showerror("Missing API key",
                                 "Enter your OpenRouter API key on the 'Keys & Models' tab first.",
                                 parent=self)
            return
        self._append_log("--- Starting avatar ---\n")
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self.process = subprocess.Popen(
            [sys.executable, "-u", str(APP_DIR / "main.py")],
            cwd=APP_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )
        threading.Thread(target=self._read_process_output, args=(self.process,), daemon=True).start()
        self.start_button.configure(text="■  Stop avatar", fg_color=("#b3261e", "#8c1d18"),
                                    hover_color=("#8c1d18", "#601410"))
        self.status_label.configure(text="Running - settings changes apply after a restart")

    def _stop_avatar(self):
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self._on_process_ended()

    def _on_process_ended(self):
        self.process = None
        self.start_button.configure(text="▶  Start avatar",
                                    fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"],
                                    hover_color=ctk.ThemeManager.theme["CTkButton"]["hover_color"])
        self.status_label.configure(text="Stopped")
        self._append_log("--- Avatar stopped ---\n")

    def _read_process_output(self, process):
        for line in process.stdout:
            self.log_queue.put(line)
        process.wait()
        self.log_queue.put(None)  # sentinel: process ended

    def _poll_log_queue(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                if line is None:
                    if self.process is not None:
                        self._on_process_ended()
                else:
                    self._append_log(line)
        except queue.Empty:
            pass
        self.after(150, self._poll_log_queue)

    def _append_log(self, text: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _on_close(self):
        if self.process is not None:
            self._stop_avatar()
        self.destroy()


def main():
    app = VRTwinApp()
    app.mainloop()


if __name__ == "__main__":
    main()
