"""Efeitos animados do cenário, desenhados por cima do chão (antes dos objetos e dos
personagens, que continuam passando na frente). Definidos em scene.py ("effects").

Waterfall ("waterfall"): água correndo por cima da própria arte da ilha.
  "rect"   (x, y, w, h) em px da imagem do chão: onde a água corre
  "dir"    direção do fluxo (dx, dy), ex.: (0, 1) = caindo; (-0.85, 0.5) = riacho na diagonal
  "speed"  velocidade (px de tela por segundo)
  "splash" (x1, x2, y) em px da imagem: onde a água bate embaixo (respingos e névoa); opcional
  "mist"   True = névoa subindo do respingo

Como funciona:
  - a camada de água é a própria arte da cachoeira (só os pixels claros/azulados do
    retângulo), deslocada continuamente na direção do fluxo e misturada por cima da
    original: parece que a água desce;
  - riscos de luz finos escorrem mais rápido que a água;
  - as bordas do retângulo esmaecem, para não ter corte;
  - no "splash" saem gotinhas (sobem e caem com gravidade) e baforadas de névoa.
"""
import math
import random

import pygame


def _soft_blob(radius, color, alpha):
    s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for r in range(radius, 0, -1):
        a = round(alpha * (1 - r / radius) ** 1.5)
        pygame.draw.circle(s, (*color, a), (radius, radius), r)
    return s


class Waterfall:
    FLOW_ALPHA = 150          # quanto a camada que corre aparece por cima da arte
    STREAKS = 16              # riscos de luz

    def __init__(self, world, spec, seed=0):
        self.rng = random.Random(seed)
        k = world.k
        x, y, w, h = spec["rect"]
        sx, sy = world.to_screen((x, y))
        self.rect = pygame.Rect(round(sx), round(sy), max(4, round(w * k)), max(4, round(h * k)))
        self.rect = self.rect.clip(pygame.Rect((0, 0), world.ground.get_size()).move(world.ground_pos))
        dx, dy = spec.get("dir", (0, 1))
        n = math.hypot(dx, dy) or 1
        self.dir = (dx / n, dy / n)
        self.speed = spec.get("speed", 120) * k / 0.45      # px de tela (calibrado no mapa de Natal)
        self.y = self.rect.bottom                           # (ordenação, se precisar)
        self.t = 0.0
        self._build(world)
        sp = spec.get("splash")
        self.splash = None
        if sp:
            x1, x2, yy = sp
            a, b = world.to_screen((x1, yy)), world.to_screen((x2, yy))
            self.splash = (a[0], b[0], a[1])
        self.mist = spec.get("mist", False)
        self.drops = []       # [x, y, vx, vy, vida, vida_total, raio]
        self.puffs = []       # [x, y, vida, vida_total, escala]
        self._acc_drop = self._acc_mist = 0.0
        self._mist_img = _soft_blob(16, (235, 242, 250), 70)
        self.streaks = [self._new_streak(first=True) for _ in range(self.STREAKS)]

    def _build(self, world):
        """Água = pixels claros e azulados da arte no retângulo; alpha esmaece nas bordas."""
        r = self.rect
        src = world.ground.subsurface(r.move(-world.ground_pos[0], -world.ground_pos[1])).copy()
        w, h = r.size
        water = pygame.Surface((w, h), pygame.SRCALPHA)
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        edge = max(3, w // 7)
        for yy in range(h):
            fy = min(1.0, yy / 3, (h - 1 - yy) / max(3, h // 8))
            for xx in range(w):
                c = src.get_at((xx, yy))
                lum = (c.r + c.g + c.b) / 3
                if c.a < 200 or lum < 105 or c.b < c.r:
                    continue                          # rocha escura / fora da ilha
                fx = min(1.0, xx / edge, (w - 1 - xx) / edge)
                a = max(0.0, min(1.0, fx * fy * min(1.0, (lum - 105) / 40)))
                water.set_at((xx, yy), (c.r, c.g, c.b, 255))
                mask.set_at((xx, yy), (255, 255, 255, round(self.FLOW_ALPHA * a)))
        self.water = water
        self.mask = mask
        self.layer = pygame.Surface((w, h), pygame.SRCALPHA)

    def _new_streak(self, first=False):
        w, h = self.rect.size
        return {
            "x": self.rng.uniform(0, w), "y": self.rng.uniform(0, h), "pos": 0.0,
            "len": self.rng.uniform(6, 18), "spd": self.rng.uniform(1.2, 1.8),
            "alpha": self.rng.randint(110, 200), "w": self.rng.choice((1, 1, 2)),
        }

    # ---------- por quadro ----------
    def update(self, dt):
        self.t += dt
        for s in self.streaks:                 # riscos andam mais rápido que a água
            s["pos"] += self.speed * s["spd"] * dt
        if self.splash:
            x1, x2, y = self.splash
            self._acc_drop += dt * 55
            while self._acc_drop >= 1:
                self._acc_drop -= 1
                life = self.rng.uniform(0.35, 0.8)
                self.drops.append([self.rng.uniform(x1, x2), y + self.rng.uniform(-2, 2),
                                   self.rng.gauss(0, 18), -self.rng.uniform(25, 70), life, life,
                                   self.rng.choice((1, 1, 2))])
            if self.mist:
                self._acc_mist += dt * 4
                while self._acc_mist >= 1:
                    self._acc_mist -= 1
                    life = self.rng.uniform(1.6, 2.8)
                    self.puffs.append([self.rng.uniform(x1, x2), y - self.rng.uniform(0, 6), life, life,
                                       self.rng.uniform(0.6, 1.3)])
        for p in self.drops:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 170 * dt            # gravidade
            p[4] -= dt
        self.drops = [p for p in self.drops if p[4] > 0]
        for m in self.puffs:
            m[1] -= 9 * dt
            m[0] += math.sin(self.t + m[3]) * 3 * dt
            m[2] -= dt
        self.puffs = [m for m in self.puffs if m[2] > 0]

    # ---------- desenho ----------
    def draw(self, surface):
        r = self.rect
        w, h = r.size
        dx, dy = self.dir
        off = self.t * self.speed
        ox, oy = (dx * off) % w, (dy * off) % h
        layer = self.layer
        layer.fill((0, 0, 0, 0))
        for i in (0, -1):                      # 4 cópias = a água "dá a volta" sem emenda
            for j in (0, -1):
                layer.blit(self.water, (round(ox + i * w), round(oy + j * h)))
        # riscos de luz escorrendo
        for s in self.streaks:                 # na direção do fluxo, dando a volta no retângulo
            x0 = (s["x"] + dx * s["pos"]) % w
            y0 = (s["y"] + dy * s["pos"]) % h
            x1, y1 = x0 + dx * s["len"], y0 + dy * s["len"]
            pygame.draw.line(layer, (240, 248, 255, s["alpha"]), (x0, y0), (x1, y1), s["w"])
        layer.blit(self.mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)   # só onde é água
        surface.blit(layer, r.topleft)
        # névoa e respingos
        for m in self.puffs:
            k = m[2] / m[3]
            size = max(4, round(32 * m[4] * (1.4 - 0.6 * k)))
            img = pygame.transform.smoothscale(self._mist_img, (size, size))
            img.set_alpha(round(255 * min(1.0, k * 1.5) * (0.5 + 0.5 * k)))
            surface.blit(img, img.get_rect(center=(round(m[0]), round(m[1]))))
        for p in self.drops:                   # gotinhas: brancas, ficam azuladas no fim da vida
            fresh = p[4] / p[5] > 0.4
            color = (240, 248, 255) if fresh else (190, 212, 235)
            pygame.draw.circle(surface, color, (round(p[0]), round(p[1])), p[6] if fresh else 1)


class PlantSway:
    """Plantas e arbustos PINTADOS no chão balançando bem de leve ("sway").

    "plants": [(x0, y0, x1, y1), ...] em px da imagem do chão: a caixa de cada planta, com
              y1 = onde ela toca o chão (a base fica parada, o topo balança).
    "amp":    multiplica o balanço (padrão 1).

    Cada planta vira um recorte da própria arte do chão, inclinado em POSES posições com
    deslocamento de fração de pixel (decor.soft_sway_poses) e com as bordas de cima e dos
    lados esmaecidas, para não aparecer emenda com o chão parado. Cada uma tem seu ritmo; a
    chuva balança mais e um personagem passando por dentro agita a planta.
    """
    POSES = 13
    PAD = 0.3                 # margem de esmaecimento em volta da caixa (fração do tamanho)

    def __init__(self, world, spec, seed=0):
        from .decor import soft_sway_poses
        self.world = world
        self.rng = random.Random(seed + 7)
        self.t = 0.0
        self.y = 0
        gx, gy = world.ground_pos
        area = pygame.Rect((gx, gy), world.ground.get_size())
        amp_k = spec.get("amp", 1.0)
        self.plants = []
        for x0, y0, x1, y1 in spec.get("plants", []):
            (sx0, sy0), (sx1, sy1) = world.to_screen((x0, y0)), world.to_screen((x1, y1))
            w, h = sx1 - sx0, sy1 - sy0
            px, py = max(4, round(w * self.PAD)), max(4, round(h * self.PAD))
            r = pygame.Rect(round(sx0) - px, round(sy0) - py, round(w) + 2 * px, round(h) + py).clip(area)
            if r.w < 6 or r.h < 6:
                continue
            src = world.ground.subsurface(r.move(-gx, -gy)).copy()
            amp = max(0.9, min(2.4, r.h * 0.04)) * amp_k
            poses, pad = soft_sway_poses(src, amp, self.POSES)
            # esmaecer: transparente nas margens (lados e topo), base inteira
            mask = pygame.Surface(poses[0].get_size(), pygame.SRCALPHA)
            mw, mh = mask.get_size()
            for x in range(mw):
                fx = min(1.0, max(0.0, (x - pad) / px), max(0.0, (mw - pad - 1 - x) / px))
                for y in range(mh):
                    fy = min(1.0, y / py)
                    f = min(fx, fy)
                    f = f * f * (3 - 2 * f)
                    mask.set_at((x, y), (255, 255, 255, round(255 * f)))
            for p in poses:
                p.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            # retângulo dos "pés" dentro da planta (quem passa por ali agita)
            feet = pygame.Rect(round(sx0), round(sy0 + h * 0.4), round(w), max(4, round(h * 0.6)))
            self.plants.append({"poses": poses, "pos": (r.x - pad, r.y), "feet": feet,
                                "phase": self.rng.uniform(0, 6.3), "freq": self.rng.uniform(0.16, 0.32),
                                "rustle": 0.0})

    def update(self, dt):
        self.t += dt
        actors = getattr(self.world, "actors", ())
        for p in self.plants:
            p["rustle"] = max(0.0, p["rustle"] - dt * 0.9)
            for a in actors:
                if p["feet"].collidepoint(a.x, a.y) and a.state in ("walk", "run"):
                    p["rustle"] = 1.0

    def draw(self, surface):
        from .decor import breeze
        wind = getattr(self.world, "wind", 1.0)
        n = self.POSES
        for p in self.plants:
            v = breeze(self.t, p["phase"], p["freq"], wind)
            if p["rustle"]:
                v += math.sin(self.t * 18 + p["phase"]) * p["rustle"] * 0.9
            v = max(-1.0, min(1.0, v))
            surface.blit(p["poses"][round((v + 1) / 2 * (n - 1))], p["pos"])


KINDS = {"waterfall": Waterfall, "sway": PlantSway}


def make_effect(world, spec, seed=0):
    return KINDS[spec["kind"]](world, spec, seed)
