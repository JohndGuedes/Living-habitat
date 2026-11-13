"""Uma área do minimundo: uma ilha flutuante (chão) + objetos (props.py),
como descrito em scene.AREAS.

Arquivos da área (assets/sprites/world/areas/<nome>/, gerados por tools/make_areas.py):
  ground.png    a ilha;  walkable.png  onde dá para andar (branco);
  water.png     o lago (onde dá para nadar);  meta.json  florzinhas (comida).
Os mapas são esticados sobre a ilha e podem ser retocados à mão.
"""
import datetime
import json
import logging
from collections import deque

import pygame

from .config import NATAL_MONTHS, ROOT, SEASON, SPRITES_DIR
from .decor import scatter
from .effects import make_effect
from .fairies import Fairies
from .lighting import SceneLights
from .props import make_prop
from .scene import AREAS, DECOR, DECOR_SCALE, DECOR_SEED, DECOR_SOLID

log = logging.getLogger(__name__)

# Posição/tamanho dos objetos salvos pelo editor (tecla O); valem por cima de scene.py
LAYOUT_FILE = ROOT / "layout.json"


def layout_key(area, season):
    return f"{area}@{season}"


def load_layout(area, defs, season=None):
    """Objetos da área: o que o editor salvou em layout.json (para esta estação, ou o da
    área sem estação), senão os de scene.py. Entradas antigas (só posição/tamanho) são
    completadas com o objeto de mesmo tipo e posição na lista de scene.py."""
    defs = [dict(d) for d in defs]
    if not LAYOUT_FILE.exists():
        return defs
    try:
        data = json.loads(LAYOUT_FILE.read_text(encoding="utf-8"))
    except ValueError:
        log.warning("layout.json inválido: usando scene.py")
        return defs
    saved = data.get(layout_key(area, season)) if season else None
    if saved is None:
        saved = data.get(area)
    if saved is None:
        return defs
    out = []
    for i, s in enumerate(saved):
        base = defs[i] if i < len(defs) and defs[i]["kind"] == s.get("kind") else {}
        d = {**base, **s}
        if "img_pos" not in d or "kind" not in d:
            continue
        d["img_pos"] = tuple(d["img_pos"])
        for key in ("seats", "seats_rel", "footprint"):
            if isinstance(d.get(key), list) and key == "footprint":
                d[key] = tuple(d[key])
        out.append(d)
    return out


class FoodSpot:
    """Florzinha brilhante desenhada na ilha: serve de comida (t_eat)."""
    kind = "flor_ilha"

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.rustle = 0.0
SKY_TOP = (118, 168, 210)
SKY_BOTTOM = (176, 210, 228)


def current_season(override=None):
    """"natal" em novembro/dezembro (ou o que estiver fixado em config.SEASON)."""
    season = override or SEASON
    if season:
        return season
    return "natal" if datetime.date.today().month in NATAL_MONTHS else "normal"


class World:
    def __init__(self, width: int, height: int, area: str, margin: int = 16, season=None):
        self.width, self.height = width, height
        self.name = area
        # época: "natal" pode trocar o mapa inteiro (scene "seasons") ou usar ground_natal.png
        self.season = current_season(season)
        spec = AREAS[area]
        self.spec = {**spec, **spec.get("seasons", {}).get(self.season, {})}
        self.indoor = bool(self.spec.get("indoor", False))
        self.folder = SPRITES_DIR / self.spec["folder"]
        self.frozen = self.season == "natal" and (self.folder / "walkable_frozen.png").exists()
        self.background = self._sky()
        self.ground, self.ground_pos, self.walk_mask = self._load_ground(margin)
        self.lake_mask = self._load_water()
        # congelado: não dá para nadar (o lago continua sendo lago para beber na beira)
        self.water_mask = pygame.mask.Mask(self.lake_mask.get_size()) if self.frozen else self.lake_mask
        # objetos: scene.py, com o que o editor salvou em layout.json por cima
        self.prop_defs = load_layout(area, self.spec.get("props", []), self.season)
        self.props = [make_prop(self._place(d)) for d in self.prop_defs]
        self.fruits = []             # frutas caídas das árvores (props.Fruit)
        self.wind, self.actors = 1.0, ()   # atualizados em update (balanço das plantas)
        for p in self.props:
            p.world = self
        self.spawn = self.to_screen(self.spec.get("spawn", (0, 0)))
        self.spawns = {k: self.to_screen(v) for k, v in self.spec.get("spawns", {}).items()}
        # saídas para outras áreas: [{"to", "at": (x, y), "arrive": (x, y) em px da imagem de lá}]
        self.exits = [
            dict(
                e,
                at=self.to_screen(e["at"]),
                **({"return_pos": self.to_screen(e["return_at"])} if "return_at" in e else {}),
            )
            for e in self.spec.get("exits", [])
        ]
        # luzes (pisca-pisca, porta, lanternas...) e brilho no gelo (lighting.py)
        self.lights = SceneLights(self, self.spec.get("lighting", {}))
        # fadinhas voando em grupinhos (fairies.py)
        self.fairies = Fairies(self, self.spec.get("fairies", {}))
        self._lake_surface = None
        # efeitos animados por cima do chão (ex.: a água da cachoeira correndo)
        self.effects = [make_effect(self, e, seed=i) for i, e in enumerate(self.spec.get("effects", []))]
        # pulos (ex.: por cima da cachoeira): pares de pontos de tela
        self.jumps = [(self.to_screen(a), self.to_screen(b)) for a, b in self.spec.get("jumps", [])]
        meta = self.folder / "meta.json"
        food = json.loads(meta.read_text(encoding="utf-8")).get("food", []) if meta.exists() else []
        self.food_spots = [FoodSpot(*self.to_screen(p)) for p in food]
        # plantas animadas (deixa livre a área onde o personagem nasce)
        self.decor = scatter(self, DECOR.get(area, {}), DECOR_SCALE, DECOR_SOLID,
                             keep_clear=[(*self.spawn, 70)] + [(p.x, p.y, 95) for p in self.props],
                             seed=DECOR_SEED)

    def to_screen(self, p):
        """px da imagem ground.png -> px de tela."""
        return (self.ground_pos[0] + p[0] * self.k, self.ground_pos[1] + p[1] * self.k)

    def _place(self, d):
        """Objeto de scene: "img_pos" -> "pos" de tela; "scale" relativa à ilha."""
        d = dict(d)
        if "img_pos" in d:
            d["pos"] = self.to_screen(d.pop("img_pos"))
        d["scale"] = d.get("scale", 1) * self.k
        return d

    # ---------- montagem ----------
    def _sky(self) -> pygame.Surface:
        s = pygame.Surface((self.width, self.height))
        top = (14, 16, 26) if self.indoor else SKY_TOP
        bot = (24, 26, 38) if self.indoor else SKY_BOTTOM
        for y in range(self.height):
            t = y / (self.height - 1)
            s.fill([round(a + (b - a) * t) for a, b in zip(top, bot)], (0, y, self.width, 1))
        return s

    def _load_ground(self, margin):
        """Ilha escalada para caber na tela (centralizada; "top_room" reserva espaço
        em cima, ex.: a caverna) + máscara andável."""
        path = self.folder / "ground.png"
        variant = self.folder / f"ground_{self.season}.png"   # ex.: natal (pode ter outra resolução)
        if not path.exists():
            log.warning("sem %s — rode tools/make_areas.py. Usando chão liso.", path)
            img = pygame.Surface((self.width - 2 * margin, self.height - 2 * margin))
            img.fill((60, 100, 95))
            mask = pygame.mask.Mask(img.get_size(), fill=True)
            self.k = 1.0
            return img, (margin, margin), mask

        img = pygame.image.load(path).convert_alpha()
        room = self.spec.get("top_room", 0)
        k = min((self.width - 2 * margin) / img.get_width(),
                (self.height - 2 * margin) / (img.get_height() + room))
        self.k = k                       # posições de scene.py = px de ground.png
        size = (round(img.get_width() * k), round(img.get_height() * k))
        if variant.exists():             # mesma ilha, mesma posição: estica para o mesmo tamanho
            img = pygame.image.load(variant).convert_alpha()
        img = pygame.transform.smoothscale(img, size)
        total = img.get_height() + room * k
        pos = ((self.width - img.get_width()) // 2, round((self.height - total) / 2 + room * k))

        wpath = self.folder / ("walkable_frozen.png" if self.frozen else "walkable.png")
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
        self.wind, self.actors = wind, actors     # lidos pelas plantas que balançam
        for p in self.props:
            p.update(dt)
        for e in self.effects:
            e.update(dt)
        self.lights.update(dt)
        self.fairies.update(dt, actors)
        for f in self.fruits:
            f.update(dt)
        self.fruits = [f for f in self.fruits if not f.eaten and f.age < 600]
        for d in self.decor:
            d.update(dt, wind, actors)

    @property
    def drawables(self) -> list:
        """Tudo que é desenhado ordenado por profundidade (junto do personagem)."""
        return self.props + self.decor + self.fruits

    def draw(self, surface: pygame.Surface):
        """Céu + ilha + camada de chão dos objetos (sombras). Objetos e personagem
        são desenhados depois, ordenados por y (veja Game.step)."""
        surface.blit(self.background, (0, 0))
        surface.blit(self.ground, self.ground_pos)
        for e in self.effects:                 # água correndo etc. (personagens passam na frente)
            e.draw(surface)
        for p in self.props:
            p.draw_ground(surface)

    def draw_lights(self, surface: pygame.Surface, darkness: float = 0.0):
        self.lights.draw(surface, darkness)
        self.fairies.draw_light(surface, darkness)
        for p in self.props:
            p.draw_light(surface, darkness)

    def lake_surface(self):
        """(retângulo na tela, máscara branca do lago) para recortar reflexos e brilhos, ou None."""
        if self._lake_surface is None:
            m = self.lake_mask
            if not m.count():
                self._lake_surface = False
            else:
                box = m.get_bounding_rects()
                r = box[0].unionall(box[1:]) if len(box) > 1 else box[0]
                sub = pygame.mask.Mask(r.size)
                sub.draw(m, (-r.x, -r.y))
                surf = sub.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(255, 255, 255, 0))
                self._lake_surface = (r.move(self.ground_pos), surf)
        return self._lake_surface or None

    def on_lake(self, x, y, margin=6):
        """Os pés estão em cima do lago (gelo/água)?"""
        gx, gy = round(x - self.ground_pos[0]), round(y - self.ground_pos[1] + margin)
        w, h = self.lake_mask.get_size()
        return 0 <= gx < w and 0 <= gy < h and bool(self.lake_mask.get_at((gx, gy)))

    def draw_debug(self, surface: pygame.Surface):
        """Contorno da área andável (debug)."""
        ox, oy = self.ground_pos
        pts = self.walk_mask.outline(4)
        if len(pts) > 2:
            pygame.draw.lines(surface, (80, 220, 255), True, [(x + ox, y + oy) for x, y in pts], 2)
        for a, b in getattr(self, "jumps", []):                       # pulos (rosa)
            pygame.draw.line(surface, (255, 120, 220), a, b, 2)
            for p in (a, b):
                pygame.draw.circle(surface, (255, 120, 220), [round(v) for v in p], 10, 2)
        for e in self.exits:                                          # saídas (amarelo)
            pygame.draw.circle(surface, (255, 220, 60), [round(v) for v in e["at"]], 14, 2)
        for f in self.food_spots:                                    # comida (verde)
            pygame.draw.circle(surface, (120, 255, 140), (round(f.x), round(f.y)), 3)
        if getattr(self, "water_mask", None) is not None:            # onde dá para nadar
            wp = self.water_mask.outline(4)
            if len(wp) > 2:
                pygame.draw.lines(surface, (60, 120, 255), True, [(x + ox, y + oy) for x, y in wp], 2)

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
        self._build_water()
        # saídas e destinos caem em ponto andável e alcançável (a grade de navegação)
        for e in self.exits:
            e["at"] = self.nav_point(e["at"])
            if "return_pos" in e:
                e["return_pos"] = self.nav_point(e["return_pos"])
        self.jumps = [(self.nav_point(a), self.nav_point(b)) for a, b in self.jumps]

    def nav_point(self, p):
        """Centro da célula de navegação mais perto de `p`."""
        C = self.NAV_CELL
        cx, cy = p[0] // C, p[1] // C
        best = min(self.nav_cells, key=lambda c: (c[0] - cx) ** 2 + (c[1] - cy) ** 2)
        return self._cell_center(*best)

    # ---------- água (nadar) ----------
    def _load_water(self):
        """water.png (o lago, gerado por tools/make_areas.py) esticado sobre a ilha."""
        path = self.folder / "water.png"
        if not path.exists():
            return pygame.mask.Mask(self.ground.get_size())
        img = pygame.image.load(path).convert()
        mask = pygame.mask.from_threshold(img, (255, 255, 255), (60, 60, 60, 255))
        return mask.scale(self.ground.get_size())

    def _build_water(self):
        """Pontos de nado (`water_cells`), depois que a navegação existe."""
        C = self.NAV_CELL
        self.water_cells = [(x, y) for y in range(C // 2, self.height, C) for x in range(C // 2, self.width, C)
                            if self.swimmable(self._foot_at(x, y))]

    def swimmable(self, rect: pygame.Rect) -> bool:
        """Dá para nadar aqui? (pés + uma margem inteiros dentro do lago)"""
        if not hasattr(self, "water_mask"):
            return False
        r = rect.inflate(24, 14)
        ox, oy = self.ground_pos
        foot = pygame.mask.Mask(r.size, fill=True)
        return self.water_mask.overlap_area(foot, (r.x - ox, r.y - oy)) == r.w * r.h

    def water_point(self, rng, near=None, radius=None):
        cells = self.water_cells
        if near is not None and radius:
            close = [c for c in cells if (c[0] - near[0]) ** 2 + (c[1] - near[1]) ** 2 <= radius * radius]
            cells = close or cells
        return rng.choice(cells) if cells else None

    def clear_water(self, a, b) -> bool:
        """Dá para nadar em linha reta de a até b?"""
        (x0, y0), (x1, y1) = a, b
        steps = max(1, int(max(abs(x1 - x0), abs(y1 - y0)) / 8))
        return all(self.swimmable(self._foot_at(x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps))
                   for i in range(steps + 1))

    def _solid_hit(self, rect):
        return any(p.solid is not None and p.solid.colliderect(rect) for p in self.props + self.decor)

    def _cell_center(self, cx, cy):
        C = self.NAV_CELL
        return cx * C + C / 2, cy * C + C / 2

    def _is_water(self, x, y) -> bool:
        gx, gy = round(x - self.ground_pos[0]), round(y - self.ground_pos[1])
        if not (0 <= gx < self.ground.get_width() and 0 <= gy < self.ground.get_height()):
            return False
        return bool(self.lake_mask.get_at((gx, gy)))

    def _find_shore(self):
        """Pontos andáveis com água logo ao lado (esquerda/direita): onde ele bebe.
        Retorna [(x, y, lado_da_agua)]."""
        out = []
        for cx, cy in self.nav_cells:
            x, y = self._cell_center(cx, cy)
            for side, sx in (("right", 1), ("left", -1)):
                if any(self._is_water(x + sx * d, y + dy) for d in (30, 42, 54, 66, 78) for dy in (-6, -14)):
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
    def dummies(self):
        return [p for p in self.props if p.kind == "zote"]

    @property
    def snowmen(self):
        return [p for p in self.props if p.kind == "snowman"]

    @property
    def campfires(self):
        return [p for p in self.props if p.kind == "campfire"]

    @property
    def grubs_natal(self):
        return [p for p in self.props if p.kind == "grub_natal"]

    @property
    def fruit_trees(self):
        return [p for p in self.props if p.kind == "fruit_tree"]

    @property
    def benches(self):
        return [p for p in self.props if p.kind == "bench"]

    @property
    def beds(self):
        return [p for p in self.props if p.kind == "bed"]

    @property
    def caves(self):
        return [p for p in self.props if p.kind == "cave"]

    def ice_point(self, rng):
        """Ponto andável em cima do lago congelado (para patinar), ou None."""
        if not self.frozen:
            return None
        cells = [c for c in self.nav_cells if self._is_water(*self._cell_center(*c))]
        return self._cell_center(*rng.choice(cells)) if cells else None

    def exit_to(self, area):
        return next((e for e in self.exits if e["to"] == area), None)

    def shade_at(self, x: float, y: float) -> float:
        """Luz no ponto (1 = sol, <1 = sombra de algum objeto)."""
        return min((p.shade_at(x, y) for p in self.props), default=1.0)
