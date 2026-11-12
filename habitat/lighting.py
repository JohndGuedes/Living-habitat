"""Iluminação, sombras e reflexos.

SceneLights ("lighting" no scene.py da área):
  "warm":    luz quente, em px da imagem do chão. Dois jeitos:
             {"pos": (x, y), "radius": r, "color", "flicker"}  brilho difuso (lanterna, estrela)
             {"kind": "opening", "rect": (x, y, w, h), "spill": (dx, dy, comprimento, abertura),
              "radius", "color", "flicker"}  luz vindo DE DENTRO por uma abertura (porta,
              janela): a abertura brilha por inteiro, um halo suave em volta e a luz se
              espalhando no chão à frente num leque que esmaece
  "strings": [[(x, y), (x, y), ...], ...]  fios de pisca-pisca: lâmpadas a cada BULB_GAP px ao
             longo da linha, com cores alternadas, piscando cada uma no seu ritmo
  "sheen":   True = brilho do céu deslizando devagar sobre o lago congelado
  Desenhado depois do escurecimento (luz aditiva): forte à noite, fraquinho de dia.

Sombras do sol (cast_shadow): a silhueta do personagem/objeto deitada no chão, inclinada
para o lado oposto ao sol (Environment.sun): de manhã para um lado, à tarde para o outro,
comprida no começo e no fim do dia, sumindo à noite.

Reflexos (reflect): quem está sobre o gelo (ou água) aparece de cabeça para baixo debaixo
dos pés, azulado e meio transparente, recortado pela forma do lago.
"""
import math
import random

import pygame

BULB_GAP = 20                  # px da imagem entre lâmpadas de um fio
BULB_COLORS = [(255, 70, 70), (90, 255, 120), (255, 205, 80), (110, 170, 255), (255, 110, 220)]


def _glow(radius, color, softness=3.0):
    """Brilho difuso (fundo preto, para luz aditiva): queda gaussiana, sem anéis.
    Calculado pequeno e ampliado com suavização."""
    radius = max(3, round(radius))
    n = max(8, min(48, radius // 2))                 # resolução da conta
    small = pygame.Surface((n * 2, n * 2))
    for y in range(n * 2):
        for x in range(n * 2):
            d = math.hypot(x + 0.5 - n, y + 0.5 - n) / n
            k = math.exp(-softness * d * d) * max(0.0, 1 - d)
            small.set_at((x, y), [round(c * k) for c in color])
    return pygame.transform.smoothscale(small, (radius * 2, radius * 2))


def _blur(surface, amount):
    """Desfoque barato: reduz e amplia de volta (duas vezes)."""
    w, h = surface.get_size()
    for _ in range(2):
        sw, sh = max(1, round(w / amount)), max(1, round(h / amount))
        surface = pygame.transform.smoothscale(pygame.transform.smoothscale(surface, (sw, sh)), (w, h))
    return surface


def _opening_light(world, spec):
    """Luz de dentro da casa saindo por uma abertura (porta/janela): (imagem, topo-esquerdo).

    A ilha é isométrica: a soleira acompanha a parede ("edge": direção da base da parede)
    e a luz sai para a frente dessa parede ("spill": dx, dy, comprimento, abertura), num
    leque que se abre e esmaece."""
    k = world.k
    x, y, w, h = spec["rect"]
    color = spec.get("color", (255, 160, 80))
    dx, dy, length, spread = spec.get("spill", (0.0, 1.0, 60, 1.8))
    n = math.hypot(dx, dy) or 1
    dx, dy = dx / n, dy / n
    ex, ey = spec.get("edge", (1.0, 0.0))
    n = math.hypot(ex, ey) or 1
    ex, ey = ex / n, ey / n
    halo = spec.get("radius", max(w, h))
    cx0, cy0 = x + w / 2, y + h                     # meio da soleira
    hw0 = w / 2 / max(0.3, abs(ex))                  # meia largura ao longo da parede

    def band(f):
        """Quadrilátero do leque da soleira até a fração f do comprimento."""
        cx1, cy1 = cx0 + dx * length * f, cy0 + dy * length * f
        hw1 = hw0 * (1 + (spread - 1) * f)
        return [(cx0 - ex * hw0, cy0 - ey * hw0), (cx0 + ex * hw0, cy0 + ey * hw0),
                (cx1 + ex * hw1, cy1 + ey * hw1), (cx1 - ex * hw1, cy1 - ey * hw1)]

    pts = band(1.0) + [(x - halo, y - halo), (x + w + halo, y + h + halo)]
    bx = min(p[0] for p in pts) - halo / 2
    by = min(p[1] for p in pts) - halo / 2
    bw = max(p[0] for p in pts) + halo / 2 - bx
    bh = max(p[1] for p in pts) + halo / 2 - by
    W, H = max(4, round(bw * k)), max(4, round(bh * k))
    surf = pygame.Surface((W, H))

    def P(px, py):
        return ((px - bx) * k, (py - by) * k)

    # 1) leque de luz no chão: faixas da soleira até longe, cada vez mais fracas e largas
    bands = 16
    for i in range(bands, 0, -1):
        f = i / bands
        a = (1 - f) ** 1.3
        pygame.draw.polygon(surf, [round(c * (0.2 + 0.6 * a)) for c in color], [P(*p) for p in band(f)])
    # 2) a abertura inteira brilhando (luz de dentro)
    r = pygame.Rect(*[round(v) for v in P(x, y)], max(1, round(w * k)), max(1, round(h * k)))
    pygame.draw.rect(surf, [round(c * 0.9) for c in color], r, border_radius=max(1, r.w // 2))
    surf = _blur(surf, max(2.0, 6 * k * max(1.0, w / 30)))
    # 3) halo suave em volta da abertura
    g = _glow(halo * k, [round(c * 0.6) for c in color], softness=2.2)
    surf.blit(g, g.get_rect(center=r.center), special_flags=pygame.BLEND_ADD)
    return surf, world.to_screen((bx, by))


class SceneLights:
    def __init__(self, world, spec, seed=0):
        self.world = world
        rng = random.Random(seed)
        k = world.k
        self.t = 0.0
        self.warm = []
        for w in spec.get("warm", []):
            col = w.get("color", (255, 170, 90))
            if w.get("kind") == "opening":            # porta / janela: luz vindo de dentro
                img, (x, y) = _opening_light(world, w)
                self.warm.append({"img": img, "topleft": (x, y), "flicker": w.get("flicker", 0.06),
                                  "phase": rng.uniform(0, 6.3)})
                continue
            x, y = world.to_screen(w["pos"])
            r = w.get("radius", 80) * k
            img = _glow(r, col, softness=2.6)
            core = _glow(max(4, r * 0.3), tuple(min(255, c + 60) for c in col), softness=4.0)
            img.blit(core, core.get_rect(center=img.get_rect().center), special_flags=pygame.BLEND_ADD)
            self.warm.append({"img": img, "topleft": (x - img.get_width() / 2, y - img.get_height() / 2),
                              "flicker": w.get("flicker", 0.1), "phase": rng.uniform(0, 6.3)})
        self.bulbs = []
        n = 0
        for line in spec.get("strings", []):
            pts = [world.to_screen(p) for p in line]
            gap = BULB_GAP * k
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                seg = math.hypot(x1 - x0, y1 - y0)
                steps = max(1, int(seg / gap))
                for i in range(steps):
                    f = i / steps
                    col = BULB_COLORS[n % len(BULB_COLORS)]
                    n += 1
                    self.bulbs.append({"x": x0 + (x1 - x0) * f, "y": y0 + (y1 - y0) * f, "col": col,
                                       "phase": rng.uniform(0, 6.3), "speed": rng.uniform(1.2, 2.6)})
            if pts:
                col = BULB_COLORS[n % len(BULB_COLORS)]
                n += 1
                self.bulbs.append({"x": pts[-1][0], "y": pts[-1][1], "col": col,
                                   "phase": rng.uniform(0, 6.3), "speed": rng.uniform(1.2, 2.6)})
        self._bulb_glow = {c: _glow(13, c, softness=3.2) for c in BULB_COLORS}
        self._bulb_core = {c: _glow(4, tuple(min(255, v + 110) for v in c), softness=3.0) for c in BULB_COLORS}
        self.sheen = spec.get("sheen", False)
        self._sheen_band = None

    def update(self, dt):
        self.t += dt

    # ---------- desenho (depois do escurecimento) ----------
    def draw(self, surface, darkness):
        night = max(0.0, min(1.0, (darkness - 0.1) / 0.6))
        base = 0.18 + 0.82 * night                   # de dia ainda dá para ver um pouco
        add = pygame.BLEND_ADD
        for w in self.warm:
            fl = 1 - w["flicker"] * (0.5 + 0.5 * math.sin(self.t * 9 + w["phase"])) * (0.6 + 0.4 * math.sin(self.t * 23))
            self._blit_at(surface, w["img"], w["topleft"], base * fl)
        for b in self.bulbs:
            tw = 0.55 + 0.45 * math.sin(self.t * b["speed"] + b["phase"])
            s = (0.25 + 0.75 * night) * tw
            self._blit(surface, self._bulb_glow[b["col"]], (b["x"], b["y"]), s)
            self._blit(surface, self._bulb_core[b["col"]], (b["x"], b["y"]), min(1.0, s * 1.5))
        if self.sheen:
            self._draw_sheen(surface, 0.35 + 0.4 * (1 - night))

    @staticmethod
    def _blit_at(surface, glow, topleft, strength):
        if strength <= 0.02:
            return
        if strength < 0.99:
            glow = glow.copy()
            v = round(255 * min(1.0, strength))
            glow.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
        surface.blit(glow, (round(topleft[0]), round(topleft[1])), special_flags=pygame.BLEND_ADD)

    @staticmethod
    def _blit(surface, glow, center, strength):
        if strength <= 0.02:
            return
        if strength < 0.99:
            glow = glow.copy()
            v = round(255 * min(1.0, strength))
            glow.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
        surface.blit(glow, glow.get_rect(center=(round(center[0]), round(center[1]))), special_flags=pygame.BLEND_ADD)

    def _draw_sheen(self, surface, strength):
        """Faixa de brilho do céu deslizando sobre o gelo (só onde é lago)."""
        w = self.world
        lake = w.lake_surface()
        if lake is None:
            return
        rect, mask = lake
        if self._sheen_band is None or self._sheen_band.get_size() != rect.size:
            band = pygame.Surface(rect.size, pygame.SRCALPHA)
            self._sheen_band = band
        band = self._sheen_band
        band.fill((0, 0, 0, 0))
        span = rect.w + rect.h
        pos = (self.t * 18) % (span + 120) - 60
        for i in range(-40, 41, 2):                  # faixa diagonal suave
            a = round(70 * strength * (1 - abs(i) / 40))
            x = pos + i
            pygame.draw.line(band, (200, 225, 255, a), (x, 0), (x - rect.h * 0.6, rect.h), 2)
        band.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(band, rect.topleft)


# ---------------------------------------------------------------- sombras
_shadow_cache = {}


def cast_shadow(surface, img, foot, anchor, sun, max_cache=600):
    """Sombra do sol: `img` (quadro já virado para o lado certo), `foot` = pés na tela,
    `anchor` = (ax, ay) dos pés dentro de img. `sun` = (lado, comprimento, força)."""
    side, length, strength = sun
    if strength <= 0.02:
        return
    ax, ay = anchor
    h = img.get_height()
    squash = max(0.08, 0.32 * length)
    shear = side * (0.5 + 0.9 * length)            # px de lado por px de altura
    key = (id(img), round(squash, 2), round(shear, 2))
    sh = _shadow_cache.get(key)
    if sh is None:
        if len(_shadow_cache) > max_cache:
            _shadow_cache.clear()
        sil = img.copy()
        sil.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MIN)    # silhueta preta
        nh = max(1, round(ay * squash))              # só até os pés (o que está acima do chão)
        body = pygame.transform.smoothscale(sil.subsurface((0, 0, img.get_width(), min(h, round(ay)))),
                                            (img.get_width(), nh))
        extra = round(abs(shear) * nh)
        sh = pygame.Surface((img.get_width() + extra, nh), pygame.SRCALPHA)
        for row in range(nh):                        # cisalhamento: a "cabeça" vai para o lado
            up = nh - 1 - row                        # distância dos pés
            dx = shear * up
            x = round(dx) + (extra if shear < 0 else 0)
            sh.blit(body, (x, row), (0, row, img.get_width(), 1))
        _shadow_cache[key] = sh
    shadow = sh
    a = round(255 * strength)
    extra = shadow.get_width() - img.get_width()
    left = foot[0] - ax - (extra if shear < 0 else 0)
    top = foot[1] - shadow.get_height()
    tmp = shadow.copy()
    tmp.set_alpha(a)
    surface.blit(tmp, (round(left), round(top)))


# ---------------------------------------------------------------- reflexos
def reflect(surface, world, img, foot, anchor, lift=0.0, alpha=150):
    """Reflexo no gelo/água: img de cabeça para baixo com a linha dos pés em `foot`,
    recortado pelo lago (world.lake_surface)."""
    lake = world.lake_surface()
    if lake is None:
        return
    rect, mask = lake
    ax, ay = anchor
    flip = pygame.transform.flip(img, False, True)
    h = img.get_height()
    left = round(foot[0] - ax)
    top = round(foot[1] - (h - ay) + lift)          # pulando: o reflexo se afasta
    r = pygame.Rect(left, top, flip.get_width(), h)
    clip = r.clip(rect)
    if not clip.w or not clip.h:
        return
    part = flip.subsurface(clip.move(-left, -top)).copy()
    part.fill((200, 220, 245, 255), special_flags=pygame.BLEND_RGBA_MULT)   # levemente azulado
    part.blit(mask, (0, 0), clip.move(-rect.x, -rect.y), special_flags=pygame.BLEND_RGBA_MULT)
    part.set_alpha(alpha)
    surface.blit(part, clip.topleft)
