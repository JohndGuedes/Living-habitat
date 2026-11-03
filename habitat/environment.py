"""Ambiente vivo: hora do dia e clima de verdade, da localização do PC.

- Localização: pelo IP da internet (ipinfo.io). Se falhar, usa LOCATION_FALLBACK.
  Pode fixar em config.LOCATION para não consultar o IP.
- Clima + nascer/pôr do sol + fuso: Open-Meteo (grátis, sem chave).
- Hora: a do FUSO DA LOCALIZAÇÃO (vem da API), para o pôr do sol do jogo bater
  com o de verdade mesmo se o relógio do PC estiver em outro fuso. Sem
  internet, usa o relógio do PC.

Tudo da rede roda numa thread em segundo plano; o jogo nunca trava esperando.

Visual:
- Luz ambiente: cor multiplicada sobre a cena, interpolada entre
  noite -> amanhecer -> dia -> tarde -> entardecer -> noite.
- Chuva: gotas, respingos, céu mais escuro; trovoada pisca relâmpagos.
- `darkness` (0 = dia claro, 1 = noite) é usado pelas luzes (fogueira, janelas).
"""
import json
import logging
import math
import random
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import pygame

from .config import LOCATION, LOCATION_FALLBACK, WEATHER_REFRESH_MIN

log = logging.getLogger(__name__)

# --- Cores de luz ambiente (multiplicam a cena) ---
NIGHT = (62, 74, 128)
DAWN = (226, 176, 170)
DAY = (255, 255, 255)
AFTERNOON = (255, 226, 186)
DUSK = (236, 150, 120)

# Códigos WMO de clima -> intensidade de chuva (0..1)
RAIN_CODES = {51: 0.25, 53: 0.35, 55: 0.45, 56: 0.35, 57: 0.45,
              61: 0.5, 63: 0.75, 65: 1.0, 66: 0.6, 67: 0.9,
              80: 0.5, 81: 0.8, 82: 1.0, 95: 1.0, 96: 1.0, 99: 1.0}
THUNDER_CODES = {95, 96, 99}

# Atalhos de teste (tecla T / R)
TIME_PRESETS = [None, ("Dia", 10 * 60), ("Tarde", 16 * 60 + 30), ("Noite", 21 * 60)]
RAIN_PRESETS = [None, 0.8, 0.0]


def _http_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "LivingHabitat/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


class WeatherService:
    """Busca localização e clima numa thread. Leia `self.data` (dict ou None)."""

    def __init__(self):
        self.location = None  # (lat, lon, cidade)
        self.data = None      # último clima recebido
        self.error = None
        threading.Thread(target=self._run, daemon=True, name="clima").start()

    def _locate(self):
        if LOCATION:
            return LOCATION
        try:
            info = _http_json("https://ipinfo.io/json")
            lat, lon = (float(v) for v in info["loc"].split(","))
            return lat, lon, info.get("city") or "?"
        except Exception as e:  # sem internet, bloqueado etc.
            log.warning("não deu para achar a localização pelo IP (%s); usando %s", e, LOCATION_FALLBACK[2])
            return LOCATION_FALLBACK

    def _run(self):
        while True:
            try:
                if self.location is None:
                    self.location = self._locate()
                lat, lon, city = self.location
                w = _http_json(
                    "https://api.open-meteo.com/v1/forecast"
                    f"?latitude={lat}&longitude={lon}"
                    "&current=temperature_2m,precipitation,rain,showers,weather_code,cloud_cover,is_day"
                    "&daily=sunrise,sunset&timezone=auto&forecast_days=1")
                cur = w["current"]
                self.data = {
                    "city": city,
                    "temp": cur.get("temperature_2m"),
                    "code": cur.get("weather_code", 0),
                    "precip": cur.get("precipitation", 0) or 0,
                    "clouds": cur.get("cloud_cover", 0) or 0,
                    "utc_offset": w.get("utc_offset_seconds"),
                    "sunrise": _minutes(w["daily"]["sunrise"][0]),
                    "sunset": _minutes(w["daily"]["sunset"][0]),
                    "fetched": time.time(),
                }
                self.error = None
                log.info("clima em %s: código %s, %.1f mm, %s°C", city, self.data["code"],
                         self.data["precip"], self.data["temp"])
                time.sleep(WEATHER_REFRESH_MIN * 60)
            except Exception as e:
                self.error = str(e)
                log.warning("falha ao buscar o clima (%s); tentando de novo em 1 min", e)
                time.sleep(60)


def _minutes(iso: str) -> int:
    """'2026-11-02T05:36' -> minutos desde a meia-noite."""
    hh, mm = iso[11:16].split(":")
    return int(hh) * 60 + int(mm)


def _lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


class Environment:
    def __init__(self, width: int, height: int, online: bool = True):
        self.w, self.h = width, height
        self.weather = WeatherService() if online else None
        self.time_preset = 0   # índice em TIME_PRESETS (0 = automático)
        self.rain_preset = 0   # índice em RAIN_PRESETS (0 = automático)
        self.rain = 0.0        # intensidade atual (suavizada)
        self.light = DAY       # cor ambiente atual
        self.darkness = 0.0
        self.minute = 0        # minuto do dia em uso
        self.phase = "Dia"
        self.drops = []        # [x, y, velocidade, comprimento]
        self.splashes = []     # [x, y, vida]
        self.flash = 0.0
        self.rng = random.Random()
        self.overlay = pygame.Surface((width, height))
        self.rain_layer = pygame.Surface((width, height), pygame.SRCALPHA)
        self.font = pygame.font.Font(None, 24)

    # ---------- entradas ----------
    @property
    def data(self):
        return self.weather.data if self.weather else None

    def cycle_time(self):
        self.time_preset = (self.time_preset + 1) % len(TIME_PRESETS)

    def cycle_rain(self):
        self.rain_preset = (self.rain_preset + 1) % len(RAIN_PRESETS)

    def now_minutes(self) -> float:
        """Minuto do dia no fuso da localização (ou do PC, sem dados)."""
        d = self.data
        if d and d.get("utc_offset") is not None:
            now = datetime.now(timezone.utc) + timedelta(seconds=d["utc_offset"])
        else:
            now = datetime.now()
        return now.hour * 60 + now.minute + now.second / 60

    def target_rain(self) -> float:
        preset = RAIN_PRESETS[self.rain_preset]
        if preset is not None:
            return preset
        d = self.data
        if not d:
            return 0.0
        r = RAIN_CODES.get(d["code"], 0.0)
        if not r and d["precip"] > 0.1:  # está caindo água mesmo sem código de chuva
            r = min(1.0, 0.3 + d["precip"] / 4)
        return r

    def thunder(self) -> bool:
        d = self.data
        if RAIN_PRESETS[self.rain_preset] is not None:
            return False
        return bool(d and d["code"] in THUNDER_CODES)

    # ---------- luz do dia ----------
    def _keyframes(self):
        d = self.data
        sr = d["sunrise"] if d else 6 * 60
        ss = d["sunset"] if d else 18 * 60
        return [(sr - 50, NIGHT), (sr, DAWN), (sr + 70, DAY), (15 * 60, DAY),
                (ss - 70, AFTERNOON), (ss, DUSK), (ss + 50, NIGHT)]

    def _light_at(self, minute: float):
        kf = self._keyframes()
        if minute <= kf[0][0] or minute >= kf[-1][0]:
            return NIGHT
        for (m0, c0), (m1, c1) in zip(kf, kf[1:]):
            if m0 <= minute <= m1:
                return _lerp(c0, c1, (minute - m0) / max(1, m1 - m0))
        return DAY

    def _phase_name(self, minute: float) -> str:
        d = self.data
        sr = d["sunrise"] if d else 6 * 60
        ss = d["sunset"] if d else 18 * 60
        if minute < sr - 20 or minute >= ss + 30:
            return "Noite"
        if minute < sr + 40:
            return "Amanhecer"
        if minute < 12 * 60:
            return "Dia"
        if minute < ss - 20:
            return "Tarde"
        return "Entardecer"

    # ---------- atualização ----------
    def update(self, dt: float):
        preset = TIME_PRESETS[self.time_preset]
        self.minute = preset[1] if preset else self.now_minutes()
        self.phase = self._phase_name(self.minute)

        # chuva sobe/desce aos poucos
        target = self.target_rain()
        self.rain += (target - self.rain) * min(1.0, dt * 0.8)
        if abs(self.rain - target) < 0.01:
            self.rain = target

        light = self._light_at(self.minute)
        if self.rain > 0.02:  # céu fechado: mais escuro e azulado
            light = _lerp(light, (light[0] * 0.62, light[1] * 0.66, light[2] * 0.76), self.rain)
        self.light = light
        lum = (0.3 * light[0] + 0.59 * light[1] + 0.11 * light[2]) / 255
        self.darkness = max(0.0, min(1.0, (1 - lum) / 0.65))

        self._update_rain(dt)
        if self.thunder() and self.rng.random() < dt / 9:  # relâmpago de vez em quando
            self.flash = 0.35
        self.flash = max(0.0, self.flash - dt)

    def _update_rain(self, dt):
        want = int(420 * self.rain)
        while len(self.drops) < want:
            self.drops.append([self.rng.uniform(-60, self.w), self.rng.uniform(-self.h, 0),
                               self.rng.uniform(700, 950), self.rng.uniform(14, 26)])
        if len(self.drops) > want:
            del self.drops[want:]
        for d in self.drops:
            d[1] += d[2] * dt
            d[0] += 90 * dt  # vento leve
            if d[1] > self.h or (d[1] > 40 and self.rng.random() < dt * 1.6):
                if d[1] > 40:  # bateu no chão: respingo
                    self.splashes.append([d[0], min(d[1], self.h - 2), 0.25])
                d[0], d[1] = self.rng.uniform(-60, self.w), self.rng.uniform(-80, -10)
        for s in self.splashes:
            s[2] -= dt
        self.splashes = [s for s in self.splashes if s[2] > 0]

    # ---------- desenho ----------
    def apply_light(self, surface: pygame.Surface):
        """Escurece/colore a cena conforme a hora e o clima (chamar ANTES das luzes)."""
        if self.light != DAY:
            self.overlay.fill(self.light)
            surface.blit(self.overlay, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

    def draw_weather(self, surface: pygame.Surface):
        """Chuva e relâmpago (chamar DEPOIS das luzes)."""
        if self.drops or self.splashes:
            self.rain_layer.fill((0, 0, 0, 0))
            a = round(90 + 60 * self.rain)
            for x, y, _, ln in self.drops:
                pygame.draw.line(self.rain_layer, (196, 210, 235, a), (x, y), (x - ln * 0.12, y - ln), 2)
            for x, y, life in self.splashes:
                r = round(10 * (1 - life / 0.25)) + 2
                pygame.draw.ellipse(self.rain_layer, (210, 222, 240, round(400 * life)),
                                    (x - r, y - r // 3, r * 2, r * 2 // 3), 1)
            surface.blit(self.rain_layer, (0, 0))
        if self.flash:
            self.overlay.fill([round(255 * min(1.0, self.flash * 2.4))] * 3)
            surface.blit(self.overlay, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def hud_text(self) -> str:
        m = int(self.minute)
        parts = [f"{m // 60:02d}:{m % 60:02d}", self.phase]
        d = self.data
        if d:
            parts.append(f"{d['city']} {d['temp']:.0f}°C" if d.get("temp") is not None else d["city"])
        elif self.weather and self.weather.error:
            parts.append("sem internet")
        else:
            parts.append("buscando clima...")
        if self.rain > 0.05 or self.target_rain() > 0:
            parts.append("Trovoada" if self.thunder() else "Chovendo")
        manual = []
        if TIME_PRESETS[self.time_preset]:
            manual.append("hora")
        if RAIN_PRESETS[self.rain_preset] is not None:
            manual.append("chuva")
        if manual:
            parts.append(f"(manual: {', '.join(manual)})")
        return "  ·  ".join(parts)

    def draw_hud(self, surface: pygame.Surface):
        txt = self.font.render(self.hud_text(), True, (240, 240, 230))
        bg = pygame.Surface((txt.get_width() + 16, txt.get_height() + 10), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 120))
        x = self.w - bg.get_width() - 8
        surface.blit(bg, (x, 8))
        surface.blit(txt, (x + 8, 13))
