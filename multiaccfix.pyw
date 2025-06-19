'''
Dependancies
pip install psutil requests pyautogui

INSTRUCTIONS
Change the webhook URL to wherever you'd like to be notified
Add your discord id so you get pinged whenever it breaks
Use the Gui and locate the JOIN SERVER button on your roblox account manager
Enjoy :)

do "pip install pip install -r requirements.txt" if you encounter module not found error (open cmd and copy whatever i wrote there)

"@criticize." on Discord was here ^_^ I'm not the original creator of the script, just someone who curated it by a bit :p
'''

from __future__ import annotations
import time
import datetime as dt
import threading
import psutil
import requests
import pyautogui
import tkinter as tk
from tkinter import ttk, messagebox
import json
import os

CONFIG_PATH = 'watchdog_config.json'

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {"has_shown_manual": False}
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(cfg, f)

def show_manual():
    message = (
        "👋 Welcome to Roblox Macro Watchdog!\n\n"
        "Here's how to use it:\n"
        "1. Use 'Set Button Coord' to capture the location of your macro's JOIN button.\n"
        "2. Fill in your Discord Webhook URL in the source code.\n"
        "3. Enter your Discord user ID to receive crash alerts.\n"
        "4. Hit 'Start' to begin monitoring.\n"
        "5. The app will restart Roblox every 45 mins or after a crash.\n"
        "6. Use 'Test Countdown' to check Discord notifications.\n\n"
        "✅ That's it. Enjoy automated uptime!"
    )
    messagebox.showinfo("📘 How To Use", message)

# ────────────────────────────────────────────────
# CONFIGURE ME (defaults – can be overridden in GUI)
WEBHOOK_URLS = [
    'CHANGE ME',
    #'CHANGE ME',
]
BUTTON_COORDS   = (1525, 195)   # fallback pixel (x, y) of the macro‑tool button
BASE_INTERVAL = 20 * 60         # seconds between regular restarts
WARNING_OFFSET  = 60            # 1‑minute warning before restart
PROCESS_NAME    = 'robloxplayerbeta.exe'
RETRY_DELAY     = 30            # seconds to wait for clients to appear
MAX_RETRIES     = 3             # attempts before giving up
PING_USER_ID    = 'ADD USER ID HERE'
MSG_SCHEDULED   = '⏰ Restarting now…'
MSG_CRASH       = '⏰ Restarting now… (Game Crashed)'
# ────────────────────────────────────────────────


def count_roblox() -> int:
    return sum(1 for p in psutil.process_iter(['name'])
               if p.info['name'] and p.info['name'].lower() == PROCESS_NAME)


def kill_roblox() -> None:
    for p in psutil.process_iter(['name']):
        if p.info['name'] and p.info['name'].lower() == PROCESS_NAME:
            try:
                p.kill()
            except psutil.Error:
                pass


def click_button() -> None:
    x, y = BUTTON_COORDS
    pyautogui.moveTo(x, y, duration=0.2)
    pyautogui.click()


def send_webhook(msg: str) -> None:
    for url in WEBHOOK_URLS:
        try:
            requests.post(url, json={"content": msg}, timeout=10)
        except requests.RequestException:
            pass


def warn_via_timestamp(seconds_ahead: int = WARNING_OFFSET) -> None:
    epoch = int(time.time()) + seconds_ahead
    send_webhook(f"⚠️  The macro will restart <t:{epoch}:R> (<t:{epoch}:t> ET).")


class MacroWatchdog(threading.Thread):
    def __init__(self, status_cb):
        super().__init__(daemon=True)
        self._stop_evt = threading.Event()
        self.status_cb = status_cb

    def stop(self):
        self._stop_evt.set()

    # -------------------------------------------------
    def perform_restart(self, announce: str):
        global BUTTON_COORDS
        send_webhook(announce)
        for attempt in range(1, MAX_RETRIES + 1):
            if self._stop_evt.is_set():
                return
            kill_roblox()
            time.sleep(1)
            click_button()
            for _ in range(RETRY_DELAY):
                if self._stop_evt.is_set():
                    return
                time.sleep(1)
            if count_roblox() > 0:
                return  # success
            if attempt < MAX_RETRIES:
                send_webhook(f"⚠️  Restart attempt {attempt} failed — retrying…")
            else:
                send_webhook(f"❌ Restart failed after {MAX_RETRIES} attempts <@{PING_USER_ID}>")
                self.stop()
                self.status_cb('Failed')
                return

    # -------------------------------------------------
    def run(self):
        self.status_cb('Running')
        last_seen = count_roblox()
        warned = False
        cycle_start = dt.datetime.now()

        while not self._stop_evt.is_set():
            time.sleep(5)
            current = count_roblox()
            if current == 1 and last_seen > 1:
                # Early restart due to crash
                self.perform_restart(MSG_CRASH)
                cycle_start, warned = dt.datetime.now(), False
            last_seen = current

            elapsed = (dt.datetime.now() - cycle_start).total_seconds()
            if not warned and elapsed >= BASE_INTERVAL - WARNING_OFFSET:
                warn_via_timestamp(WARNING_OFFSET)
                warned = True
            if elapsed >= BASE_INTERVAL:
                # Scheduled restart after countdown
                self.perform_restart(MSG_SCHEDULED)
                cycle_start, warned = dt.datetime.now(), False

        self.status_cb('Stopped')


class MacroGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title('Roblox Macro Watchdog')
        self.root.resizable(False, False)

        # Status row
        self.status_var = tk.StringVar(value='Stopped')
        ttk.Label(root, text='Status:').grid(row=0, column=0, padx=10, pady=5, sticky='e')
        ttk.Label(root, textvariable=self.status_var).grid(row=0, column=1, padx=10, pady=5, sticky='w')

        # Coord display + picker
        self.coords_var = tk.StringVar(value=str(BUTTON_COORDS))
        ttk.Label(root, text='Button coord:').grid(row=1, column=0, padx=10, pady=5, sticky='e')
        ttk.Label(root, textvariable=self.coords_var).grid(row=1, column=1, padx=10, pady=5, sticky='w')
        ttk.Button(root, text='Set Button Coord', command=self.pick_coord).grid(row=1, column=2, padx=10, pady=5)

        # Controls
        self.start_btn = ttk.Button(root, text='Start', command=self.start)
        self.start_btn.grid(row=2, column=0, padx=10, pady=10)
        self.stop_btn = ttk.Button(root, text='Stop', command=self.stop, state=tk.DISABLED)
        self.stop_btn.grid(row=2, column=1, padx=10, pady=10)
        ttk.Button(root, text='Test Countdown', command=self.test_countdown).grid(row=2, column=2, padx=10, pady=10)

        self.watchdog: MacroWatchdog | None = None
        self.root.protocol('WM_DELETE_WINDOW', self.on_close)

    # ------- GUI helpers
    def set_status(self, txt: str):
        self.status_var.set(txt)

    def start(self):
        if self.watchdog and self.watchdog.is_alive():
            return
        self.watchdog = MacroWatchdog(self.set_status)
        self.watchdog.start()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

    def stop(self):
        if self.watchdog and self.watchdog.is_alive():
            self.watchdog.stop()
            self.watchdog.join(timeout=1)
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.set_status('Stopped')

    def on_close(self):
        self.stop()
        self.root.destroy()

    # Coord picker
    def pick_coord(self):
        messagebox.showinfo("Capture coordinate",
                            "Move the mouse over the macro's PLAY button.\nCoordinates will be captured in 5 seconds.")
        self.root.after(100, self._capture_coord_async)

    def _capture_coord_async(self):
        def capture():
            time.sleep(5)
            x, y = pyautogui.position()
            global BUTTON_COORDS
            BUTTON_COORDS = (x, y)
            self.coords_var.set(str(BUTTON_COORDS))
            messagebox.showinfo("Coordinate captured", f"New coord: {BUTTON_COORDS}")
        threading.Thread(target=capture, daemon=True).start()

    # Test countdown
    def test_countdown(self):
        warn_via_timestamp(WARNING_OFFSET)
        messagebox.showinfo("Test sent", "Countdown test message sent to all webhooks.")


if __name__ == '__main__':
    pyautogui.FAILSAFE = True
    root = tk.Tk()
    app = MacroGUI(root)

    cfg = load_config()
    if not cfg.get("has_shown_manual", False):
        show_manual()
        cfg["has_shown_manual"] = True
        save_config(cfg)

    root.mainloop()

