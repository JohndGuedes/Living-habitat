"""O minimundo: a ilha flutuante (chão) + objetos do cenário (props.py,
posicionados por scene.py).

Chão: assets/sprites/world/ground/ground.png, gerado por tools/make_ground.py.
Onde dá para andar: assets/sprites/world/ground/walkable.png (branco = anda),
esticado sobre a ilha. Pode ser retocado à mão num editor de imagem.
"""
import logging
from collections import deque

import pygame

from .config import SPRITES_DIR
from .decor import scatter
from .props import make_prop
from .scene import DECOR, DECOR_SCALE, DECOR_SEED, DECOR_SOLID, SCENE, SPAWN

log = logging.getLogger(__name__)

GROUND_DIR = SPRITES_DIR / "world" / "ground"
SKY_TOP = (118, 168, 210)
SKY_BOTTOM = (176, 210, 228)


class World:
    def __init__(self, width: int, height: int, margin: int = 16):
        self.width, self.height = width, height
        self.background = self._sky()
        self.ground, self.ground_pos, self.walk_mask = self._load_ground(margin)
        self.props = [make_prop(d) for d in SCENE]
        # plantas animadas (deixa livre a área onde o personagem nasce)
        self.decor = scatter(self, DECOR, DECOR_SCALE, DECOR_SOLID,
                             keep_clear=[(*SPAWN, 70)] + [(p.x, p.y, 95) for p in self.props],
                             seed=DECOR_SEED)

    # ---------- montagem ----------
    def _sky(self) -> pygame.Surface:
        s = pygame.Surface((self.width, self.height))
        for y in range(self.height):
            t = y / (self.height - 1)
            s.fill([round(a + (b - a) * t) for a, b in zip(SKY_TOP, SKY_BOTTOM)], (0, y, self.width, 1))
        return s

    def _load_ground(self, margin):
        """Ilha escalada para caber na tela (centralizada) + máscara andável."""
        path = GROUND_DIR / "ground.png"
        if not path.exists():
            log.warning("sem %s — rode tools/make_ground.py. Usando chão liso.", path.name)
            img = pygame.Surface((self.width - 2 * margin, self.height - 2 * margin))
            img.fill((104, 156, 50))
            mask = pygame.mask.Mask(img.get_size(), fill=True)
            return img, (margin, margin), mask

        img = pygame.image.load(path).convert_alpha()
        k = min((self.width - 2 * margin) / img.get_width(), (self.height - 2 * margin) / img.get_height())
        img = pygame.transform.smoothscale_by(img, k)
        pos = ((self.width - img.get_width()) // 2, (self.height - img.get_height()) // 2)

        wpath = GROUND_DIR / "walkable.png"
        if wpath.exists():
            wimg = pygame.image.load(wpath).convert()
            mask = pygame.mask.from_threshold(wimg, (255, 255, 255), (60, 60, 60, 255))
            mask = mask.scale(img.get_size())
        else:  # sem mapa: anda em qualquer parte visível da ilha
            log.warning("sem walkable.png — andando em toda a ilha")
            mask = pygame.mask.from_surface(img)
        return img, pos, mask

    # ---------- por quadro ----------
    def update(self, dt: float, wind: float = 1.0, actors=()):
        """`wind` acelera o balanço das plantas; `actors` agitam as que atravessam."""
        for p in self.props:
            p.update(dt)
        for d in self.decor:
            d.update(dt, wind, actors)

    @property
    def drawables(self) -> list:
        """Tudo que é desenhado ordenado por profundidade (junto do personagem)."""
        return self.props + self.decor

    def draw(self, surface: pygame.Surface):
        """Céu + ilha + camada de chão dos objetos (sombras). Objetos e personagem
        são desenhados depois, ordenados por y (veja Game.step)."""
        surface.blit(self.background, (0, 0))
        surface.blit(self.ground, self.ground_pos)
        for p in self.props:
            p.draw_ground(surface)

    def draw_lights(self, surface: pygame.Surface, darkness: float = 0.0):
        for p in self.props:
            p.draw_light(surface, darkness)

    def draw_debug(self, surface: pygame.Surface):
        """Contorno da área andável (debug)."""
        ox, oy = self.ground_pos
        pts = self.walk_mask.outline(4)
        if len(pts) > 2:
            pygame.draw.lines(surface, (80, 220, 255), True, [(x + ox, y + oy) for x, y in pts], 2)

    # ---------- regras do chão ----------
    def walkable(self, rect: pygame.Rect) -> bool:
        """True se `rect` (pés de alguém) está inteiro dentro da área andável."""
        ox, oy = self.ground_pos
        foot = pygame.mask.Mask(rect.size, fill=True)
        return self.walk_mask.overlap_area(foot, (rect.x - ox, rect.y - oy)) == rect.w * rect.h

    def blocked(self, rect: pygame.Rect) -> bool:
        """True se `rect` sai da área andável ou encosta em algum objeto sólido."""
        if not self.walkable(rect):
            return True
        return any(p.solid is not None and p.solid.colliderect(rect) for p in self.props + self.decor)

    def clamp(self, entity):
        """Garante que a entidade fica dentro da tela (a máscara cuida do resto)."""
        entity.x = max(0, min(self.width, entity.x))
        entity.y = max(0, min(self.height, entity.y))

    def nearest_walkable(self, x: float, y: float, rect_at) -> tuple[float, float]:
        """Ponto andável mais perto de (x, y). `rect_at(x, y)` = retângulo dos pés."""
        for r in range(0, max(self.width, self.height), 8):
            for dx in range(-r, r + 1, 8):
                for dy in ((-r, r) if abs(dx) != r else range(-r, r + 1, 8)):
                    if self.walkable(rect_at(x + dx, y + dy)):
                        return x + dx, y + dy
        return x, y

    # ---------- navegação (usada pela rotina do personagem) ----------
    NAV_CELL = 16

    def build_nav(self, foot_at):
        """Prepara a grade de navegação. `foot_at(x, y)` = retângulo dos pés.
        Chamar depois que o personagem existir (o tamanho dos pés importa)."""
        self._foot_at = foot_at
        C = self.NAV_CELL
        self.nav_w, self.nav_h = self.width // C, self.height // C
        self.nav = [[self.walkable(foot_at(cx * C + C / 2, cy * C + C / 2)) and
                     not self._solid_hit(foot_at(cx * C + C / 2, cy * C + C / 2))
                     for cx in range(self.nav_w)] for cy in range(self.nav_h)]
        self.nav_cells = [(cx, cy) for cy in range(self.nav_h) for cx in range(self.nav_w) if self.nav[cy][cx]]
        self.shore = self._find_shore()

    def _solid_hit(self, rect):
        return any(p.solid is not None and p.solid.colliderect(rect) for p in self.props + self.decor)

    def _cell_center(self, cx, cy):
        C = self.NAV_CELL
        return cx * C + C / 2, cy * C + C / 2

    def _is_water(self, x, y) -> bool:
        gx, gy = round(x - self.ground_pos[0]), round(y - self.ground_pos[1])
        if not (0 <= gx < self.ground.get_width() and 0 <= gy < self.ground.get_height()):
            return False
        r, g, b, a = self.ground.get_at((gx, gy))
        return a > 200 and b >= 85 and r <= 100 and g >= 90  # azul-esverdeado do lago

    def _find_shore(self):
        """Pontos andáveis com água logo ao lado (esquerda/direita): onde ele bebe.
        Retorna [(x, y, lado_da_agua)]."""
        out = []
        for cx, cy in self.nav_cells:
            x, y = self._cell_center(cx, cy)
            for side, sx in (("right", 1), ("left", -1)):
                if any(self._is_water(x + sx * d, y + dy) for d in (30, 42, 54) for dy in (-6, -14)):
                    out.append((x, y, side))
                    break
        return out

    def random_point(self, rng, near=None, radius=None):
        """Ponto andável aleatório (opcionalmente perto de `near`)."""
        cells = self.nav_cells
        if near is not None and radius:
            nx, ny = near
            close = [c for c in cells if (self._cell_center(*c)[0] - nx) ** 2 +
                     (self._cell_center(*c)[1] - ny) ** 2 <= radius * radius]
            cells = close or cells
        return self._cell_center(*rng.choice(cells))

    def clear_line(self, a, b) -> bool:
        """Dá para andar em linha reta de a até b?"""
        (x0, y0), (x1, y1) = a, b
        steps = max(1, int(max(abs(x1 - x0), abs(y1 - y0)) / 8))
        for i in range(steps + 1):
            t = i / steps
            if self.blocked(self._foot_at(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)):
                return False
        return True

    def find_path(self, start, goal) -> list[tuple[float, float]]:
        """Caminho (lista de pontos) de start até goal pela grade andável (BFS),
        simplificado em retas. Lista vazia se não houver caminho."""
        if self.clear_line(start, goal):
            return [goal]
        C = self.NAV_CELL

        def cell_of(p):
            cx, cy = int(p[0] // C), int(p[1] // C)
            if 0 <= cx < self.nav_w and 0 <= cy < self.nav_h and self.nav[cy][cx]:
                return cx, cy
            # célula andável mais próxima
            return min(self.nav_cells, key=lambda c: (c[0] - cx) ** 2 + (c[1] - cy) ** 2)

        s, g = cell_of(start), cell_of(goal)
        prev = {s: None}
        q = deque([s])
        while q:
            cur = q.popleft()
            if cur == g:
                break
            cx, cy = cur
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                nx, ny = cx + dx, cy + dy
                if not (0 <= nx < self.nav_w and 0 <= ny < self.nav_h) or (nx, ny) in prev:
                    continue
                if not self.nav[ny][nx] or (dx and dy and not (self.nav[cy][nx] and self.nav[ny][cx])):
                    continue
                prev[(nx, ny)] = cur
                q.append((nx, ny))
        if g not in prev:
            return []
        cells = []
        cur = g
        while cur is not None:
            cells.append(cur)
            cur = prev[cur]
        pts = [self._cell_center(*c) for c in reversed(cells)][1:] + [goal]
        # simplifica: pula pontos enquanto der para ir reto
        path, here = [], start
        i = 0
        while i < len(pts):
            j = len(pts) - 1
            while j > i and not self.clear_line(here, pts[j]):
                j -= 1
            path.append(pts[j])
            here = pts[j]
            i = j + 1
        return path

    @property
    def benches(self):
        return [p for p in self.props if p.kind == "bench"]

    def shade_at(self, x: float, y: float) -> float:
        """Luz no ponto (1 = sol, <1 = sombra de algum objeto)."""
        return min((p.shade_at(x, y) for p in self.props), default=1.0)
