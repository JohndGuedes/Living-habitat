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
        self._anim_time = 0.0
        self._moon_cache = {}   # (phase_bucket, radius) -> Surface
        self._glow_cache = {}   # (radius, color) -> Surface gaussiana difusa
        # Estrelinhas fixas em torno do arco celeste no topo da tela
        rng_stars = random.Random(77)
        self._arc_stars = [
            (rng_stars.uniform(-96, 96), rng_stars.uniform(-12, 14),
             rng_stars.uniform(0.0, math.tau), rng_stars.choice((1, 1, 2)))
            for _ in range(16)
        ]

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
    def sun(self):
        """(lado, comprimento, força) da sombra do sol, ou None à noite.
        lado: -1 = sombra para a esquerda (manhã) ... +1 = para a direita (fim da tarde);
        comprimento: curto ao meio-dia, comprido perto do nascer/pôr do sol."""
        d = self.data or {}
        sr, ss = d.get("sunrise", 6 * 60), d.get("sunset", 18 * 60)
        if not (sr < self.minute < ss):
            return None
        f = (self.minute - sr) / (ss - sr)               # 0 = nascer, 1 = pôr
        side = 2 * f - 1
        length = 0.35 + 1.1 * abs(side) ** 1.5
        strength = 0.55 * (1 - self.darkness) * (1 - 0.5 * min(1.0, self.rain))
        return side, length, strength

    def update(self, dt: float):
        self._anim_time += dt
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

    # ---------- fase da lua e indicador celeste de horário ----------
    def moon_phase(self) -> float:
        """Fase astronômica da lua no dia atual: 0.0 = Lua Nova, 0.25 = Quarto Crescente,
        0.5 = Lua Cheia, 0.75 = Quarto Minguante."""
        now_utc = datetime.now(timezone.utc)
        # Lua nova de referência: 2000-01-06 18:14 UTC; ciclo sinódico = 29,530588853 dias
        ref = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
        days = (now_utc - ref).total_seconds() / 86400.0
        return (days / 29.530588853) % 1.0

    def moon_phase_name(self, phase: float | None = None) -> str:
        """Nome em português da fase da lua do dia."""
        p = self.moon_phase() if phase is None else (phase % 1.0)
        names = (
            "Lua Nova",
            "Lua Crescente",
            "Quarto Crescente",
            "Crescente Gibosa",
            "Lua Cheia",
            "Minguante Gibosa",
            "Quarto Minguante",
            "Lua Minguante",
        )
        idx = int(((p + 1 / 16) % 1.0) * 8)
        return names[idx]

    def _soft_glow(self, radius: int, color: tuple[int, int, int], max_alpha: int = 120) -> pygame.Surface:
        """Halo difuso gaussiano (sem anéis marcados)."""
        key = (radius, color, max_alpha)
        cached = self._glow_cache.get(key)
        if cached is not None:
            return cached
        half = max(8, radius // 2)
        small = pygame.Surface((half * 2, half * 2), pygame.SRCALPHA)
        c = half - 0.5
        for y in range(half * 2):
            for x in range(half * 2):
                d = math.hypot(x - c, y - c) / half
                if d < 1.0:
                    k = math.exp(-3.2 * d * d) - math.exp(-3.2)
                    a = round(max_alpha * max(0.0, k))
                    if a > 0:
                        small.set_at((x, y), (*color, a))
        out = pygame.transform.smoothscale(small, (radius * 2, radius * 2))
        self._glow_cache[key] = out
        return out

    def _moon_disc(self, radius: int, phase: float) -> pygame.Surface:
        """Renderiza o disco da lua com a fase exata do dia (terminador esférico 3D + mares lunares)."""
        bucket = round((phase % 1.0) * 96) % 96
        key = (bucket, radius)
        cached = self._moon_cache.get(key)
        if cached is not None:
            return cached

        p = bucket / 96.0
        # Garante que mesmo perto da Lua Nova exista um fino crescente prateado bem legível
        dist_new = min(p, 1.0 - p)
        if 0.015 < dist_new < 0.11:
            p = 0.11 if p < 0.5 else 0.89
        angle = p * math.tau
        # Vetor de direção da luz solar no referencial da lua:
        # p=0 -> (0, -1) (Lua Nova, iluminada por trás)
        # p=0.25 -> (1, 0) (Quarto Crescente, metade direita iluminada)
        # p=0.5 -> (0, 1) (Lua Cheia, totalmente iluminada de frente)
        # p=0.75 -> (-1, 0) (Quarto Minguante, metade esquerda iluminada)
        sx, sz = math.sin(angle), -math.cos(angle)

        ss = 2  # superamostragem 2x para borda suave
        R = radius * ss
        size = R * 2 + 4
        cx = cy = size / 2.0
        surf = pygame.Surface((size, size), pygame.SRCALPHA)

        # Manchas suaves dos mares lunares (x, y normalizados, raio, intensidade)
        maria = (
            (-0.28, -0.22, 0.34, 0.12),
            (0.22, -0.18, 0.28, 0.10),
            (0.32, 0.15, 0.24, 0.09),
            (-0.18, 0.28, 0.25, 0.08),
            (0.02, -0.02, 0.20, 0.07),
        )

        for y in range(size):
            ny = (y + 0.5 - cy) / R
            if abs(ny) >= 1.0:
                continue
            for x in range(size):
                nx = (x + 0.5 - cx) / R
                r2 = nx * nx + ny * ny
                if r2 >= 1.0:
                    continue
                r = math.sqrt(r2)
                edge_aa = max(0.0, min(1.0, (1.0 - r) * R * 0.9))
                nz = math.sqrt(max(0.0, 1.0 - r2))

                # Textura sutil de mares lunares
                dip = 0.0
                for mx, my, mr, md in maria:
                    d2 = (nx - mx) ** 2 + (ny - my) ** 2
                    if d2 < mr * mr:
                        dip += md * (1.0 - d2 / (mr * mr))

                # Iluminação esférica ao longo do terminador da fase lunar
                dot = nx * sx + nz * sz
                lit = max(0.0, min(1.0, (dot + 0.05) / 0.12))

                # Lado iluminado (marfim/prata) vs lado na sombra (luz cinérea azulada)
                limb = 0.90 + 0.10 * nz
                bright = (1.0 - dip) * limb
                lit_r = 255 * bright
                lit_g = 248 * bright
                lit_b = 224 * bright

                dark_k = (0.90 - dip * 0.4)
                dark_r = 56 * dark_k
                dark_g = 70 * dark_k
                dark_b = 108 * dark_k

                cr = round(dark_r + (lit_r - dark_r) * lit)
                cg = round(dark_g + (lit_g - dark_g) * lit)
                cb = round(dark_b + (lit_b - dark_b) * lit)

                # Fino aro prateado na borda para destacar mesmo na Lua Nova
                if r > 0.85:
                    rim = (r - 0.85) / 0.15
                    rim_strength = rim * (0.45 + 0.45 * lit)
                    cr = min(255, round(cr + (235 - cr) * rim_strength))
                    cg = min(255, round(cg + (242 - cg) * rim_strength))
                    cb = min(255, round(cb + (255 - cb) * rim_strength))

                surf.set_at((x, y), (cr, cg, cb, round(255 * edge_aa)))

        out = pygame.transform.smoothscale(surf, (radius * 2 + 2, radius * 2 + 2))
        self._moon_cache[key] = out
        return out

    def _draw_sun_icon(self, surface: pygame.Surface, x: float, y: float, day_t: float, alpha: float = 1.0):
        """Desenha o solzinho mudando gradativamente de cor e brilho do amanhecer ao pôr do sol."""
        if alpha <= 0.02:
            return
        # Paleta gradativa conforme a posição do sol no dia (0 = nascer, 0.5 = meio-dia, 1 = pôr)
        if day_t < 0.2:
            k = day_t / 0.2
            core = _lerp((255, 165, 110), (255, 238, 150), k)
            halo = _lerp((255, 120, 90), (255, 200, 90), k)
        elif day_t < 0.75:
            k = (day_t - 0.2) / 0.55
            core = _lerp((255, 242, 160), (255, 228, 135), k)
            halo = _lerp((255, 205, 95), (255, 180, 80), k)
        else:
            k = (day_t - 0.75) / 0.25
            core = _lerp((255, 228, 135), (255, 138, 92), k)
            halo = _lerp((255, 180, 80), (240, 95, 75), k)

        glow = self._soft_glow(30, halo, round(135 * alpha))
        surface.blit(glow, glow.get_rect(center=(round(x), round(y))))

        size = 56
        icon = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size // 2

        # Raios solares girando suavemente
        rot = self._anim_time * 0.45
        num_rays = 8
        for i in range(num_rays):
            ang = rot + i * (math.tau / num_rays)
            pulse = 1.0 + 0.12 * math.sin(self._anim_time * 2.4 + i)
            r_in = 12.0
            r_out = (17.0 if i % 2 == 0 else 14.5) * pulse
            x0 = c + math.cos(ang) * r_in
            y0 = c + math.sin(ang) * r_in
            x1 = c + math.cos(ang) * r_out
            y1 = c + math.sin(ang) * r_out
            pygame.draw.line(icon, (*core, round(230 * alpha)), (x0, y0), (x1, y1), 2)

        # Disco solar
        pygame.draw.circle(icon, (*halo, round(240 * alpha)), (c, c), 10)
        pygame.draw.circle(icon, (*core, round(255 * alpha)), (c, c), 8)
        pygame.draw.circle(icon, (255, 252, 235, round(225 * alpha)), (c - 2, c - 2), 3)

        surface.blit(icon, icon.get_rect(center=(round(x), round(y))))

    def _draw_moon_icon(self, surface: pygame.Surface, x: float, y: float, phase: float, alpha: float = 1.0):
        """Desenha a lua com a fase real do dia e halo difuso prateado/azulado."""
        if alpha <= 0.02:
            return
        illum = 0.5 * (1.0 - math.cos(phase * math.tau))
        glow_alpha = round((95 + 50 * illum) * alpha)
        glow = self._soft_glow(28, (175, 210, 255), glow_alpha)
        surface.blit(glow, glow.get_rect(center=(round(x), round(y))))

        disc = self._moon_disc(11, phase)
        if alpha < 0.99:
            disc = disc.copy()
            disc.set_alpha(round(255 * alpha))
        surface.blit(disc, disc.get_rect(center=(round(x), round(y))))

    def hud_text(self) -> str:
        """Resumo discreto do estado celeste (sem cidade, temperatura ou relógio numérico)."""
        if self.phase == "Noite":
            return f"{self.phase}  ·  {self.moon_phase_name()}"
        return self.phase

    def draw_hud(self, surface: pygame.Surface):
        """Indicador visual de horário no topo-centro da tela: arco celeste onde o Sol (de dia)
        ou a Lua (à noite, com a fase real do dia) avançam gradativamente conforme o horário."""
        d = self.data or {}
        sr = d.get("sunrise", 6 * 60)
        ss = d.get("sunset", 18 * 60)
        m = self.minute % 1440

        cx = self.w // 2
        base_y = 38       # linha do horizonte nas pontas do arco
        arch_h = 18       # altura do zênite no centro (y = 20)
        span_x = 84       # meia-largura do arco celeste

        def arc_pos(t: float) -> tuple[float, float]:
            t = max(0.0, min(1.0, t))
            px = cx + (t * 2.0 - 1.0) * span_x
            py = base_y - math.sin(t * math.pi) * arch_h
            return px, py

        # Calcula se estamos no ciclo diurno ou noturno e a fração contínua (0..1) do ciclo
        day_len = max(60.0, float(ss - sr))
        night_len = max(60.0, 1440.0 - day_len)
        is_daytime = sr <= m <= ss
        if is_daytime:
            day_t = (m - sr) / day_len
            night_t = 0.0
        else:
            day_t = 0.0
            night_dist = (m - ss) if m > ss else (1440.0 - ss + m)
            night_t = night_dist / night_len

        # Transição suave no nascer e no pôr do sol (+/- 28 min)
        twilight = 28.0
        dist_sr = min(abs(m - sr), 1440.0 - abs(m - sr))
        dist_ss = min(abs(m - ss), 1440.0 - abs(m - ss))
        if is_daytime:
            sun_alpha = 1.0
            moon_alpha = max(0.0, 1.0 - dist_sr / twilight) if m - sr < twilight else (
                max(0.0, 1.0 - dist_ss / twilight) if ss - m < twilight else 0.0
            )
        else:
            moon_alpha = 1.0
            sun_alpha = max(0.0, 1.0 - dist_ss / twilight) if dist_ss < twilight else (
                max(0.0, 1.0 - dist_sr / twilight) if dist_sr < twilight else 0.0
            )

        hud = pygame.Surface((240, 68), pygame.SRCALPHA)
        ox = cx - 120

        # Estrelinhas cintilando ao redor do arco durante a noite/crepúsculo
        if self.darkness > 0.15:
            star_k = min(1.0, (self.darkness - 0.15) / 0.65)
            for sx_off, sy_off, phase_s, s_rad in self._arc_stars:
                tw = 0.45 + 0.55 * math.sin(self._anim_time * 2.2 + phase_s)
                sa = round(185 * star_k * tw)
                if sa > 10:
                    px = round(120 + sx_off)
                    py = round(28 + sy_off)
                    pygame.draw.circle(hud, (230, 240, 255, sa), (px, py), s_rad)

        # Trilha do arco celeste (linha sutil + trilha percorrida até o horário atual)
        steps = 36
        pts = [arc_pos(i / steps) for i in range(steps + 1)]
        local_pts = [(round(px - ox), round(py)) for px, py in pts]
        track_col = (210, 224, 248, 65) if self.darkness > 0.4 else (255, 250, 232, 85)
        pygame.draw.aalines(hud, track_col, False, local_pts)

        active_t = day_t if is_daytime else night_t
        active_steps = max(1, round(active_t * steps))
        if active_steps >= 1:
            prog_col = (180, 215, 255, 160) if not is_daytime else (255, 225, 130, 175)
            pygame.draw.aalines(hud, prog_col, False, local_pts[:active_steps + 1])

        # Marcadores discretos de horizonte (nascer/pôr) e zênite (meio-dia/meia-noite)
        for t_mark, r_mark in ((0.0, 2), (0.5, 2), (1.0, 2)):
            mx, my = arc_pos(t_mark)
            pygame.draw.circle(hud, (240, 244, 252, 130), (round(mx - ox), round(my)), r_mark)

        surface.blit(hud, (ox, 0))

        # Desenha a Lua (com a fase real do dia) e/ou o Sol na posição exata do horário
        phase = self.moon_phase()
        if moon_alpha > 0.02:
            mt = night_t if not is_daytime else (1.0 if m - sr < twilight else 0.0)
            mx, my = arc_pos(mt)
            self._draw_moon_icon(surface, mx, my, phase, alpha=moon_alpha)

        if sun_alpha > 0.02:
            st = day_t if is_daytime else (1.0 if dist_ss < twilight else 0.0)
            sx, sy = arc_pos(st)
            self._draw_sun_icon(surface, sx, sy, st, alpha=sun_alpha)

        # Nuvem suave passando sob o astro quando está chovendo
        if self.rain > 0.08:
            ax, ay = arc_pos(active_t)
            ca = round(min(210, 230 * self.rain))
            cloud = pygame.Surface((46, 20), pygame.SRCALPHA)
            c_col = (185, 198, 220, ca) if self.darkness < 0.5 else (110, 125, 155, ca)
            pygame.draw.ellipse(cloud, c_col, (4, 6, 38, 12))
            pygame.draw.circle(cloud, c_col, (16, 9), 7)
            pygame.draw.circle(cloud, c_col, (27, 8), 8)
            surface.blit(cloud, cloud.get_rect(center=(round(ax + 6), round(ay + 9))))
