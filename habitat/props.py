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
    kind = "campfire"
    footprint = (58, 20)
    frame_duration = 0.09

    def __init__(self, x, y, defn):
        super().__init__(x, y, defn)
        self.sparks = []  # [x, y, vy, vida]
        self.rng = random.Random(3)
        self.glows = [radial_glow(r, (150, 78, 22)) for r in (220, 236, 252)]

    def placeholder_frames(self):
        frames = []
        for f in range(6):
            rng = random.Random(f * 31 + 5)
            s = _canvas(42, 44)
            # pedras em anel
            for i in range(9):
                a = math.pi * (0.05 + i / 8 * 0.9)
                px, py = 21 - math.cos(a) * 17, 38 + math.sin(a) * 3 - 2
                pygame.draw.circle(s, OUTLINE, (px, py), 4)
                pygame.draw.circle(s, (132, 128, 124), (px, py - 0.5), 3)
            # lenha cruzada
            pygame.draw.line(s, OUTLINE, (7, 39), (35, 31), 6)
            pygame.draw.line(s, OUTLINE, (7, 31), (35, 39), 6)
            pygame.draw.line(s, (122, 76, 40), (8, 38), (34, 31), 4)
            pygame.draw.line(s, (100, 62, 34), (8, 32), (34, 38), 4)
            # chamas: línguas em camadas (vermelho -> laranja -> amarelo)
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

    def update(self, dt):
        super().update(dt)
        if self.rng.random() < dt * 9:  # solta faíscas
            self.sparks.append([self.x + self.rng.uniform(-14, 14), self.y - 40,
                                -self.rng.uniform(40, 90), self.rng.uniform(0.6, 1.3)])
        for sp in self.sparks:
            sp[0] += math.sin(self.time * 6 + sp[1]) * 12 * dt
            sp[1] += sp[2] * dt
            sp[3] -= dt
        self.sparks = [sp for sp in self.sparks if sp[3] > 0]

    def draw_ground(self, surface):
        sh = _soft_ellipse(44, 12, (20, 20, 10), alpha=26)
        surface.blit(sh, sh.get_rect(center=(round(self.x), round(self.y - 6))))

    def draw(self, surface, viewer=None):
        super().draw(surface, viewer)
        for x, y, _, life in self.sparks:
            c = (255, 200, 90) if life > 0.4 else (230, 110, 40)
            surface.fill(c, (round(x), round(y), P, P))

    def draw_light(self, surface, darkness=0.0):
        glow = self.glows[int(self.time * 7) % len(self.glows)]
        add_light(surface, glow, (round(self.x), round(self.y - 30)), 0.45 + 0.55 * darkness)
        if darkness > 0.05:
            # o fogo é a própria luz: redesenha por cima, sem o escurecimento da noite
            img = self.image().copy()
            img.set_alpha(round(255 * min(1.0, darkness * 1.3)))
            surface.blit(img, img.get_rect(midbottom=(round(self.x), round(self.y))))
            for x, y, _, life in self.sparks:
                c = (255, 200, 90) if life > 0.4 else (230, 110, 40)
                surface.fill(c, (round(x), round(y), P, P))


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
        self.seats = defn.get("seats", [-32, 32])
        self.occupied = {}  # índice do assento -> personagem
        img = self.frames[0]
        self.seat_height = defn.get("seat_height", 0.42) * img.get_height()
        if "footprint" not in defn:
            self.defn = dict(defn, footprint=(round(img.get_width() * 0.85), 12))

    def free_seat(self, who=None):
        for i, _ in enumerate(self.seats):
            if self.occupied.get(i) in (None, who):
                return i
        return None

    def seat_pos(self, i):
        return self.x + self.seats[i], self.y + 3

    def approach(self, i):
        """Onde parar antes de sentar (na frente do assento, fora da área sólida)."""
        return self.x + self.seats[i], self.y + 34


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


KINDS = {cls.kind: cls for cls in (House, Tree, Campfire, Dummy, Bench, Lamp)}


def make_prop(defn: dict) -> Prop:
    x, y = defn["pos"]
    return KINDS[defn["kind"]](x, y, defn)
