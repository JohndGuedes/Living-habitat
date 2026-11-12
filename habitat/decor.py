"""Plantas decorativas animadas (gramas, flores, arbustos) espalhadas pela ilha.

Arte: assets/sprites/world/gramas/gramas.png — uma folha com várias linhas;
cada linha (ou trecho de linha) é um tipo de planta. Os desenhos de uma linha
são VARIAÇÕES (formatos/tamanhos um pouco diferentes), não quadros de um
balanço — tocá-los em sequência fazia a planta "tremer". Então cada planta
sorteia uma variação e o BALANÇO é feito por código: a imagem é inclinada
(cisalhamento) com a base parada e o topo indo de um lado para o outro.
Os desenhos são achados sozinhos (pixels visíveis conectados) e agrupados em
linhas pela base.

Vida:
- cada planta tem ritmo e fase próprios (não balançam todas juntas);
- `wind` (vem do clima: chuva = mais vento) aumenta e acelera o balanço;
- quando alguém passa por dentro, a planta se agita por um instante.

Quantidades e tamanho por tipo ficam em scene.py (DECOR).
"""
import logging
import math
import random

import pygame

from .config import SPRITES_DIR

log = logging.getLogger(__name__)

SHEET = SPRITES_DIR / "world" / "gramas" / "gramas.png"

# Inclinação máxima do topo (px) por família de planta
SWAY = {"grama": 6.0, "flor": 4.0, "arbusto": 2.2}
POSES = 11  # quantas inclinações pré-calculadas (de -máx a +máx)

# tipo -> (linha na folha, primeira variação, última variação exclusiva)
SETS = {
    "grama_alta":     (0, 0, 9),
    "grama_cheia":    (1, 0, 9),
    "grama_pequena":  (2, 0, 11),
    "flor_branca":    (3, 0, 5),
    "flor_vermelha":  (3, 5, 10),
    "flor_amarela":   (4, 0, 5),
    "flor_azul":      (4, 5, 10),
    "arbusto":        (5, 0, 6),
    "arbusto_rosa":   (6, 0, 5),
    "arbusto_branco": (6, 5, 8),
    "arbusto_liso":   (6, 8, 11),
}


def _rows(sheet: pygame.Surface):
    """Recortes da folha agrupados em linhas (de cima p/ baixo, esquerda p/ direita)."""
    mask = pygame.mask.from_surface(sheet, 40)
    rects = sorted((r for r in mask.get_bounding_rects() if r.w * r.h > 400), key=lambda r: r.bottom)
    rows = []
    for r in rects:
        if rows and abs(rows[-1][-1].bottom - r.bottom) < 40:
            rows[-1].append(r)
        else:
            rows.append([r])
    return [sorted(row, key=lambda r: r.x) for row in rows]


def _base_x(img: pygame.Surface) -> float:
    """Centro x da parte de baixo (onde a planta sai do chão): âncora estável
    mesmo com as folhas balançando."""
    h = img.get_height()
    xs = [x for y in range(int(h * 0.82), h) for x in range(img.get_width()) if img.get_at((x, y))[3] > 60]
    return sum(xs) / len(xs) if xs else img.get_width() / 2


def load_sets(scales: dict[str, float]) -> dict[str, list[tuple[pygame.Surface, float]]]:
    """{tipo: [(variação, base_x), ...]} já escalados. Vazio se a folha não existir."""
    if not SHEET.exists():
        log.warning("sem %s — sem plantas decorativas", SHEET.name)
        return {}
    sheet = pygame.image.load(SHEET).convert_alpha()
    rows = _rows(sheet)
    out = {}
    for name, (row, a, b) in SETS.items():
        if row >= len(rows) or b > len(rows[row]):
            log.warning("plantas: '%s' não encontrado na folha (linha %d)", name, row)
            continue
        k = scales.get(name, scales.get("*", 0.3))
        frames = []
        for rect in rows[row][a:b]:
            img = pygame.transform.smoothscale_by(sheet.subsurface(rect), k)
            frames.append((img, _base_x(img)))
        out[name] = frames
    return out


def sway_poses(img: pygame.Surface, amp: float, n: int = POSES):
    """Versões inclinadas da imagem: base parada, topo deslocado de -amp a +amp
    (cisalhamento por faixas de 2 px). Retorna (poses, margem lateral)."""
    w, h = img.get_size()
    pad = math.ceil(amp) + 1
    poses = []
    for k in range(n):
        a = -amp + 2 * amp * k / (n - 1)
        s = pygame.Surface((w + 2 * pad, h), pygame.SRCALPHA)
        for y in range(0, h, 2):
            off = a * ((h - y) / h) ** 1.6
            s.blit(img, (pad + round(off), y), (0, y, w, 2))
        poses.append(s)
    return poses, pad


def soft_sway_poses(img: pygame.Surface, amp: float, n: int = POSES, up: int = 3, curve: float = 1.6):
    """Como sway_poses, mas com deslocamento de fração de pixel (feito numa cópia `up`x
    maior e reduzida com suavização): para balanços bem leves (1-2 px), sem "degraus".
    Retorna (poses, margem lateral)."""
    w, h = img.get_size()
    pad = math.ceil(amp) + 1
    big = pygame.transform.scale(img, (w * up, h * up))    # sem suavizar: parada = idêntica
    H = h * up
    poses = []
    for k in range(n):
        a = (-amp + 2 * amp * k / (n - 1)) * up
        s = pygame.Surface(((w + 2 * pad) * up, H), pygame.SRCALPHA)
        for y in range(0, H, 2):
            off = a * ((H - y) / H) ** curve
            s.blit(big, (pad * up + round(off), y), (0, y, w * up, 2))
        poses.append(pygame.transform.smoothscale(s, (w + 2 * pad, h)))
    return poses, pad


def breeze(t: float, phase: float, freq: float, wind: float = 1.0) -> float:
    """Brisa leve e irregular, de -1 a 1 (wind > 1 = chuva/vento: balança mais)."""
    x = t * math.tau * freq + phase
    v = math.sin(x) * 0.7 + math.sin(x * 2.3 + 1.7) * 0.3
    return max(-1.0, min(1.0, v * min(1.0, 0.6 + 0.25 * (wind - 1))))


_POSE_CACHE: dict = {}


class Decor:
    def __init__(self, kind, x, y, variants, rng: random.Random, footprint=None):
        self.kind = kind
        self.x, self.y = x, y
        idx = rng.randrange(len(variants))
        flip = rng.random() < 0.5            # variedade: metade espelhada
        key = (kind, idx, flip)
        if key not in _POSE_CACHE:
            img, bx = variants[idx]
            if flip:
                img, bx = pygame.transform.flip(img, True, False), img.get_width() - bx
            amp = next((v for k, v in SWAY.items() if kind.startswith(k)), 4.0)
            poses, pad = sway_poses(img, amp)
            _POSE_CACHE[key] = (poses, bx + pad)
        self.poses, self.base_x = _POSE_CACHE[key]
        self.phase = rng.uniform(0, math.tau)
        self.freq = rng.uniform(0.35, 0.6)    # balanços por segundo (ritmo próprio)
        self.time = 0.0
        self.rustle = 0.0                    # agitação quando alguém passa
        self.wind = 1.0
        self.footprint = footprint

    @property
    def solid(self) -> pygame.Rect | None:
        if not self.footprint:
            return None
        w, d = self.footprint
        return pygame.Rect(round(self.x - w / 2), round(self.y - d), w, d)

    def update(self, dt: float, wind: float = 1.0, actors=()):
        for a in actors:
            if abs(a.x - self.x) < 34 and abs(a.y - self.y) < 16 and getattr(a, "state", "") in ("walk", "run", "land"):
                self.rustle = 0.7
        self.rustle = max(0.0, self.rustle - dt)
        self.wind = wind
        self.time += dt * (0.8 + 0.4 * wind)

    def lean(self) -> float:
        """Inclinação atual de -1 a 1."""
        t = self.time * math.tau * self.freq + self.phase
        breeze = math.sin(t) * 0.75 + math.sin(t * 2.3 + 1.7) * 0.25   # brisa irregular
        strength = min(1.0, 0.35 + 0.3 * self.wind)                      # chuva = mais vento
        v = breeze * strength
        if self.rustle:  # agitação rápida que vai acalmando
            v += math.sin(self.time * 22) * self.rustle * 1.2
        return max(-1.0, min(1.0, v))

    def draw(self, surface: pygame.Surface, viewer=None):
        n = len(self.poses)
        img = self.poses[round((self.lean() + 1) / 2 * (n - 1))]
        surface.blit(img, (round(self.x - self.base_x), round(self.y - img.get_height())))


def scatter(world, counts: dict[str, int], scales: dict[str, float], solid: dict[str, tuple],
            keep_clear: list[tuple[float, float, float]], seed: int = 7) -> list[Decor]:
    """Espalha plantas em pontos andáveis da ilha, sem amontoar.
    keep_clear: [(x, y, raio)] áreas livres (ex.: onde o personagem nasce)."""
    sets = load_sets(scales)
    rng = random.Random(seed)
    gx, gy = world.ground_pos
    gw, gh = world.ground.get_size()
    placed: list[Decor] = []
    # arbustos primeiro (precisam de mais espaço)
    for kind in sorted(counts, key=lambda k: not k.startswith("arbusto")):
        if kind not in sets:
            continue
        variants = sets[kind]
        w = max(img.get_width() for img, _ in variants)
        spacing = max(30, w * 0.7)
        for _ in range(counts[kind]):
            for _try in range(200):
                x, y = rng.uniform(gx, gx + gw), rng.uniform(gy, gy + gh)
                base = pygame.Rect(round(x - w * 0.35), round(y - 6), round(w * 0.7), 8)
                if not world.walkable(base):
                    continue
                if any(abs(d.x - x) < spacing and abs(d.y - y) < spacing * 0.5 for d in placed):
                    continue
                if any((x - cx) ** 2 + (y - cy) ** 2 < r * r for cx, cy, r in keep_clear):
                    continue
                placed.append(Decor(kind, x, y, variants, rng, solid.get(kind)))
                break
    return placed
