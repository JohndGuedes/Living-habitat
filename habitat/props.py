"""Objetos do cenário: casa, árvore, fogueira, boneco de treino.

Cada objeto tem uma BASE (x, y) = ponto onde encosta no chão (centro de
baixo). Ela serve para:
  - ordenar o desenho por profundidade (quem tem y maior fica na frente);
  - a área sólida (`footprint`: largura x profundidade, em px de tela) que o
    personagem não atravessa.

ARTE: se existir assets/sprites/world/<tipo>.png (imagem única) ou a pasta
assets/sprites/world/<tipo>/ (quadros de animação), ela é usada com a base no
centro de baixo da imagem. Senão, desenha um PROVISÓRIO por código (pixel art
simples em resolução de mundo, ampliada por WORLD_PIXEL).
"""
import math
import random

import pygame

from .assets import load_prop_frames
from .config import WORLD_PIXEL

P = WORLD_PIXEL
OUTLINE = (52, 36, 28)


def _canvas(w, h):
    return pygame.Surface((w, h), pygame.SRCALPHA)


def _up(surf, factor=P):
    """Amplia um desenho em px de mundo para px de tela (vizinho mais próximo)."""
    return pygame.transform.scale_by(surf, factor)


def _soft_ellipse(rx, ry, color, layers=6, alpha=14):
    """Elipse de bordas suaves (camadas sobrepostas), para sombras."""
    s = pygame.Surface((rx * 2, ry * 2), pygame.SRCALPHA)
    for i in range(layers):
        k = 1 - i / layers * 0.6
        r = pygame.Rect(0, 0, rx * 2 * k, ry * 2 * k)
        r.center = (rx, ry)
        pygame.draw.ellipse(s, (*color, alpha), r)
    return s


def radial_glow(radius, color):
    """Gradiente radial (fundo preto) para luz aditiva (BLEND_ADD)."""
    s = pygame.Surface((radius * 2, radius * 2))
    for i in range(radius, 0, -3):
        k = (1 - i / radius) ** 1.6
        pygame.draw.circle(s, [round(c * k) for c in color], (radius, radius), i)
    return s


def add_light(surface, glow, center, strength):
    """Soma uma luz na cena com intensidade 0..1."""
    if strength <= 0.01:
        return
    if strength < 0.99:
        glow = glow.copy()
        v = round(255 * strength)
        glow.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
    surface.blit(glow, glow.get_rect(center=center), special_flags=pygame.BLEND_ADD)


class Prop:
    kind = "prop"
    footprint = (0, 0)       # (largura, profundidade) da área sólida, px de tela
    frame_duration = 0.12

    def __init__(self, x: float, y: float, defn: dict):
        self.x, self.y = x, y
        self.defn = defn
        self.time = 0.0
        self.scale = defn.get("scale", 1)
        # "base_offset": px da arte original entre a borda de baixo e o ponto que toca o chão
        self.base_offset = defn.get("base_offset", 0) * self.scale
        art = load_prop_frames(self.kind, self.scale, defn.get("file"))
        self.has_art = art is not None          # False = usando o provisório
        self.frames = art or self.placeholder_frames()

    # --- arte provisória (cada tipo sobrescreve) ---
    def placeholder_frames(self) -> list[pygame.Surface]:
        s = _canvas(10, 10)
        s.fill((255, 0, 255))
        return [_up(s)]

    @property
    def solid(self) -> pygame.Rect | None:
        w, d = self.defn.get("footprint", self.footprint)
        if not w:
            return None
        return pygame.Rect(round(self.x - w / 2), round(self.y - d), w, d)

    def update(self, dt: float):
        self.time += dt

    def image(self) -> pygame.Surface:
        return self.frames[int(self.time / self.frame_duration) % len(self.frames)]

    def shadow_image(self) -> pygame.Surface:
        """Imagem usada na sombra do sol (sem o balanço da brisa)."""
        return self.image()

    def draw_ground(self, surface):
        """Camada do chão (sombras), desenhada antes de tudo."""

    def draw(self, surface, viewer=None):
        img = self.image()
        surface.blit(img, img.get_rect(midbottom=(round(self.x), round(self.y + self.base_offset))))

    def draw_light(self, surface, darkness: float = 0.0):
        """Luz, desenhada DEPOIS do escurecimento da noite/chuva.
        `darkness`: 0 = dia claro, 1 = noite."""

    def shade_at(self, x, y) -> float:
        """Fator de luz (1 = normal, <1 = na sombra) num ponto do chão."""
        return 1.0


class House(Prop):
    kind = "house"
    footprint = (350, 60)

    def placeholder_frames(self):
        W, H = 124, 112
        s = _canvas(W, H)
        # chaminé (atrás do telhado)
        s.fill(OUTLINE, (85, 3, 14, 26))
        s.fill((128, 122, 120), (86, 4, 12, 24))
        for y in range(8, 28, 5):
            s.fill((104, 98, 96), (86, y, 12, 1))
        # paredes de tábua
        s.fill(OUTLINE, (11, 49, 102, 60))
        s.fill((198, 160, 112), (12, 50, 100, 58))
        for x in range(20, 112, 8):
            s.fill((168, 128, 86), (x, 50, 1, 58))
        # telhado (trapézio) com fileiras de telhas
        roof = [(1, 54), (123, 54), (104, 13), (20, 13)]
        pygame.draw.polygon(s, (150, 52, 44), roof)
        for y in range(19, 54, 6):
            t = (y - 13) / 41
            x0, x1 = round(20 - 19 * t), round(104 + 19 * t)
            s.fill((112, 36, 32), (x0, y, x1 - x0, 1))
        pygame.draw.polygon(s, OUTLINE, roof, 1)
        s.fill((182, 76, 60), (21, 13, 83, 2))  # cumeeira clara
        # porta
        s.fill(OUTLINE, (53, 77, 20, 31))
        s.fill((110, 70, 42), (54, 78, 18, 30))
        s.fill((88, 54, 32), (62, 78, 1, 30))
        s.fill((236, 200, 90), (68, 92, 2, 2))
        # janelas com luz quente
        for wx in (23, 83):
            s.fill(OUTLINE, (wx - 1, 63, 20, 18))
            s.fill((255, 214, 122), (wx, 64, 18, 16))
            s.fill((240, 170, 80), (wx, 72, 18, 8))
            s.fill(OUTLINE, (wx + 8, 64, 2, 16))
            s.fill(OUTLINE, (wx, 71, 18, 2))
        # base de pedra
        s.fill((120, 116, 112), (9, 106, 106, 6))
        for x in range(11, 113, 9):
            s.fill((96, 92, 90), (x, 106, 1, 6))
        return [_up(s, 3)]  # um pouco maior que o resto, para a porta caber o Knight

    # Janelas (relativas à base) do desenho provisório; com arte própria,
    # defina "lights": [(dx, dy), ...] em scene.py.
    WINDOWS = [(-90, -120), (90, -120)]

    def __init__(self, x, y, defn):
        super().__init__(x, y, defn)
        self.windows = defn.get("lights", [] if self.has_art else self.WINDOWS)
        self.glow = radial_glow(80, (150, 110, 50))

    def draw_light(self, surface, darkness=0.0):
        for dx, dy in self.windows:
            add_light(surface, self.glow, (round(self.x + dx), round(self.y + dy)), darkness)

    def draw_ground(self, surface):
        sh = _soft_ellipse(220, 34, (20, 30, 20), alpha=18)
        surface.blit(sh, sh.get_rect(center=(round(self.x), round(self.y - 4))))


class Tree(Prop):
    kind = "tree"
    footprint = (34, 16)
    SHADE_LIGHT = 0.68  # quanto o personagem escurece na sombra

    def __init__(self, x, y, defn):
        super().__init__(x, y, defn)
        # sombra projetada no chão (deslocada para a direita: sol à esquerda)
        self.shade_center = (x + 40, y + 4)
        self.shade_r = defn.get("shade", (200, 64))
        self.shade_surf = _soft_ellipse(*self.shade_r, (10, 40, 16), layers=7, alpha=20)

    def placeholder_frames(self):
        W, H = 156, 176
        s = _canvas(W, H)
        # tronco + raízes
        s.fill(OUTLINE, (69, 104, 18, 70))
        s.fill((116, 78, 46), (70, 104, 16, 70))
        s.fill((92, 60, 36), (80, 104, 6, 70))
        for x, w in ((62, 9), (85, 9)):
            s.fill(OUTLINE, (x, 168, w, 7))
            s.fill((116, 78, 46), (x + 1, 169, w - 2, 5))
        # copa: aglomerado de bolas com sombra / cor / luz
        blobs = [(78, 62, 50), (40, 82, 34), (116, 82, 34), (54, 38, 32), (102, 40, 32),
                 (78, 96, 36), (24, 60, 22), (134, 62, 22)]
        for cx, cy, r in blobs:
            pygame.draw.circle(s, OUTLINE, (cx, cy + 1), r + 1)
        for cx, cy, r in blobs:
            pygame.draw.circle(s, (44, 106, 50), (cx + 2, cy + 3), r)
        for cx, cy, r in blobs:
            pygame.draw.circle(s, (66, 146, 62), (cx - 1, cy - 1), r - 4)
        for cx, cy, r in blobs:
            pygame.draw.circle(s, (104, 182, 82), (cx - r // 3, cy - r // 3), r // 3)
        rng = random.Random(7)  # pontinhos de folha
        for _ in range(140):
            x, y = rng.randrange(W), rng.randrange(120)
            if s.get_at((x, y))[3] and s.get_at((x, y))[:3] != OUTLINE:
                s.set_at((x, y), (52, 124, 54) if rng.random() < 0.6 else (124, 196, 96))
        return [_up(s)]

    def draw_ground(self, surface):
        surface.blit(self.shade_surf, self.shade_surf.get_rect(center=self.shade_center))

    def draw(self, surface, viewer=None):
        img = self.image()
        rect = img.get_rect(midbottom=(round(self.x), round(self.y)))
        # Personagem atrás da copa: deixa a árvore meio transparente
        if viewer is not None and viewer.y < self.y and rect.collidepoint(viewer.x, viewer.y - 40):
            img = img.copy()
            img.set_alpha(150)
        surface.blit(img, rect)

    def shade_at(self, x, y):
        rx, ry = self.shade_r
        dx, dy = (x - self.shade_center[0]) / (rx * 0.85), (y - self.shade_center[1]) / (ry * 0.85)
        return self.SHADE_LIGHT if dx * dx + dy * dy <= 1 else 1.0


class Campfire(Prop):
    """Fogueira interativa (arte em world/campfire/, recortada por tools/make_campfire.py).

    Estados:
      - Acesa (`lit = True`): passa por `kindling` ao acender e anima `fire_0..4` em loop,
        soltando fagulhas (`spark_0..3`), línguas de fogo (`flame`) e fumaça (`smoke_0..2`),
        além de iluminar o redor com brilho quente difuso que oscila como fogo real.
      - Apagada (`lit = False`): ao apagar passa por `fire_4` soltando bastante fumaça e fica
        em `extinguished` (lenha queimada); no Natal, depois de um tempo apagada, acumula neve
        (`unlit_snow`)."""
    kind = "campfire"
    footprint = (52, 16)
    frame_duration = 0.11
    IGNITE_TIME = 0.55
    DOUSE_TIME = 0.45
    SNOW_SETTLE = 45.0
    _glow_cache = {}

    def __init__(self, x, y, defn):
        super().__init__(x, y, defn)
        from .config import SPRITES_DIR
        folder = SPRITES_DIR / "world" / "campfire"

        def ld(name, k=1.0):
            f = folder / f"{name}.png"
            if not f.exists():
                return None
            return pygame.transform.smoothscale_by(pygame.image.load(str(f)).convert_alpha(), self.scale * k)

        self.unlit_snow = ld("unlit_snow")
        self.extinguished = ld("extinguished")
        self.kindling = ld("kindling")
        self.fire_frames = [img for img in (ld(f"fire_{i}") for i in range(5)) if img]
        self.flame_img = ld("flame", 0.5)
        self.smokes = [img for img in (ld(f"smoke_{i}", 0.65) for i in range(3)) if img]
        self.spark_imgs = [img for img in (ld(f"spark_{i}", 0.6) for i in range(4)) if img]
        if self.fire_frames:
            self.frames = self.fire_frames
            self.has_art = True
        img = self.frames[0]
        if "footprint" not in defn:
            self.defn = dict(self.defn, footprint=(max(16, round(img.get_width() * 0.44)), 14))
        self.lit = bool(defn.get("lit", True))
        self.has_snow = not self.lit
        self.snow_timer = self.SNOW_SETTLE
        self.light_level = 1.0 if self.lit else 0.0
        self.trans_mode = None      # "ignite" | "douse" | None
        self.trans_t = 0.0
        self.after_smoke = 0.0      # segundos soltando fumaça logo após apagar
        self.sparks = []            # [x, y, vx, vy, vida, max_vida, img_ou_None]
        self.flames = []            # [x, y, vy, vida, max_vida]
        self.smoke_puffs = []       # [img, x, y, vx, vy, vida, max_vida]
        self.rng = random.Random(int(x * 13 + y * 7) ^ 3)
        self.claimed = None

    def placeholder_frames(self):
        frames = []
        for f in range(6):
            rng = random.Random(f * 31 + 5)
            s = _canvas(42, 44)
            for i in range(9):
                a = math.pi * (0.05 + i / 8 * 0.9)
                px, py = 21 - math.cos(a) * 17, 38 + math.sin(a) * 3 - 2
                pygame.draw.circle(s, OUTLINE, (px, py), 4)
                pygame.draw.circle(s, (132, 128, 124), (px, py - 0.5), 3)
            pygame.draw.line(s, OUTLINE, (7, 39), (35, 31), 6)
            pygame.draw.line(s, OUTLINE, (7, 31), (35, 39), 6)
            pygame.draw.line(s, (122, 76, 40), (8, 38), (34, 31), 4)
            pygame.draw.line(s, (100, 62, 34), (8, 32), (34, 38), 4)
            for color, hmin, hmax, wid in (((226, 74, 32), 22, 30, 9),
                                           ((255, 148, 40), 15, 21, 7),
                                           ((255, 232, 128), 8, 12, 4)):
                for ox in (-5, 0, 5):
                    h = rng.randint(hmin, hmax) - abs(ox)
                    w = wid - abs(ox) // 3
                    bx, by = 21 + ox + rng.randint(-1, 1), 34
                    tip = bx + rng.randint(-3, 3)
                    pygame.draw.polygon(s, color, [(bx - w, by), (bx - w * 0.6, by - h * 0.5),
                                                   (tip, by - h), (bx + w * 0.6, by - h * 0.5),
                                                   (bx + w, by)])
            frames.append(_up(s))
        return frames

    def _spawn_spark(self, burst=False):
        w = self.frames[0].get_width()
        sx = self.x + self.rng.uniform(-0.18, 0.18) * w
        sy = self.y - self.rng.uniform(14, 38) * self.scale
        vx = self.rng.uniform(-28, 28) if burst else self.rng.uniform(-12, 12)
        vy = -self.rng.uniform(55, 115) if burst else -self.rng.uniform(38, 82)
        life = self.rng.uniform(0.55, 1.15)
        sp_img = self.rng.choice(self.spark_imgs) if (self.spark_imgs and self.rng.random() < 0.55) else None
        self.sparks.append([sx, sy, vx, vy, life, life, sp_img])

    def _spawn_smoke(self, high=False):
        if not self.smokes:
            return
        w, h = self.frames[0].get_size()
        sm_img = self.rng.choice(self.smokes)
        sx = self.x + self.rng.uniform(-0.12, 0.12) * w
        sy = self.y - (h * (0.52 if high else 0.28))
        vx = self.rng.uniform(-10, 14)
        vy = -self.rng.uniform(22, 42)
        life = self.rng.uniform(0.9, 1.6)
        self.smoke_puffs.append([sm_img, sx, sy, vx, vy, life, life])

    def light_up(self):
        """Acende a fogueira com transição `kindling` e explosão suave de fagulhas."""
        if self.lit:
            return
        self.lit = True
        self.has_snow = False
        self.trans_mode = "ignite"
        self.trans_t = 0.0
        self.after_smoke = 0.0
        for _ in range(10):
            self._spawn_spark(burst=True)
        for _ in range(2):
            self._spawn_smoke(high=False)
        if self.flame_img:
            self.flames.append([self.x, self.y - 22 * self.scale, -48 * self.scale, 0.45, 0.45])

    def extinguish(self):
        """Apaga a fogueira passando por `fire_4` e soltando fumaça da brasa."""
        if not self.lit:
            return
        self.lit = False
        self.has_snow = False
        self.snow_timer = self.SNOW_SETTLE
        self.trans_mode = "douse"
        self.trans_t = 0.0
        self.after_smoke = 3.2
        for _ in range(5):
            self._spawn_smoke(high=False)

    def toggle(self):
        if self.lit:
            self.extinguish()
        else:
            self.light_up()

    def image(self) -> pygame.Surface:
        if self.trans_mode == "ignite" and self.kindling:
            return self.kindling
        if self.trans_mode == "douse" and len(self.fire_frames) >= 5:
            return self.fire_frames[4]
        if not self.lit:
            if self.has_snow and self.unlit_snow:
                return self.unlit_snow
            return self.extinguished or self.unlit_snow or self.frames[0]
        # Quando acesa, alterna entre as poses de fogo vivo (fire_0..3, e ocasionalmente fire_4)
        cycle = self.fire_frames[:4] if len(self.fire_frames) >= 4 else self.frames
        return cycle[int(self.time / self.frame_duration) % len(cycle)]

    def shadow_image(self) -> pygame.Surface:
        return self.extinguished or self.unlit_snow or self.frames[0]

    def update(self, dt):
        super().update(dt)
        if self.trans_mode == "ignite":
            self.trans_t += dt
            if self.trans_t >= self.IGNITE_TIME:
                self.trans_mode = None
        elif self.trans_mode == "douse":
            self.trans_t += dt
            if self.trans_t >= self.DOUSE_TIME:
                self.trans_mode = None

        target_light = 1.0 if self.lit else 0.0
        if self.trans_mode == "ignite":
            target_light = 0.45 + 0.55 * (self.trans_t / self.IGNITE_TIME)
        elif self.trans_mode == "douse":
            target_light = 0.35 * max(0.0, 1.0 - self.trans_t / self.DOUSE_TIME)
        speed = 3.2 if target_light > self.light_level else 2.6
        if self.light_level < target_light:
            self.light_level = min(target_light, self.light_level + speed * dt)
        elif self.light_level > target_light:
            self.light_level = max(target_light, self.light_level - speed * dt)

        if not self.lit:
            if self.after_smoke > 0:
                self.after_smoke = max(0.0, self.after_smoke - dt)
                if self.rng.random() < dt * 3.5:
                    self._spawn_smoke(high=False)
            elif getattr(getattr(self, "world", None), "season", "") == "natal" and not self.has_snow:
                self.snow_timer -= dt
                if self.snow_timer <= 0:
                    self.has_snow = True
        else:
            if self.rng.random() < dt * 11:
                self._spawn_spark(burst=False)
            if self.flame_img and self.rng.random() < dt * 2.2:
                w = self.frames[0].get_width()
                life = self.rng.uniform(0.35, 0.6)
                self.flames.append([
                    self.x + self.rng.uniform(-0.1, 0.1) * w,
                    self.y - 26 * self.scale,
                    -self.rng.uniform(35, 60) * max(0.7, self.scale),
                    life,
                    life,
                ])
            if self.rng.random() < dt * 1.6:
                self._spawn_smoke(high=True)

        for sp in self.sparks:
            sp[0] += (sp[2] + math.sin(self.time * 6 + sp[1]) * 14) * dt
            sp[1] += sp[3] * dt
            sp[4] -= dt
        self.sparks = [sp for sp in self.sparks if sp[4] > 0]

        for fl in self.flames:
            fl[1] += fl[2] * dt
            fl[3] -= dt
        self.flames = [fl for fl in self.flames if fl[3] > 0]

        for sm in self.smoke_puffs:
            sm[1] += (sm[3] + math.sin(self.time * 2.5 + sm[2] * 0.05) * 8) * dt
            sm[2] += sm[4] * dt
            sm[5] -= dt
        self.smoke_puffs = [sm for sm in self.smoke_puffs if sm[5] > 0]

    def draw_ground(self, surface):
        rx = max(24, round(self.frames[0].get_width() * 0.46))
        ry = max(8, round(rx * 0.28))
        sh = _soft_ellipse(rx, ry, (20, 20, 15), alpha=26)
        surface.blit(sh, sh.get_rect(center=(round(self.x), round(self.y - 4))))

    def _draw_particles(self, surface, draw_smoke=True):
        if draw_smoke:
            for sm_img, sx, sy, _, _, life, mlife in self.smoke_puffs:
                k = life / max(0.01, mlife)
                im = pygame.transform.smoothscale_by(sm_img, 0.75 + 0.45 * (1 - k))
                im.set_alpha(round(175 * math.sin(k * math.pi)))
                surface.blit(im, im.get_rect(center=(round(sx), round(sy))))
        if self.flame_img:
            for fx, fy, _, life, mlife in self.flames:
                k = life / max(0.01, mlife)
                im = pygame.transform.smoothscale_by(self.flame_img, max(0.25, 0.55 + 0.45 * k))
                im.set_alpha(round(240 * min(1.0, k * 1.4)))
                surface.blit(im, im.get_rect(midbottom=(round(fx), round(fy))))
        for sx, sy, _, _, life, mlife, sp_img in self.sparks:
            k = life / max(0.01, mlife)
            if sp_img is not None:
                im = sp_img.copy()
                im.set_alpha(round(255 * min(1.0, k * 1.5)))
                surface.blit(im, im.get_rect(center=(round(sx), round(sy))))
            else:
                c = (255, 215, 105) if k > 0.45 else (235, 115, 40)
                surface.fill(c, (round(sx), round(sy), P, P))

    def draw(self, surface, viewer=None):
        super().draw(surface, viewer)
        self._draw_particles(surface, draw_smoke=True)

    def draw_light(self, surface, darkness=0.0):
        if self.light_level <= 0.02:
            return
        from .lighting import _glow
        flick = 0.90 + 0.10 * (0.6 * math.sin(self.time * 8.5) + 0.4 * math.sin(self.time * 14.3))
        strength = self.light_level * (0.35 + 0.65 * max(0.15, darkness)) * flick
        level = max(1, min(16, round(strength * 16)))
        r = max(55, round(135 * max(0.65, self.scale)))
        key = (r, level)
        if key not in Campfire._glow_cache:
            v = round(255 * level / 16)
            halo = _glow(r, (160, 88, 32), softness=3.0)
            core = _glow(max(10, r // 4), (210, 145, 75), softness=3.4)
            halo.blit(core, core.get_rect(center=halo.get_rect().center), special_flags=pygame.BLEND_ADD)
            pool = pygame.transform.smoothscale(
                _glow(r, (95, 58, 24), softness=2.5),
                (round(r * 2.3), round(r * 0.85)),
            )
            for g in (halo, pool):
                g.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
            Campfire._glow_cache[key] = (halo, pool)
        halo, pool = Campfire._glow_cache[key]
        surface.blit(pool, pool.get_rect(center=(round(self.x), round(self.y - 2))), special_flags=pygame.BLEND_ADD)
        surface.blit(
            halo,
            halo.get_rect(center=(round(self.x), round(self.y - 28 * self.scale))),
            special_flags=pygame.BLEND_ADD,
        )
        if darkness > 0.05:
            # Redesenha as chamas e fagulhas por cima do escurecimento da noite
            img = self.image().copy()
            img.set_alpha(round(255 * min(1.0, darkness * 1.25 * self.light_level)))
            surface.blit(img, img.get_rect(midbottom=(round(self.x), round(self.y + self.base_offset))))
            self._draw_particles(surface, draw_smoke=False)


class Dummy(Prop):
    """Boneco de treino: balança quando leva um golpe (mola amortecida)."""
    kind = "dummy"
    footprint = (26, 12)

    def __init__(self, x, y, defn):
        super().__init__(x, y, defn)
        self.angle = 0.0   # graus (positivo = anti-horário)
        self.spin = 0.0
        self.flash = 0.0
        # canvas 2x mais alto: a base do desenho fica no CENTRO, que é o pivô da rotação
        img = self.frames[0]
        self.pivot_img = pygame.Surface((img.get_width(), img.get_height() * 2), pygame.SRCALPHA)
        self.pivot_img.blit(img, (0, 0))

    def placeholder_frames(self):
        s = _canvas(34, 62)
        s.fill(OUTLINE, (14, 20, 6, 42))          # poste
        s.fill((118, 80, 46), (15, 20, 4, 42))
        s.fill(OUTLINE, (3, 25, 28, 6))           # braço
        s.fill((132, 90, 52), (4, 26, 26, 4))
        pygame.draw.ellipse(s, OUTLINE, (7, 13, 20, 33))      # saco de palha
        pygame.draw.ellipse(s, (216, 182, 98), (8, 14, 18, 31))
        pygame.draw.ellipse(s, (236, 206, 126), (10, 16, 7, 12))
        for y in (23, 36):                         # cordas
            s.fill((140, 98, 54), (9, y, 16, 2))
        pygame.draw.circle(s, OUTLINE, (17, 9), 8)  # cabeça
        pygame.draw.circle(s, (200, 164, 96), (17, 9), 7)
        for ex in (14, 20):                        # olhos em X
            s.set_at((ex - 1, 7), OUTLINE); s.set_at((ex + 1, 9), OUTLINE)
            s.set_at((ex, 8), OUTLINE)
            s.set_at((ex + 1, 7), OUTLINE); s.set_at((ex - 1, 9), OUTLINE)
        s.fill((96, 64, 36), (11, 58, 12, 4))     # estaca
        return [_up(s)]

    def hit(self, from_side: str):
        """Golpe vindo de quem olha para `from_side` ('right' empurra para a direita)."""
        self.spin += -260 if from_side == "right" else 260
        self.flash = 0.12

    def update(self, dt):
        super().update(dt)
        acc = -70 * self.angle - 5 * self.spin
        self.spin += acc * dt
        self.angle += self.spin * dt
        self.angle = max(-35, min(35, self.angle))
        self.flash = max(0.0, self.flash - dt)

    def draw_ground(self, surface):
        sh = _soft_ellipse(22, 7, (20, 30, 20), alpha=30)
        surface.blit(sh, sh.get_rect(center=(round(self.x), round(self.y - 2))))

    def draw(self, surface, viewer=None):
        img = pygame.transform.rotate(self.pivot_img, self.angle) if abs(self.angle) > 0.5 else self.pivot_img
        if self.flash:
            img = img.copy()
            img.fill((110, 110, 110), special_flags=pygame.BLEND_RGB_ADD)
        surface.blit(img, img.get_rect(center=(round(self.x), round(self.y))))


class Bench(Prop):
    """Banco para sentar. Arte: "file" em scene.py (ex.: items/town_bench_lit.png).

    `seats`: posições dos assentos (dx em px de TELA a partir da base).
    Quem senta fica com os pés na base do banco, um pouco À FRENTE (y maior,
    para ser desenhado na frente dele), levantado `seat_height` px."""
    kind = "bench"
    footprint = (120, 12)

    def __init__(self, x, y, defn):
        super().__init__(x, y, defn)
        img = self.frames[0]
        # "seats_rel"/"approach_rel": frações da largura/altura da arte (acompanham o tamanho)
        if "seats_rel" in defn:
            self.seats = [f * img.get_width() for f in defn["seats_rel"]]
        else:
            self.seats = defn.get("seats", [-32, 32])
        self.occupied = {}  # índice do assento -> personagem
        self.seat_height = defn.get("seat_height", 0.42) * img.get_height()
        if "approach_rel" in defn:
            self.defn = dict(self.defn, approach_dy=round(defn["approach_rel"] * img.get_height()))
        if "footprint" not in defn:
            self.defn = dict(self.defn, footprint=(round(img.get_width() * 0.85), 12))

    def free_seat(self, who=None):
        for i, _ in enumerate(self.seats):
            if self.occupied.get(i) in (None, who):
                return i
        return None

    def seat_pos(self, i):
        return self.x + self.seats[i], self.y + 3

    def approach(self, i):
        """Onde parar antes de sentar (na frente do assento, fora da área sólida)."""
        return self.x + self.seats[i], self.y + self.defn.get("approach_dy", 34)


PLANT_NAMES = ("arbusto", "capim", "planta", "folhas")   # itens da biblioteca que balançam


class Breeze:
    """Balanço leve e contínuo de uma imagem (planta/árvore): base parada, topo indo e
    vindo 1-3 px com a brisa (mais com chuva). Poses em cache por `key`."""
    POSES = 13
    _cache = {}

    def __init__(self, img, key):
        from .decor import soft_sway_poses
        key = key + (img.get_size(),)
        if key not in Breeze._cache:
            amp = max(1.0, min(3.0, img.get_height() * 0.016))
            Breeze._cache[key] = soft_sway_poses(img, amp, self.POSES)[0]
        self.poses = Breeze._cache[key]
        self.phase = random.uniform(0, 6.3)
        self.freq = random.uniform(0.14, 0.26)

    def image(self, t, world=None):
        from .decor import breeze
        v = breeze(t, self.phase, self.freq, getattr(world, "wind", 1.0))
        return self.poses[round((v + 1) / 2 * (self.POSES - 1))]


class Item(Prop):
    """Objeto da biblioteca (assets/sprites/world/library/<conjunto>/<nome>.png), colocado
    pelo editor (tecla O, depois L). "solid": se bloqueia a passagem (padrão sim): a área
    sólida é uma faixa na base, com metade da largura da arte."""
    kind = "item"
    _lights_db = {}              # pasta -> conteúdo do lights.json (cache)
    _glows = {}                  # (raio) -> imagens de brilho (cache)

    def __init__(self, x, y, defn):
        super().__init__(x, y, defn)
        if "footprint" not in defn:
            w = self.frames[0].get_width()
            fp = (max(8, round(w * 0.5)), 10) if defn.get("solid", True) else (0, 0)
            self.defn = dict(self.defn, footprint=fp)
        # lanternas: lights.json na pasta do item (px da imagem original) -> px de tela
        self.lamps = []
        f = defn.get("file")
        if f:
            from .config import SPRITES_DIR
            path = SPRITES_DIR / f
            db = Item._lights_db.get(path.parent)
            if db is None:
                import json
                jf = path.parent / "lights.json"
                db = json.loads(jf.read_text(encoding="utf-8")) if jf.exists() else {}
                Item._lights_db[path.parent] = db
            pts = db.get(path.stem, [])
            bulbs = db.get("bulbs", {}).get(path.stem, [])
            if pts or bulbs:
                orig = pygame.image.load(str(path))
                img = self.frames[0]
                k = img.get_width() / orig.get_width()
                left = self.x - img.get_width() / 2
                top = self.y + self.base_offset - img.get_height()
                self.lamps = [(left + lx * k, top + ly * k) for lx, ly in pts]
                self.bulbs = [(left + bx * k, top + by * k, random.uniform(0, 6.3), random.uniform(1.2, 2.6))
                              for bx, by in bulbs]
                self.lamp_k = k
        self.bulbs = getattr(self, "bulbs", [])
        self.phase = random.uniform(0, 6.3)
        # plantas (arbusto, capim, folhas...) balançam bem de leve com a brisa
        name = defn.get("name") or (str(f).rsplit("/", 1)[-1].rsplit(".", 1)[0] if f else "")
        self.breeze = None
        if name.startswith(PLANT_NAMES) and not self.lamps and not self.bulbs:
            self.breeze = Breeze(self.frames[0], ("item", f, round(self.scale, 3)))

    def image(self):
        if self.breeze:
            return self.breeze.image(self.time, getattr(self, "world", None))
        return super().image()

    def shadow_image(self):
        return self.frames[0] if self.breeze else super().image()

    def draw_light(self, surface, darkness: float = 0.0):
        """Lanternas acesas: brilho difuso no vidro + uma pocinha de luz no chão.
        Pisca-pisca: lâmpadas coloridas piscando cada uma no seu ritmo."""
        if not self.lamps and not self.bulbs:
            return
        from .lighting import BULB_COLORS, _glow
        night = max(0.0, min(1.0, (darkness - 0.1) / 0.6))
        for n, (bx, by, ph, sp) in enumerate(self.bulbs):
            col = BULB_COLORS[n % len(BULB_COLORS)]
            level = max(0, min(12, round(12 * (0.25 + 0.75 * night) * (0.55 + 0.45 * math.sin(self.time * sp + ph)))))
            if not level:
                continue
            key = ("bulb", col, level)
            if key not in Item._glows:
                v = round(255 * level / 12)
                g = _glow(11, col, softness=3.2)
                core = _glow(3, tuple(min(255, c + 110) for c in col), softness=3.0)
                g.blit(core, core.get_rect(center=g.get_rect().center), special_flags=pygame.BLEND_ADD)
                g.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
                Item._glows[key] = g
            g = Item._glows[key]
            surface.blit(g, g.get_rect(center=(round(bx), round(by))), special_flags=pygame.BLEND_ADD)
        if not self.lamps:
            return
        s = (0.18 + 0.82 * night) * (0.93 + 0.07 * math.sin(self.time * 7 + self.phase))
        if s <= 0.02:
            return
        r = max(10, round(170 * self.lamp_k))           # do tamanho da lanterna, não do poste
        level = max(1, min(16, round(s * 16)))           # força em 16 degraus (cache)
        key = (r, level)
        if key not in Item._glows:
            v = round(255 * level / 16)
            halo = _glow(r, (210, 135, 70), softness=3.0)
            core = _glow(max(3, r // 4), (255, 225, 170), softness=3.5)
            halo.blit(core, core.get_rect(center=halo.get_rect().center), special_flags=pygame.BLEND_ADD)
            pool = pygame.transform.smoothscale(_glow(r, (110, 80, 45), softness=2.4), (round(r * 2.4), round(r * 0.8)))
            for img in (halo, pool):
                img.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
            Item._glows[key] = (halo, pool)
        halo, pool = Item._glows[key]
        for lx, ly in self.lamps:
            for img, center in ((pool, (lx, self.y + 2)), (halo, (lx, ly))):
                surface.blit(img, img.get_rect(center=(round(center[0]), round(center[1]))),
                             special_flags=pygame.BLEND_ADD)


class Cave(Prop):
    """Caverna no fundo da ilha (arte: "file", recortada por tools/make_areas.py).
    É o abrigo: à noite ele dorme lá dentro e foge da chuva para lá.

    `inside`: ponto "lá dentro" (na boca da caverna, logo à frente da base, para
    ser desenhado por cima dela, escurecido). `door`: onde parar na grama antes
    de entrar (o mundo acha o ponto andável mais perto de `door_hint`)."""
    kind = "cave"

    def __init__(self, x, y, defn):
        super().__init__(x, y, defn)
        self.inside = (x, y + 4)
        self.door_hint = (x, y + defn.get("door_dy", 70))
        self.door = None
        self.occupant = None

    def draw_ground(self, surface):
        pass


class Lamp(Prop):
    """Poste com lâmpadas que acendem à noite. "lights": posições das lâmpadas
    (px da arte ORIGINAL, relativos ao ponto da base)."""
    kind = "lamp"
    footprint = (26, 10)

    def __init__(self, x, y, defn):
        super().__init__(x, y, defn)
        self.lights = [(dx * self.scale, dy * self.scale) for dx, dy in defn.get("lights", [])]
        self.glow = radial_glow(round(110 * max(0.6, self.scale)), (170, 150, 110))
        # poça de luz no chão: gradiente radial achatado (luz aditiva não usa alpha)
        pool = radial_glow(120, (95, 85, 55))
        self.pool = pygame.transform.smoothscale(pool, (300, 90))
        self.time = 0.0

    def draw_light(self, surface, darkness=0.0):
        on = max(0.0, (darkness - 0.15) / 0.85)   # acende no fim da tarde
        if on <= 0:
            return
        flick = 0.94 + 0.06 * math.sin(self.time * 9.0)
        for dx, dy in self.lights:
            add_light(surface, self.glow, (round(self.x + dx), round(self.y + dy)), on * flick)
        add_light(surface, self.pool, (round(self.x - 40), round(self.y + 30)), on)


class FruitTree(Prop):
    """Árvore de frutas (arte em world/fruit_tree/, recortada por tools/make_fruit_tree.py).

    É a comida dos personagens: um golpe (`hit`) faz a árvore piscar branca, balançar
    (poses hit_0..3, com neve e folhas voando), soltar folhas e derrubar UMA fruta, que cai
    quicando no chão perto do tronco (`Fruit`, em world.fruits). Sem frutas, fica pelada
    ("empty") e volta a dar frutas depois de REGROW segundos.

    Árvore de IMAGEM ÚNICA (ex.: o pinheiro enfeitado da biblioteca, sem poses desenhadas):
    o balanço é feito pelo código, inclinando a copa com a base parada (decor.sway_poses),
    numa oscilação que vai parando; o resto (piscar branco, folhas, fruta) é igual."""
    kind = "fruit_tree"
    SINGLE_TIME = 0.7            # duração do balanço da árvore de imagem única
    HIT_POSES = ("hit_0", "hit_1", "hit_2", "hit_3")
    POSE_TIME = 0.09
    FLASH = 0.09
    REGROW = (90, 160)

    def __init__(self, x, y, defn):
        super().__init__(x, y, defn)
        from .config import SPRITES_DIR
        folder = SPRITES_DIR / "world" / "fruit_tree"
        self.poses = {}
        name = defn.get("name") or ""
        self.single = not (name.startswith("arvore_frutas") or str(defn.get("file", "")).endswith("arvore_frutas.png")
                           or not defn.get("file"))
        if not self.single:
            for pose in ("full", "empty") + self.HIT_POSES:
                f = folder / f"{pose}.png"
                if f.exists():
                    self.poses[pose] = pygame.transform.smoothscale_by(pygame.image.load(str(f)).convert_alpha(),
                                                                       self.scale)
        else:                                          # imagem única: inclinações pré-calculadas
            from .decor import sway_poses
            img = self.frames[0]
            self.sway, _ = sway_poses(img, amp=max(3.0, img.get_width() * 0.12), n=9)
        self.fruit_imgs = [pygame.transform.smoothscale_by(pygame.image.load(str(f)).convert_alpha(), self.scale * 0.55)
                           for f in sorted(folder.glob("fruit_*.png"))]
        if self.poses:
            self.frames = [self.poses["full"]]
        img = self.frames[0]
        if "footprint" not in defn:                  # só o tronco é sólido
            self.defn = dict(self.defn, footprint=(max(8, round(img.get_width() * 0.22)), 10))
        self.max_fruits = defn.get("fruits", 4)
        self.fruits = self.max_fruits
        self.regrow = 0.0
        self.hit_t = None            # tempo desde o último golpe (None = parada)
        self.shake_side = 1
        self.leaves = []             # [x, y, vx, vy, vida, cor]
        self.world = None            # o World liga (para a fruta cair em lugar andável)

    def shadow_image(self):
        if self.hit_t is not None:
            return self.image()
        if self.single:
            return self.frames[0]
        return self.poses.get("full" if self.fruits > 0 else "empty", self.frames[0])

    def _idle(self, name, img):
        """Pose parada balançando de leve com a brisa (props.Breeze, uma por pose)."""
        b = self._breezes.get(name)
        if b is None:
            b = self._breezes[name] = Breeze(img, ("tree", str(self.defn.get("file")), name, round(self.scale, 3)))
            b.phase, b.freq = self._breeze_phase, self._breeze_freq    # trocar de pose não dá pulo
        return b.image(self.time, self.world)

    def image(self):
        if not hasattr(self, "_breezes"):
            self._breezes = {}
            self._breeze_phase, self._breeze_freq = random.uniform(0, 6.3), random.uniform(0.12, 0.2)
        if self.single:
            if self.hit_t is None:
                return self._idle("single", self.frames[0])
            lean = math.sin(self.hit_t * 26) * math.exp(-self.hit_t * 5) * self.shake_side
            return self.sway[max(0, min(len(self.sway) - 1, round((lean + 1) / 2 * (len(self.sway) - 1))))]
        if self.hit_t is not None:
            i = int(self.hit_t / self.POSE_TIME)
            if i < len(self.HIT_POSES) and self.HIT_POSES[i] in self.poses:
                return self.poses[self.HIT_POSES[i]]
        name = "full" if self.fruits > 0 else "empty"
        return self._idle(name, self.poses.get(name, self.frames[0]))

    def hit(self, from_side: str = "right"):
        """Golpe: balança, solta folhas e derruba uma fruta (se tiver)."""
        if self.hit_t is not None and self.hit_t < 0.25:
            return None
        self.hit_t = 0.0
        self.shake_side = 1 if from_side == "right" else -1
        img = self.frames[0]
        w, h = img.get_width(), img.get_height()
        for _ in range(random.randint(7, 12)):        # folhas e neve voando
            col = random.choice([(70, 95, 70), (95, 120, 85), (120, 80, 60), (235, 240, 250)])
            self.leaves.append([self.x + random.uniform(-0.35, 0.35) * w, self.y - random.uniform(0.45, 0.85) * h,
                                random.uniform(-25, 25) + 30 * self.shake_side, random.uniform(-20, 10),
                                random.uniform(1.2, 2.2), col])
        if self.fruits <= 0 or not self.fruit_imgs:
            return None
        self.fruits -= 1
        if self.fruits == 0:
            self.regrow = random.uniform(*self.REGROW)
        side = random.choice((-1, 1))
        target = (self.x + side * random.uniform(0.18, 0.4) * w, self.y + random.uniform(4, 22) * self.scale * 3)
        if self.world is not None:
            target = self.world.nav_point(target) if self.world.blocked(pygame.Rect(round(target[0]) - 4,
                                                                                     round(target[1]) - 3, 8, 6)) else target
        fruit = Fruit(random.choice(self.fruit_imgs), (self.x + side * 0.15 * w, self.y - 0.55 * h), target)
        if self.world is not None:
            self.world.fruits.append(fruit)
        return fruit

    def update(self, dt):
        super().update(dt)
        if self.hit_t is not None:
            self.hit_t += dt
            end = self.SINGLE_TIME if self.single else self.POSE_TIME * len(self.HIT_POSES) + 0.1
            if self.hit_t > end:
                self.hit_t = None
        if self.fruits == 0:
            self.regrow -= dt
            if self.regrow <= 0:
                self.fruits = self.max_fruits
        for lf in self.leaves:
            lf[0] += (lf[2] + math.sin(self.time * 3 + lf[1]) * 12) * dt
            lf[1] += (lf[3] + 28) * dt                 # caem devagar, balançando
            lf[3] *= 0.98
            lf[4] -= dt
        self.leaves = [lf for lf in self.leaves if lf[4] > 0]

    def draw(self, surface, viewer=None):
        img = self.image()
        x = self.x
        if self.hit_t is not None:                     # tremida que vai parando
            if not self.single:
                x += math.sin(self.hit_t * 55) * 4 * self.scale * max(0.0, 1 - self.hit_t / 0.4) * self.shake_side
            if self.hit_t < self.FLASH:                # pisca branca no golpe
                img = img.copy()
                img.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_MAX)
        surface.blit(img, img.get_rect(midbottom=(round(x), round(self.y + self.base_offset))))
        for lx, ly, _, _, life, col in self.leaves:
            size = 2 if life > 0.6 else 1
            pygame.draw.rect(surface, col, (round(lx), round(ly), size + 1, size))


class Fruit:
    """Fruta que caiu da árvore: cai quicando até o chão e fica lá até alguém pegar."""

    def __init__(self, img, start, target):
        self.img = img
        self.x, self.y = target                      # onde fica no chão (ordenação por y)
        self.sx = start[0]
        self.z = max(10.0, target[1] - start[1])     # altura acima do chão
        self.vz = 0.0
        self.vx = (target[0] - start[0]) / 0.55
        self.fx = start[0]
        self.landed = False
        self.claimed = None                          # quem vai pegar
        self.bounces = 0
        self.age = 0.0
        self.eaten = False

    def update(self, dt):
        self.age += dt
        if self.landed:
            return
        self.vz -= 520 * dt
        self.z += self.vz * dt
        if abs(self.fx - self.x) > 1:
            self.fx += self.vx * dt
            if (self.vx > 0 and self.fx > self.x) or (self.vx < 0 and self.fx < self.x):
                self.fx = self.x
        if self.z <= 0:
            self.z = 0
            if self.bounces < 2 and abs(self.vz) > 60:
                self.vz = -self.vz * 0.35            # quica
                self.bounces += 1
            else:
                self.vz = 0
                self.fx = self.x
                self.landed = True

    SHINE_EVERY = 1.6        # segundos entre um reflexo e outro
    SHINE_TIME = 0.45        # quanto o reflexo leva para atravessar a fruta

    def draw(self, surface, viewer=None):
        w, h = self.img.get_size()
        sh = pygame.Surface((max(4, w), max(2, w // 3)), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 60), sh.get_rect())
        surface.blit(sh, sh.get_rect(center=(round(self.fx), round(self.y))))
        rect = self.img.get_rect(midbottom=(round(self.fx), round(self.y - self.z)))
        if self.landed and not self.claimed:          # item no chão: brilho suave pulsando em volta
            if not hasattr(Fruit, "_halo"):
                halo = pygame.Surface((64, 64), pygame.SRCALPHA)
                for r in range(32, 0, -1):
                    pygame.draw.circle(halo, (255, 245, 200, round(70 * (1 - r / 32) ** 2)), (32, 32), r)
                Fruit._halo = halo
            size = round(max(w, h) * (2.0 + 0.25 * math.sin(self.age * 4)))
            halo = pygame.transform.smoothscale(Fruit._halo, (size, size))
            surface.blit(halo, halo.get_rect(center=rect.center))
        surface.blit(self.img, rect)
        if not self.landed or self.claimed:
            return
        # reflexo branco atravessando a fruta na diagonal (recortado pelo formato dela)
        t = (self.age % self.SHINE_EVERY) / self.SHINE_TIME
        if t < 1:
            if not hasattr(self, "_mask"):
                self._mask = self.img.copy()
                self._mask.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_MAX)   # branco, mesmo alpha
            band = pygame.Surface((w, h), pygame.SRCALPHA)
            x = -h + (w + 2 * h) * t
            for i, a in ((0, 230), (1, 160), (-1, 160), (2, 70), (-2, 70)):
                pygame.draw.line(band, (255, 255, 255, a), (x + i * 2, h), (x + i * 2 + h, 0), 2)
            band.blit(self._mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(band, rect)
        # estrelinha que pisca no canto quando o reflexo passa
        s = max(0.0, 1 - abs(t - 0.6) * 3) if t < 1.2 else 0.0
        if s > 0.05:
            cx, cy = rect.right - w * 0.15, rect.top + h * 0.2
            r = 2 + 5 * s
            col = (255, 255, 240)
            pygame.draw.line(surface, col, (cx - r, cy), (cx + r, cy), 1)
            pygame.draw.line(surface, col, (cx, cy - r), (cx, cy + r), 1)
            pygame.draw.circle(surface, col, (round(cx), round(cy)), 1)




class ZoteDummy(Prop):
    """Boneco de treino (o Zote; arte em world/zote/, recortada por tools/make_zote.py).

    Cada golpe (`hit`): pisca branco, toca hit_0..4 (inclina, estoura, volta, poeira,
    endireita), solta lascas/madeira/neve voando com gravidade, faísca no impacto e às vezes
    um balão de emoção. Tem MAX_HP de vida e vai se estragando: pano rasgado ("damaged") e
    depois base quebrada ("nobase"). Na vida zero QUEBRA: a cabeça voa e fica no chão, o
    corpo sem cabeça tomba e some, sobra só a base. Depois de RESPAWN s, uma nuvem de
    fumaça e ele volta inteiro (resmungando)."""
    kind = "zote"
    MAX_HP = 10
    RESPAWN = 10.0
    IDLE_TIME = 0.2
    HIT_TIME = 0.07
    FLASH = 0.08

    def __init__(self, x, y, defn):
        super().__init__(x, y, defn)
        from .config import SPRITES_DIR
        folder = SPRITES_DIR / "world" / "zote"

        def ld(name, k=1.0):
            f = folder / f"{name}.png"
            if not f.exists():
                return None
            return pygame.transform.smoothscale_by(pygame.image.load(str(f)).convert_alpha(), self.scale * k)

        self.idle = [img for img in (ld(f"idle_{i}") for i in range(4)) if img]
        self.hits = [img for img in (ld(f"hit_{i}") for i in range(5)) if img]
        self.pose = {n: ld(n) for n in ("damaged", "nobase", "headless")}
        self.head_img, self.base_img, self.smoke = ld("head"), ld("base"), ld("smoke", 0.9)
        self.pieces = [img for img in (ld(n, 0.6) for n in
                                       ("piece_0", "piece_1", "piece_2", "piece_3", "piece_4", "piece_5",
                                        "snow_0", "snow_1")) if img]
        self.sparks = [img for img in (ld("spark_0", 0.8), ld("spark_1", 0.8)) if img]
        self.emotes = [img for img in (ld(f"emote_{i}", 0.7) for i in range(3)) if img]
        if self.idle:
            self.frames = [self.idle[0]]
        img = self.frames[0]
        if "footprint" not in defn:                    # só o poste é sólido
            self.defn = dict(self.defn, footprint=(max(8, round(img.get_width() * 0.16)), 10))
        self.hp = self.MAX_HP
        self.hit_t = None
        self.side = 1
        self.broken = 0.0            # > 0: quebrado, segundos até voltar
        self.parts = []              # [img, x, y, vx, vy, ang, va, vida, chão]
        self.spark = None            # [img, x, y, vida]
        self.emote = None            # [img, vida]
        self.head = None             # [x, y, vx, vy, ang, va, no_chão]
        self.body = None             # [ângulo, vida]
        self.puffs = []              # [x, y, vida, escala]

    # ---------- estado ----------
    def image(self):
        if self.broken > 0:
            return self.base_img or self.frames[0]
        if self.hit_t is not None and self.hits:
            i = int(self.hit_t / self.HIT_TIME)
            if i < len(self.hits):
                return self.hits[i]
        if self.hp <= 3 and self.pose.get("nobase"):
            return self.pose["nobase"]
        if self.hp <= 6 and self.pose.get("damaged"):
            return self.pose["damaged"]
        return self.idle[int(self.time / self.IDLE_TIME) % len(self.idle)] if self.idle else self.frames[0]

    @property
    def destroyed(self):
        return self.broken > 0

    def _top(self):
        img = self.frames[0]
        return self.y + self.base_offset - img.get_height()

    def hit(self, from_side: str = "right"):
        """Golpe vindo de quem olha para `from_side`."""
        if self.broken > 0:
            return
        if self.hit_t is not None and self.hit_t < 0.12:
            return
        self.side = 1 if from_side == "right" else -1
        self.hit_t = 0.0
        self.hp -= 1
        img = self.frames[0]
        w, h = img.get_size()
        cy = self._top() + h * 0.35
        for _ in range(random.randint(5, 9)):          # lascas voando para longe do golpe
            pc = random.choice(self.pieces) if self.pieces else None
            if pc is None:
                break
            self.parts.append([pc, self.x + random.uniform(-0.15, 0.15) * w, cy + random.uniform(-0.15, 0.25) * h,
                               self.side * random.uniform(40, 130), -random.uniform(60, 170),
                               random.uniform(0, 360), random.uniform(-500, 500), random.uniform(0.8, 1.4),
                               self.y + random.uniform(-4, 12)])
        if self.sparks:
            self.spark = [random.choice(self.sparks), self.x - self.side * w * 0.12, cy, 0.18]
        if self.emotes and random.random() < 0.3 and not self.emote:
            self.emote = [random.choice(self.emotes), 1.3]
        if self.hp <= 0:
            self._break()

    def _break(self):
        """Quebrou: cabeça voa, corpo tomba, sobra a base; volta em RESPAWN s."""
        self.broken = self.RESPAWN
        self.hit_t = None
        img = self.frames[0]
        h = img.get_height()
        self.head = [self.x, self._top() + h * 0.15, self.side * random.uniform(60, 110), -random.uniform(150, 210),
                     0.0, self.side * random.uniform(300, 500), False]
        self.body = [0.0, 1.4]
        for _ in range(4):
            self.puffs.append([self.x + random.uniform(-20, 20) * self.scale, self.y - random.uniform(5, 30) * self.scale,
                               0.9, random.uniform(0.7, 1.2)])
        if self.emotes:
            self.emote = [self.emotes[0], 1.5]

    def update(self, dt):
        super().update(dt)
        if self.hit_t is not None:
            self.hit_t += dt
            if self.hit_t > self.HIT_TIME * len(self.hits) + 0.05:
                self.hit_t = None
        if self.broken > 0:
            before = self.broken
            self.broken -= dt
            if before > 0.6 >= self.broken:            # fumaça de "reconstrução"
                for _ in range(5):
                    self.puffs.append([self.x + random.uniform(-25, 25) * self.scale,
                                       self.y - random.uniform(10, 60) * self.scale, 1.0, random.uniform(0.8, 1.4)])
            if self.broken <= 0:                       # volta inteiro, resmungando
                self.broken = 0.0
                self.hp = self.MAX_HP
                self.head = self.body = None
                if len(self.emotes) > 2:
                    self.emote = [self.emotes[2], 1.6]
        for pt in self.parts:                           # lascas com gravidade, quicam no chão
            pt[1] += pt[3] * dt
            pt[2] += pt[4] * dt
            pt[4] += 420 * dt
            pt[5] += pt[6] * dt
            pt[7] -= dt
            if pt[2] > pt[8]:
                pt[2], pt[4], pt[3], pt[6] = pt[8], -pt[4] * 0.3, pt[3] * 0.6, pt[6] * 0.5
        self.parts = [pt for pt in self.parts if pt[7] > 0]
        if self.spark:
            self.spark[3] -= dt
            if self.spark[3] <= 0:
                self.spark = None
        if self.emote:
            self.emote[1] -= dt
            if self.emote[1] <= 0:
                self.emote = None
        if self.head and not self.head[6]:              # cabeça voando
            hd = self.head
            hd[0] += hd[2] * dt
            hd[1] += hd[3] * dt
            hd[3] += 520 * dt
            hd[4] += hd[5] * dt
            if hd[1] >= self.y + 6:
                hd[1], hd[6] = self.y + 6, True
                hd[4] = 90 * (1 if hd[5] > 0 else -1)   # cai de lado
        if self.body:
            self.body[0] = min(85.0, self.body[0] + 260 * dt)
            self.body[1] -= dt
            if self.body[1] <= 0:
                self.body = None
        for pf in self.puffs:
            pf[1] -= 14 * dt
            pf[2] -= dt
        self.puffs = [pf for pf in self.puffs if pf[2] > 0]

    # ---------- desenho ----------
    def draw(self, surface, viewer=None):
        img = self.image()
        x = self.x
        if self.hit_t is not None and self.hit_t < self.FLASH:      # pisca branco
            img = img.copy()
            img.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_MAX)
        base_y = round(self.y + self.base_offset)
        surface.blit(img, img.get_rect(midbottom=(round(x), base_y)))
        if self.body and self.pose.get("headless"):                 # corpo tombando e sumindo
            b = pygame.transform.rotate(self.pose["headless"], -self.side * self.body[0])
            b.set_alpha(round(255 * min(1.0, self.body[1] / 0.6)))
            surface.blit(b, b.get_rect(midbottom=(round(x + self.side * self.body[0] * 0.25 * self.scale), base_y)))
        if self.head and self.head_img:                              # cabeça (voando / no chão)
            hd = self.head
            hi = pygame.transform.rotate(self.head_img, -hd[4])
            if self.broken < 0.6:
                hi.set_alpha(round(255 * max(0.0, self.broken / 0.6)))
            surface.blit(hi, hi.get_rect(midbottom=(round(hd[0]), round(hd[1]))))
        for pc, px, py, _, _, ang, _, life, _ in self.parts:
            im = pygame.transform.rotate(pc, ang)
            if life < 0.4:
                im.set_alpha(round(255 * life / 0.4))
            surface.blit(im, im.get_rect(center=(round(px), round(py))))
        if self.spark:
            sp, sx, sy, life = self.spark
            im = pygame.transform.flip(sp, self.side < 0, False)
            im.set_alpha(round(255 * min(1.0, life / 0.1)))
            surface.blit(im, im.get_rect(center=(round(sx), round(sy))))
        if self.smoke:
            for px, py, life, sc in self.puffs:
                im = pygame.transform.smoothscale_by(self.smoke, sc * (1.6 - 0.6 * life))
                im.set_alpha(round(220 * min(1.0, life)))
                surface.blit(im, im.get_rect(center=(round(px), round(py))))
        if self.emote:
            em, life = self.emote
            im = em.copy()
            im.set_alpha(round(255 * min(1.0, life / 0.3)))
            top = self._top()
            surface.blit(im, im.get_rect(midbottom=(round(x + 14 * self.scale), round(top + 6 * self.scale))))


class Snowman(Prop):
    """Boneco de neve interativo (Knight ou Hornet; arte em world/snowman_<variante>/,
    recortada por tools/make_snowmen.py).

    Estados (`stage`):
      4 = montado completo (`idle_0..2`, cachecol/manto ao vento; com meia vida mostra `hit_0` rachado)
      0 = destruído (`destroyed`, pilha de neve com cachecol/manto e arma enterrados)
      1..3 = etapas de montagem (`build_0`, `build_1`, `build_2`)

    - Bater (`hit`): pisca branco, sacode, solta bolas de neve/flocos/galhos (`piece_*`) e
      racha (`hit_0`) até desmontar (`hit_1` -> `destroyed`).
    - Montar (`build_step`): avança uma etapa (`destroyed` -> `build_0` -> `build_1` ->
      `build_2` -> `idle_0..2`) soltando neve a cada etapa até ficar pronto de novo."""
    kind = "snowman"
    MAX_HP = 4
    IDLE_TIME = 0.26
    COLLAPSE_TIME = 0.24
    BUILD_BOUNCE = 0.22
    FLASH = 0.08

    def __init__(self, x, y, defn):
        super().__init__(x, y, defn)
        from .config import SPRITES_DIR
        tag = f"{defn.get('variant', '')} {defn.get('name', '')} {defn.get('file', '')}".lower()
        self.variant = "hornet" if "hornet" in tag else "knight"
        folder = SPRITES_DIR / "world" / f"snowman_{self.variant}"

        def ld(name, k=1.0):
            f = folder / f"{name}.png"
            if not f.exists():
                return None
            return pygame.transform.smoothscale_by(pygame.image.load(str(f)).convert_alpha(), self.scale * k)

        self.builds = [img for img in (ld(f"build_{i}") for i in range(3)) if img]
        self.idle = [img for img in (ld(f"idle_{i}") for i in range(3)) if img]
        self.hits = [img for img in (ld(f"hit_{i}") for i in range(2)) if img]
        self.destroyed_img = ld("destroyed")
        self.pieces = [img for img in (ld(f"piece_{i}", 0.55) for i in range(8)) if img]
        if self.idle:
            self.frames = [self.idle[0]]
        img = self.frames[0]
        if "footprint" not in defn:
            self.defn = dict(self.defn, footprint=(max(8, round(img.get_width() * 0.22)), 10))
        self.stage = int(defn.get("stage", 4))   # 0=destruído, 1..3=montando, 4=completo
        self.hp = self.MAX_HP if self.stage >= 4 else 0
        self.hit_t = None
        self.collapse_t = None
        self.build_t = None
        self.side = 1
        self.parts = []        # [img, x, y, vx, vy, ang, va, vida, chão]
        self.snow_dots = []    # [x, y, vx, vy, vida, raio]
        self.claimed = None    # personagem que está indo montar/quebrar

    @property
    def destroyed(self) -> bool:
        """True quando está desmontado ou pela metade (precisa terminar de montar)."""
        return self.stage < 4

    @property
    def fully_built(self) -> bool:
        return self.stage >= 4 and self.collapse_t is None

    def _top(self):
        img = self.frames[0]
        return self.y + self.base_offset - img.get_height()

    def image(self):
        if self.collapse_t is not None and len(self.hits) > 1:
            return self.hits[1]
        if self.stage <= 0:
            return self.destroyed_img or self.frames[0]
        if self.stage < 4:
            idx = min(self.stage - 1, len(self.builds) - 1)
            return self.builds[idx] if self.builds else self.frames[0]
        if self.hit_t is not None and self.hits:
            return self.hits[0]
        if self.hp <= 2 and self.hits:
            return self.hits[0]
        return self.idle[int(self.time / self.IDLE_TIME) % len(self.idle)] if self.idle else self.frames[0]

    def _spawn_snow(self, count_parts=5, count_dots=10, upward=1.0):
        img = self.frames[0]
        w, h = img.get_size()
        cy = self._top() + h * 0.5
        for _ in range(count_parts):
            if not self.pieces:
                break
            pc = random.choice(self.pieces[:6] if upward < 1.2 else self.pieces)
            self.parts.append([
                pc,
                self.x + random.uniform(-0.18, 0.18) * w,
                cy + random.uniform(-0.15, 0.25) * h,
                self.side * random.uniform(30, 115) if upward >= 1.0 else random.uniform(-70, 70),
                -random.uniform(60, 165) * upward,
                random.uniform(0, 360),
                random.uniform(-420, 420),
                random.uniform(0.65, 1.25),
                self.y + random.uniform(-4, 12),
            ])
        for _ in range(count_dots):
            self.snow_dots.append([
                self.x + random.uniform(-0.26, 0.26) * w,
                cy + random.uniform(-0.1, 0.35) * h,
                random.uniform(-80, 80) + (self.side * 35 if upward >= 1.0 else 0),
                -random.uniform(45, 140) * upward,
                random.uniform(0.45, 0.95),
                max(2, round(random.uniform(2, 4) * max(0.7, self.scale))),
            ])

    def hit(self, from_side: str = "right"):
        """Golpe vindo de quem olha para `from_side`."""
        if self.stage <= 0 or self.collapse_t is not None:
            return
        if self.hit_t is not None and self.hit_t < 0.12:
            return
        self.side = 1 if from_side == "right" else -1
        self.hit_t = 0.0
        if self.stage < 4:
            self._break()
            return
        self.hp -= 1
        self._spawn_snow(count_parts=random.randint(4, 7), count_dots=random.randint(8, 14), upward=1.0)
        if self.hp <= 0:
            self._break()

    def _break(self):
        """Desmorona na pilha de neve (`hit_1` -> `destroyed`)."""
        self.stage = 0
        self.hp = 0
        self.collapse_t = 0.0
        self.hit_t = 0.0
        self._spawn_snow(count_parts=random.randint(7, 11), count_dots=random.randint(14, 22), upward=1.25)

    def build_step(self) -> bool:
        """Avança uma etapa na montagem do boneco de neve. Retorna True quando fica pronto."""
        if self.stage >= 4:
            return True
        self.collapse_t = None
        self.hit_t = None
        self.stage = min(4, self.stage + 1)
        self.build_t = 0.0
        self._spawn_snow(count_parts=random.randint(2, 4), count_dots=random.randint(8, 14), upward=0.75)
        if self.stage >= 4:
            self.hp = self.MAX_HP
            return True
        return False

    def update(self, dt):
        super().update(dt)
        if self.hit_t is not None:
            self.hit_t += dt
            if self.hit_t > 0.22:
                self.hit_t = None
        if self.collapse_t is not None:
            self.collapse_t += dt
            if self.collapse_t > self.COLLAPSE_TIME:
                self.collapse_t = None
        if self.build_t is not None:
            self.build_t += dt
            if self.build_t > self.BUILD_BOUNCE:
                self.build_t = None
        for pt in self.parts:
            pt[1] += pt[3] * dt
            pt[2] += pt[4] * dt
            pt[4] += 420 * dt
            pt[5] += pt[6] * dt
            pt[7] -= dt
            if pt[2] > pt[8]:
                pt[2], pt[4], pt[3], pt[6] = pt[8], -pt[4] * 0.28, pt[3] * 0.58, pt[6] * 0.5
        self.parts = [pt for pt in self.parts if pt[7] > 0]
        for sd in self.snow_dots:
            sd[0] += sd[2] * dt
            sd[1] += sd[3] * dt
            sd[3] += 320 * dt
            sd[4] -= dt
        self.snow_dots = [sd for sd in self.snow_dots if sd[4] > 0]

    def draw(self, surface, viewer=None):
        img = self.image()
        x = self.x
        if self.hit_t is not None:
            x += math.sin(self.hit_t * 60) * 3.5 * self.scale * max(0.0, 1 - self.hit_t / 0.22) * self.side
            if self.hit_t < self.FLASH:
                img = img.copy()
                img.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_MAX)
        elif self.build_t is not None:
            # leve impulso ao moldar uma nova parte de neve
            k = math.sin((self.build_t / self.BUILD_BOUNCE) * math.pi)
            w, h = img.get_size()
            img = pygame.transform.smoothscale(
                img,
                (max(1, round(w * (1.0 + 0.06 * k))), max(1, round(h * (1.0 - 0.05 * k)))),
            )
        base_y = round(self.y + self.base_offset)
        surface.blit(img, img.get_rect(midbottom=(round(x), base_y)))
        for pc, px, py, _, _, ang, _, life, _ in self.parts:
            im = pygame.transform.rotate(pc, ang)
            if life < 0.35:
                im.set_alpha(round(255 * life / 0.35))
            surface.blit(im, im.get_rect(center=(round(px), round(py))))
        for sx, sy, _, _, life, r in self.snow_dots:
            pygame.draw.circle(surface, (240, 246, 255), (round(sx), round(sy)), r)


class GrubNatal(Prop):
    """Grub de Natal interativo (arte em world/grub_natal/, recortada por tools/make_grub_natal.py).

    Ciclo de estados (`state`):
      - `"jar"`: preso no pote de vidro natalino (`jar_0..5`); bater (`hit`, 3 golpes) racha o vidro
        (`hit_0..2`) até quebrar (`shatter_0..2`), jogando a tampa (`lid`) e cacos (`piece_*`) longe.
      - `"free"`: livre pulando feliz com gorro de Natal (`free_0..2`) e estrelinhas; interagir
        (`interact`, ou após alguns segundos) faz ele mergulhar na neve (`burrow_0..1`).
      - `"snow"`: escondido no montinho de neve só com o gorro e estrelinhas de fora (`burrow_2`);
        interagir faz ele brotar da neve comemorando e reiniciar o ciclo."""
    kind = "grub_natal"
    MAX_HP = 3
    JAR_FRAME = 0.24
    FREE_FRAME = 0.17
    SHATTER_FRAME = 0.13
    BURROW_FRAME = 0.18
    FLASH = 0.08

    def __init__(self, x, y, defn):
        super().__init__(x, y, defn)
        from .config import SPRITES_DIR
        folder = SPRITES_DIR / "world" / "grub_natal"

        def ld(name, k=1.0):
            f = folder / f"{name}.png"
            if not f.exists():
                return None
            return pygame.transform.smoothscale_by(pygame.image.load(str(f)).convert_alpha(), self.scale * k)

        self.jar_frames = [img for img in (ld(f"jar_{i}") for i in range(6)) if img]
        self.hit_frames = [img for img in (ld(f"hit_{i}") for i in range(3)) if img]
        self.shatter_frames = [img for img in (ld(f"shatter_{i}") for i in range(3)) if img]
        self.free_frames = [img for img in (ld(f"free_{i}") for i in range(3)) if img]
        self.burrow_frames = [img for img in (ld(f"burrow_{i}") for i in range(3)) if img]
        self.broken_jar_img = ld("broken_jar")
        self.lid_img = ld("lid", 0.75)
        self.pieces = [img for img in (ld(f"piece_{i}", 0.55) for i in range(7)) if img]
        if self.jar_frames:
            self.frames = [self.jar_frames[0]]
            self.has_art = True
        img = self.frames[0]
        if "footprint" not in defn:
            self.defn = dict(self.defn, footprint=(max(12, round(img.get_width() * 0.28)), 12))
        self.state = defn.get("state", "jar")   # "jar" | "shattering" | "free" | "diving" | "snow" | "emerging"
        self.hp = self.MAX_HP
        self.state_t = 0.0
        self.hit_t = None
        self.side = 1
        self.broken_jar_t = 0.0
        self.lid_part = None         # [x, y, vx, vy, ang, va, no_chao, vida]
        self.parts = []              # [img, x, y, vx, vy, ang, va, vida, chao]
        self.snow_dots = []          # [x, y, vx, vy, vida, r]
        self.claimed = None

    def _top(self):
        img = self.frames[0]
        return self.y + self.base_offset - img.get_height()

    def _spawn_particles(self, shard_burst=False, snow_only=False):
        img = self.frames[0]
        w, h = img.get_size()
        cy = self._top() + h * 0.5
        pool = self.pieces[2:] if snow_only else self.pieces
        n_parts = random.randint(6, 10) if shard_burst else random.randint(3, 5)
        for _ in range(n_parts):
            if not pool:
                break
            pc = random.choice(pool)
            self.parts.append([
                pc,
                self.x + random.uniform(-0.2, 0.2) * w,
                cy + random.uniform(-0.15, 0.25) * h,
                self.side * random.uniform(35, 115) if shard_burst else random.uniform(-75, 75),
                -random.uniform(70, 175),
                random.uniform(0, 360),
                random.uniform(-420, 420),
                random.uniform(0.7, 1.3),
                self.y + random.uniform(-4, 12),
            ])
        for _ in range(random.randint(8, 16)):
            self.snow_dots.append([
                self.x + random.uniform(-0.25, 0.25) * w,
                cy + random.uniform(-0.1, 0.35) * h,
                random.uniform(-80, 80),
                -random.uniform(45, 135),
                random.uniform(0.45, 0.95),
                max(2, round(random.uniform(2, 4) * max(0.7, self.scale))),
            ])

    def hit(self, from_side: str = "right"):
        """Golpe no pote (ou no montinho de neve)."""
        self.side = 1 if from_side == "right" else -1
        if self.state == "snow":
            self.interact()
            return
        if self.state != "jar":
            return
        if self.hit_t is not None and self.hit_t < 0.12:
            return
        self.hit_t = 0.0
        self.hp -= 1
        self._spawn_particles(shard_burst=(self.hp <= 0), snow_only=(self.hp > 0))
        if self.hp <= 0:
            self.state = "shattering"
            self.state_t = 0.0
            self.broken_jar_t = 2.4
            h = self.frames[0].get_height()
            self.lid_part = [
                self.x,
                self._top() + h * 0.15,
                self.side * random.uniform(55, 105),
                -random.uniform(140, 195),
                0.0,
                self.side * random.uniform(260, 440),
                False,
                2.4,
            ]

    def interact(self) -> str:
        """Interação contextual (quando já está fora do pote ou escondido na neve)."""
        if self.state == "jar":
            self.hit("right")
            return "jar"
        if self.state == "free":
            self.state = "diving"
            self.state_t = 0.0
            self._spawn_particles(shard_burst=False, snow_only=True)
            return "dive"
        if self.state == "snow":
            self.state = "emerging"
            self.state_t = 0.0
            self._spawn_particles(shard_burst=False, snow_only=True)
            return "emerge"
        return self.state

    def image(self):
        if self.state == "jar":
            if self.hit_t is not None and self.hit_t < 0.14 and self.hit_frames:
                return self.hit_frames[0]
            if self.hp == 2 and len(self.hit_frames) > 1:
                return self.hit_frames[1]
            if self.hp <= 1 and len(self.hit_frames) > 2:
                return self.hit_frames[2]
            return self.jar_frames[int(self.time / self.JAR_FRAME) % len(self.jar_frames)] if self.jar_frames else self.frames[0]
        if self.state == "shattering" and self.shatter_frames:
            idx = min(len(self.shatter_frames) - 1, int(self.state_t / self.SHATTER_FRAME))
            return self.shatter_frames[idx]
        if self.state == "free" and self.free_frames:
            cycle = [0, 1, 2, 1]
            idx = cycle[int(self.time / self.FREE_FRAME) % len(cycle)]
            return self.free_frames[min(idx, len(self.free_frames) - 1)]
        if self.state == "diving" and self.burrow_frames:
            idx = min(len(self.burrow_frames) - 1, int(self.state_t / self.BURROW_FRAME))
            return self.burrow_frames[idx]
        if self.state == "snow" and self.burrow_frames:
            return self.burrow_frames[-1]
        if self.state == "emerging" and self.burrow_frames:
            seq = [self.burrow_frames[1], self.burrow_frames[0]] + (self.free_frames[1:3] if len(self.free_frames) >= 3 else [])
            idx = min(len(seq) - 1, int(self.state_t / self.BURROW_FRAME))
            return seq[idx]
        return self.frames[0]

    def update(self, dt):
        super().update(dt)
        self.state_t += dt
        if self.hit_t is not None:
            self.hit_t += dt
            if self.hit_t > 0.22:
                self.hit_t = None
        if self.broken_jar_t > 0:
            self.broken_jar_t = max(0.0, self.broken_jar_t - dt)
        if self.state == "shattering":
            if self.state_t >= self.SHATTER_FRAME * max(1, len(self.shatter_frames)):
                self.state = "free"
                self.state_t = 0.0
        elif self.state == "free":
            if self.state_t >= 22.0 and self.claimed is None:
                self.interact()
        elif self.state == "diving":
            if self.state_t >= self.BURROW_FRAME * max(1, len(self.burrow_frames)):
                self.state = "snow"
                self.state_t = 0.0
        elif self.state == "snow":
            if self.state_t >= 28.0 and self.claimed is None:
                self.interact()
        elif self.state == "emerging":
            if self.state_t >= self.BURROW_FRAME * 4:
                # Volta para o pote natalino depois de brincar na neve, pronto para ser salvo de novo
                self.state = "jar"
                self.hp = self.MAX_HP
                self.state_t = 0.0
                self._spawn_particles(shard_burst=False, snow_only=True)

        if self.lid_part is not None:
            lp = self.lid_part
            if not lp[6]:
                lp[0] += lp[2] * dt
                lp[1] += lp[3] * dt
                lp[3] += 480 * dt
                lp[4] += lp[5] * dt
                if lp[1] >= self.y + 4:
                    lp[1], lp[6], lp[4] = self.y + 4, True, 0.0
            lp[7] -= dt
            if lp[7] <= 0:
                self.lid_part = None

        for pt in self.parts:
            pt[1] += pt[3] * dt
            pt[2] += pt[4] * dt
            pt[4] += 420 * dt
            pt[5] += pt[6] * dt
            pt[7] -= dt
            if pt[2] > pt[8]:
                pt[2], pt[4], pt[3], pt[6] = pt[8], -pt[4] * 0.28, pt[3] * 0.58, pt[6] * 0.5
        self.parts = [pt for pt in self.parts if pt[7] > 0]
        for sd in self.snow_dots:
            sd[0] += sd[2] * dt
            sd[1] += sd[3] * dt
            sd[3] += 320 * dt
            sd[4] -= dt
        self.snow_dots = [sd for sd in self.snow_dots if sd[4] > 0]

    def draw(self, surface, viewer=None):
        base_y = round(self.y + self.base_offset)
        if self.broken_jar_t > 0 and self.broken_jar_img and self.state != "shattering":
            bj = self.broken_jar_img.copy()
            if self.broken_jar_t < 0.6:
                bj.set_alpha(round(255 * (self.broken_jar_t / 0.6)))
            surface.blit(bj, bj.get_rect(midbottom=(round(self.x), base_y)))
        img = self.image()
        x = self.x
        if self.hit_t is not None:
            x += math.sin(self.hit_t * 60) * 3.5 * self.scale * max(0.0, 1 - self.hit_t / 0.22) * self.side
            if self.hit_t < self.FLASH:
                img = img.copy()
                img.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_MAX)
        surface.blit(img, img.get_rect(midbottom=(round(x), base_y)))
        if self.lid_part is not None and self.lid_img:
            lp = self.lid_part
            li = pygame.transform.rotate(self.lid_img, -lp[4])
            if lp[7] < 0.5:
                li.set_alpha(round(255 * max(0.0, lp[7] / 0.5)))
            surface.blit(li, li.get_rect(midbottom=(round(lp[0]), round(lp[1]))))
        for pc, px, py, _, _, ang, _, life, _ in self.parts:
            im = pygame.transform.rotate(pc, ang)
            if life < 0.35:
                im.set_alpha(round(255 * life / 0.35))
            surface.blit(im, im.get_rect(center=(round(px), round(py))))
        for sx, sy, _, _, life, r in self.snow_dots:
            pygame.draw.circle(surface, (240, 246, 255), (round(sx), round(sy)), r)


KINDS = {cls.kind: cls for cls in (House, Tree, Campfire, Dummy, Bench, Lamp, Cave, Item, FruitTree, ZoteDummy, Snowman, GrubNatal)}


# itens da biblioteca que são árvores de frutas (dá para bater e derrubar fruta)
FRUIT_TREE_NAMES = ("arvore_frutas", "pinheiro")


def make_prop(defn: dict) -> Prop:
    x, y = defn["pos"]
    kind = defn["kind"]
    if kind == "item" and str(defn.get("name", "")).startswith(FRUIT_TREE_NAMES):
        kind = "fruit_tree"                          # (vale também para os já colocados)
    if kind == "item" and str(defn.get("name", "")).startswith("boneco_zote"):
        kind = "zote"                                # boneco de treino
    if kind == "item" and str(defn.get("name", "")).startswith("boneco_neve"):
        kind = "snowman"                             # boneco de neve (Knight / Hornet)
    if kind == "item" and str(defn.get("name", "")).lower().startswith("fogueira"):
        kind = "campfire"                            # fogueira interativa
    if kind == "item" and str(defn.get("name", "")).lower().startswith(("grub_natal", "group-natal", "group_natal")):
        kind = "grub_natal"                          # Grub de Natal no pote
    return KINDS[kind](x, y, defn)
