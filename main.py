"""
ESP32 Température / Humidité (WiFi) - application Kivy
Interroge http://<IP>/data toutes les 2 s. Aucune dépendance en plus de Kivy.

Test sur PC :  pip install kivy   puis   python main.py
"""

import json
import threading
import time
import urllib.request
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.graphics import Color, Ellipse
from kivy.metrics import dp
from kivy.storage.jsonstore import JsonStore
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
import os

POLL_SECONDS = 2


class Led(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.size_hint = (None, None)
        self.size = (dp(50), dp(50))
        self.on = False
        self.bind(pos=self.redraw, size=self.redraw)

    def set(self, on):
        self.on = on
        self.redraw()

    def redraw(self, *_):
        self.canvas.clear()
        with self.canvas:
            Color(*((0.95, 0.77, 0.06) if self.on else (0.50, 0.55, 0.55)))
            Ellipse(pos=self.pos, size=self.size)


class EspApp(App):
    title = "ESP32 Température / Humidité"

    def build(self):
        self.stop_event = threading.Event()
        self.thread = None
        self.running = False
        self.led_on = False
        self.store = JsonStore(os.path.join(self.user_data_dir, "settings.json"))

        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))

        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        saved = self.store.get("ip")["value"] if self.store.exists("ip") else ""
        self.ti_ip = TextInput(text=saved, hint_text="IP de l'ESP32 (ex. 192.168.1.50)",
                               multiline=False, input_filter=None)
        row.add_widget(self.ti_ip)
        self.btn_connect = Button(text="Démarrer", size_hint_x=0.4,
                                  on_release=lambda *_: self.toggle())
        row.add_widget(self.btn_connect)
        root.add_widget(row)

        mes = BoxLayout(size_hint_y=None, height=dp(120))
        self.lbl_temp = Label(text="-- °C", font_size="36sp", bold=True,
                              color=(0.75, 0.22, 0.17, 1))
        self.lbl_hum = Label(text="-- %", font_size="36sp", bold=True,
                             color=(0.14, 0.44, 0.64, 1))
        mes.add_widget(self.lbl_temp)
        mes.add_widget(self.lbl_hum)
        root.add_widget(mes)

        led_row = BoxLayout(size_hint_y=None, height=dp(60), spacing=dp(8))
        self.led = Led()
        led_row.add_widget(self.led)
        led_row.add_widget(Button(text="LED ON",
                                  on_release=lambda *_: self.set_led(1)))
        led_row.add_widget(Button(text="LED OFF",
                                  on_release=lambda *_: self.set_led(0)))
        root.add_widget(led_row)

        self.lbl_log = Label(text="", size_hint_y=None, halign="left",
                             valign="top", font_size="12sp")
        self.lbl_log.bind(
            width=lambda w, v: setattr(w, "text_size", (v, None)),
            texture_size=lambda w, v: setattr(w, "height", v[1]))
        self.scroll = ScrollView()
        self.scroll.add_widget(self.lbl_log)
        root.add_widget(self.scroll)

        self.lbl_status = Label(text="Arrêté", size_hint_y=None, height=dp(28))
        root.add_widget(self.lbl_status)
        return root

    # ------------------------------------------------------------ Réseau
    def base_url(self):
        ip = self.ti_ip.text.strip()
        if not ip:
            return None
        if not ip.startswith("http"):
            ip = "http://" + ip
        return ip.rstrip("/")

    def toggle(self):
        if self.running:
            self.stop()
        else:
            self.start()

    def start(self):
        if not self.base_url():
            self.log("Saisissez l'adresse IP de l'ESP32")
            return
        self.store.put("ip", value=self.ti_ip.text.strip())
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.poll_loop, daemon=True)
        self.thread.start()
        self.running = True
        self.btn_connect.text = "Arrêter"
        self.lbl_status.text = "Interrogation de " + self.base_url()

    def stop(self):
        self.stop_event.set()
        self.running = False
        self.btn_connect.text = "Démarrer"
        self.lbl_status.text = "Arrêté"
        self.lbl_temp.text = "-- °C"
        self.lbl_hum.text = "-- %"

    def fetch(self, path):
        with urllib.request.urlopen(self.base_url() + path, timeout=3) as r:
            return json.loads(r.read().decode("utf-8"))

    def poll_loop(self):
        failures = 0
        while not self.stop_event.is_set():
            try:
                data = self.fetch("/data")
                failures = 0
                self.show(data)
            except Exception as exc:
                failures += 1
                if failures == 1 or failures % 10 == 0:
                    self.show_error(str(exc))
            self.stop_event.wait(POLL_SECONDS)

    def set_led(self, state):
        if not self.base_url():
            return

        def work():
            try:
                data = self.fetch(f"/led?state={state}")
                self.show_led(bool(data.get("led")))
                self.log_main("LED " + ("allumée" if state else "éteinte"))
            except Exception as exc:
                self.log_main(f"Erreur LED : {exc}")
        threading.Thread(target=work, daemon=True).start()

    # --------------------------------------------------- Mise à jour UI
    @mainthread
    def show(self, data):
        t, h = data.get("temp"), data.get("hum")
        self.lbl_temp.text = "Erreur" if t is None else f"{t:.1f} °C"
        self.lbl_hum.text = "Erreur" if h is None else f"{h:.1f} %"
        self.led.set(bool(data.get("led")))
        self.lbl_status.text = "Connecté - " + datetime.now().strftime("%H:%M:%S")

    @mainthread
    def show_led(self, on):
        self.led.set(on)

    @mainthread
    def show_error(self, msg):
        self.lbl_status.text = "Hors ligne"
        self.log(f"Impossible de joindre l'ESP32 : {msg}")

    @mainthread
    def log_main(self, message):
        self.log(message)

    def log(self, message):
        horodatage = datetime.now().strftime("%H:%M:%S")
        lines = (self.lbl_log.text + f"{horodatage}  {message}\n").splitlines()
        self.lbl_log.text = "\n".join(lines[-100:])
        Clock.schedule_once(lambda dt: setattr(self.scroll, "scroll_y", 0), 0.05)

    def on_stop(self):
        self.stop_event.set()


if __name__ == "__main__":
    EspApp().run()
