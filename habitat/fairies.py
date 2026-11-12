'''Fadinhas: bichinhos de fundo que deixam o mundo mais vivo.

Arte: assets/sprites/world/fairies/fadinhas.png (8 quadros batendo as asas, em células
com moldura azul; por dentro a folha já é transparente: a fadinha branca com o halo).

Grupos ("swarms", scene.py "fairies"). Passam a MAIOR PARTE do tempo paradas:
  - descansando ("rest") 20-60 s num lugar: sentadas na copa das árvores, no encosto do
    banco, em cima de postes/pilares/boneco (cada uma num cantinho do objeto), batendo
    as asas devagar; ou pairando paradas no ar;
  - de vez em quando voam ("fly") devagar para outro lugar, passando por cima de tudo.
Cada fadinha tem posição e velocidade próprias e é puxada para o seu lugar no grupo:
  - se alguém passa perto, ela DEBANDA (foge para longe do personagem) e depois de um
    tempinho volta e o grupo se reúne de novo;
  - se um personagem fica PARADO uns segundos perto, às vezes uma fadinha curiosa sai do
    grupo e vai rodear a cabeça dele; se ele se mexer, ela foge de volta.

Desenho: draw() depois de todos os objetos (escurecem à noite junto com a cena) e
draw_light() depois do escurecimento: brilho azulado, quase nada de dia, forte à noite.
'''
import math
import random

import pygame

from .config import CHARACTER_SCALE, SPRITES_DIR

SHEET = SPRITES_DIR / "world" / "fairies" / "fadinhas.png"
FRAME_TIME = 0.07         # asas voando
REST_FRAME_TIME = 0.22    # asas descansando (mais devagar)
_FRAMES = None


def _load_frames(scale):
    """Células da folha (transparentes por dentro) recortadas e escaladas."""
    global _FRAMES
    if _FRAMES is not None and _FRAMES[0] == scale:
        return _FRAMES[1]
    if not SHEET.exists():
        _FRAMES = (scale, [])
        return []
    sheet = pygame.image.load(str(SHEET)).convert_alpha()      # (convert() perde o alpha)
    border = sheet.get_at((0, 0))
    m = pygame.mask.from_threshold(sheet, border, (12, 12, 12, 255))
    m.invert()
    cells = sorted((r for r in m.get_bounding_rects() if r.w > 50 and r.h > 50), key=lambda r: (r.y // 40, r.x))
    frames = []
    for r in cells:
        cw, ch = r.size
        side = min(cw, ch) - 16                       # sem as bordas da célula
        inner = pygame.Rect(r.x + (cw - side) // 2, r.y + (ch - side) // 2, side, side)
        frames.append(pygame.transform.smoothscale_by(sheet.subsurface(inner).copy(), scale))
    _FRAMES = (scale, frames)
    return frames


def _soft(radius, color):
    s = pygame.Surface((radius * 2, radius * 2))
    for r in range(radius, 0, -1):
        k = math.exp(-3.0 * (r / radius) ** 2)
        pygame.draw.circle(s, [round(c * k) for c in color], (radius, radius), r)
    return s


class Fairy:
    def __init__(self, rng, x, y):
        self.x, self.y = x, y
        self.vx = self.vy = 0.0
        self.sx = self.sy = 0.0          # lugar no grupo (relativo ao centro / ao objeto)
        self.a = rng.uniform(0, 6.3)     # fase do giro / bob
        self.w = rng.uniform(0.6, 1.4) * rng.choice((-1, 1))
        self.ft = rng.uniform(0, 8)      # atraso das asas
        self.scatter = 0.0               # > 0: debandando (fugindo)
        self.visit = None                # [personagem, segundos]: fadinha curiosa
        self.resting = False


class Swarm:
    FLY_SPEED = (18, 30)      # px/s do centro do grupo voando
    REST = (20, 60)           # s descansando num lugar
    SCARE = 34                # px: alguém mais perto debanda a fadinha
    SCATTER = (1.2, 2.4)      # s fugindo antes de voltar

    def __init__(self, world, rng, size, scale):
        self.world, self.rng = world, rng
        self.frames = _load_frames(scale)
        self.t = rng.uniform(0, 100)
        self.cx, self.cy = self._random_point()
        self.state = "rest"
        self.timer = rng.uniform(*self.REST)
        self.spot = None                  # (x, y, largura) do objeto onde estão sentadas
        self.fairies = [Fairy(rng, self.cx, self.cy) for _ in range(size)]
        self._choose_rest()
        self.cx, self.cy = self.tx, self.ty          # já começam sentadas no lugar
        for f in self.fairies:
            f.x, f.y = self.cx + f.sx, self.cy + f.sy

    # ---------- lugares ----------
    def _random_point(self):
        w = self.world
        gx, gy = w.ground_pos
        gw, gh = w.ground.get_size()
        return self.rng.uniform(gx + gw * 0.12, gx + gw * 0.88), self.rng.uniform(gy + gh * 0.15, gy + gh * 0.8)

    def _perches(self):
        """Lugares para sentar: (x, y do topo, largura) de árvores, banco, postes, boneco..."""
        out = []
        for p in self.world.props:
            img = p.image() if hasattr(p, "image") else p.frames[0]
            w, h = img.get_size()
            top = p.y + p.base_offset - h
            name = str(p.defn.get("name", ""))
            if p.kind == "fruit_tree" or "pinheiro" in name or "arvore" in name:
                out.append((p.x, top + h * 0.3, w * 0.55))              # copa
            elif p.kind == "bench":
                out.append((p.x, top + h * 0.12, w * 0.7))              # encosto
            elif getattr(p, "lamps", None):
                lx, ly = p.lamps[0]
                out.append((lx, ly - h * 0.08, w * 0.3))                # em cima da lanterna
            elif p.kind == "zote" and not getattr(p, "destroyed", False):
                out.append((p.x, top + h * 0.12, w * 0.35))             # cabeça do boneco
            elif p.kind == "item" and h > 25:
                out.append((p.x, top + h * 0.1, w * 0.5))               # topo de pedras, pilares...
        return out

    def _choose_rest(self):
        perches = self._perches()
        if perches and self.rng.random() < 0.75:
            self.spot = self.rng.choice(perches)
        else:
            x, y = self._random_point()
            self.spot = (x, y, 0)                                        # pairando no ar
        # cada fadinha num cantinho do lugar
        x, y, w = self.spot
        for f in self.fairies:
            if w > 0:
                f.sx, f.sy = self.rng.uniform(-w / 2, w / 2), self.rng.uniform(-w * 0.12, w * 0.12)
            else:
                ang = self.rng.uniform(0, 6.3)
                r = self.rng.uniform(4, 14)
                f.sx, f.sy = math.cos(ang) * r, math.sin(ang) * r * 0.5
        self.tx, self.ty = x, y

    # ---------- por quadro ----------
    def update(self, dt, actors, still):
        self.t += dt
        if self.state == "rest":
            self.timer -= dt
            if self.timer <= 0:                       # hora de ir para outro lugar
                self.state = "fly"
                self._choose_rest()
                self.speed = self.rng.uniform(*self.FLY_SPEED)
        if self.state == "fly":
            dx, dy = self.tx - self.cx, self.ty - self.cy
            d = math.hypot(dx, dy)
            if d < 3:
                self.state = "rest"
                self.timer = self.rng.uniform(*self.REST)
            else:
                step = min(d, self.speed * dt)
                self.cx += dx / d * step
                self.cy += dy / d * step + math.sin(self.t * 2) * 6 * dt
        resting = self.state == "rest"
        head = 70 * CHARACTER_SCALE
        for f in self.fairies:
            f.a += f.w * dt
            f.resting = resting and f.scatter <= 0 and f.visit is None
            # alguém passou perto: debanda (foge para longe)
            for a in actors:
                ax, ay = a.x, a.y - head * 0.5
                dd = math.hypot(f.x - ax, f.y - ay)
                if dd < self.SCARE and (f.visit is None or f.visit[0] is not a) and f.scatter <= 0:
                    ux, uy = ((f.x - ax) / dd, (f.y - ay) / dd) if dd > 0.1 else (self.rng.uniform(-1, 1), -1)
                    f.vx, f.vy = ux * self.rng.uniform(70, 110), uy * self.rng.uniform(50, 90) - 30
                    f.scatter = self.rng.uniform(*self.SCATTER)
            # fadinha curiosa: o personagem se mexeu -> foge de volta
            if f.visit:
                a = f.visit[0]
                f.visit[1] -= dt
                moved = still.get(id(a), 0) < 0.5
                if f.visit[1] <= 0 or moved:
                    f.visit = None
                    if moved:                            # susto: sai voando antes de voltar
                        f.vx, f.vy = self.rng.uniform(-60, 60), -60
                        f.scatter = self.rng.uniform(0.6, 1.2)
            # alvo: o lugar no grupo, ou a cabeça do personagem (curiosa)
            if f.visit:
                a = f.visit[0]
                tx = a.x + math.cos(f.a * 2) * 14
                ty = a.y - head - 10 + math.sin(f.a * 3) * 5
            else:
                bob = 1.5 if f.resting else 3.0
                tx = self.cx + f.sx + (math.cos(f.a) * 2 if f.resting else math.cos(f.a) * 6)
                ty = self.cy + f.sy + math.sin(self.t * 2 + f.ft) * bob
            if f.scatter > 0:                        # fugindo: segue o impulso, freando
                f.scatter -= dt
                f.vx *= 0.96
                f.vy *= 0.96
            else:                                    # mola até o alvo (se reúnem de novo)
                k, damp = (14.0, 6.0) if (f.resting or f.visit) else (9.0, 4.5)
                f.vx += ((tx - f.x) * k - f.vx * damp) * dt
                f.vy += ((ty - f.y) * k - f.vy * damp) * dt
            f.x += f.vx * dt
            f.y += f.vy * dt

    def free_fairy(self):
        free = [f for f in self.fairies if f.visit is None and f.scatter <= 0]
        return self.rng.choice(free) if free and len(free) > 1 else None

    def draw(self, surface):
        if not self.frames:
            return
        n = len(self.frames)
        for f in self.fairies:
            ft = REST_FRAME_TIME if f.resting else FRAME_TIME
            img = self.frames[int(self.t / ft + f.ft) % n]
            surface.blit(img, img.get_rect(center=(round(f.x), round(f.y))))

    def draw_light(self, surface, g):
        for f in self.fairies:
            surface.blit(g, g.get_rect(center=(round(f.x), round(f.y))), special_flags=pygame.BLEND_ADD)


class Fairies:
    """Todos os grupos de uma área ("fairies" em scene.py: swarms, size, scale)."""
    CURIOUS_AFTER = 4.0       # s parado para uma fadinha vir ver
    CURIOUS_RANGE = 220       # px até o grupo

    def __init__(self, world, spec, seed=0):
        self.rng = random.Random(seed + 99)
        self.swarms = [Swarm(world, self.rng, self.rng.randint(*spec.get("size", (3, 6))), spec.get("scale", 0.3))
                       for _ in range(spec.get("swarms", 0))]
        self._glow = _soft(8, (150, 190, 235))
        self._levels = {}            # força (12 degraus) -> brilho já escurecido
        self.still = {}              # id(personagem) -> segundos parado
        self._last = {}

    def update(self, dt, actors=()):
        actors = list(actors)
        for a in actors:             # quanto tempo cada um está parado
            last = self._last.get(id(a))
            moved = last is None or math.hypot(a.x - last[0], a.y - last[1]) > 0.5
            self.still[id(a)] = 0.0 if moved else self.still.get(id(a), 0.0) + dt
            self._last[id(a)] = (a.x, a.y)
        for s in self.swarms:
            s.update(dt, actors, self.still)
        # alguém parado faz tempo, perto de um grupo: às vezes uma fadinha curiosa vai ver
        for a in actors:
            if self.still.get(id(a), 0) < self.CURIOUS_AFTER or self.rng.random() > dt * 0.25:
                continue
            if any(f.visit and f.visit[0] is a for s in self.swarms for f in s.fairies):
                continue
            near = [s for s in self.swarms if math.hypot(s.cx - a.x, s.cy - a.y) < self.CURIOUS_RANGE]
            if near:
                f = self.rng.choice(near).free_fairy()
                if f:
                    f.visit = [a, self.rng.uniform(5, 10)]

    def draw(self, surface):
        for s in self.swarms:
            s.draw(surface)

    def draw_light(self, surface, darkness):
        night = max(0.0, min(1.0, (darkness - 0.1) / 0.6))
        level = round(12 * (0.12 + 0.55 * night))   # de dia quase nada, à noite brilham
        if level <= 0:
            return
        g = self._levels.get(level)
        if g is None:
            g = self._glow.copy()
            v = round(255 * level / 12)
            g.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
            self._levels[level] = g
        for s in self.swarms:
            s.draw_light(surface, g)
            if night > 0.5:                          # à noite a fadinha em si fica mais clara
                s.draw(surface)
