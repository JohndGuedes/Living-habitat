"""A Sombra: aparição ocasional, só à NOITE ou durante CHUVA.

- De tempos em tempos (CHECK_EVERY), se for noite ou estiver chovendo, há uma
  chance (CHANCE) de ela surgir num ponto longe de todo mundo.
- Ela aparece aos poucos, flutua (sobe e desce, deriva devagar, olha para quem
  estiver mais perto) por alguns segundos e some.
- Se alguém chegar perto demais, ela some mais rápido.
- Quando surge, avisa os moradores (brain.react_shade): o Knight fica curioso,
  a Hornet desconfiada, o Grub se esconde na terra.
- Tecla G: chama a Sombra na hora (para testar).

É desenhada depois da luz da noite (não escurece) — preta com olhos brancos.
"""
import math
import random

import pygame

from .assets import load_sprite_set
from .sprite_defs import CHARACTER_SPRITES

CHECK_EVERY = (150, 300)    # segundos entre tentativas
CHANCE = 0.5                # chance de aparecer em cada tentativa
STAY = (25, 50)             # quanto tempo fica (segundos)
FADE = 2.5                  # segundos para aparecer/sumir
SCARE_DIST = 110            # alguém chegou perto assim -> some


class Shade:
    def __init__(self, world, env, characters, seed=None):
        self.world, self.env, self.characters = world, env, characters
        self.rng = random.Random(seed)
        self.sheet = load_sprite_set(CHARACTER_SPRITES["shade"]).get("idle")
        self.x = self.y = 0.0
        self.alpha = 0.0           # 0..1
        self.visible = False       # está em cena (aparecendo, parada ou sumindo)
        self.leaving = False
        self.scared = False
        self.left = 0.0           # tempo restante em cena
        self.time = 0.0
        self.facing = "left"
        self.drift = (0.0, 0.0)
        self.timer = self.rng.uniform(40, 90)   # primeira tentativa
        self._appeared = False                  # aviso pendente para os moradores

    def pop_appeared(self) -> bool:
        """True uma única vez depois que ela surge (para os moradores reagirem)."""
        hit, self._appeared = self._appeared, False
        return hit

    def eligible(self) -> bool:
        return self.env.phase == "Noite" or self.env.rain > 0.3

    def _spot(self):
        best, best_d = None, -1
        for _ in range(30):
            x, y = self.world.random_point(self.rng)
            near_prop = any(math.hypot(p.x - x, p.y - y) < 130 for p in self.world.props)
            d = min((math.hypot(c.x - x, c.y - y) for c in self.characters), default=999)
            if not near_prop and d > best_d:
                best, best_d = (x, y), d
        return best or self.world.random_point(self.rng)

    def appear(self):
        if self.sheet is None or self.visible:
            return
        self.x, self.y = self._spot()
        self.visible, self.leaving, self.scared = True, False, False
        self.left = self.rng.uniform(*STAY)
        self.drift = (self.rng.uniform(-8, 8), self.rng.uniform(-3, 3))
        self._appeared = True

    def update(self, dt):
        self.time += dt
        if not self.visible:
            if self.eligible():
                self.timer -= dt
                if self.timer <= 0:
                    self.timer = self.rng.uniform(*CHECK_EVERY)
                    if self.rng.random() < CHANCE:
                        self.appear()
            return

        near = min(self.characters, key=lambda c: math.hypot(c.x - self.x, c.y - self.y), default=None)
        if near is not None:
            self.facing = "right" if near.x > self.x else "left"
            if math.hypot(near.x - self.x, near.y - self.y) < SCARE_DIST and not self.leaving:
                self.leaving, self.scared = True, True    # chegou perto: some depressa
        self.left -= dt
        if self.left <= 0:
            self.leaving = True
        # deriva devagar (só por onde dá para andar; bateu na borda, volta)
        nx, ny = self.x + self.drift[0] * dt, self.y + self.drift[1] * dt
        if self.world.walkable(pygame.Rect(round(nx - 14), round(ny - 8), 28, 10)):
            self.x, self.y = nx, ny
        else:
            self.drift = (-self.drift[0], -self.drift[1])
        speed = (2.5 if self.scared else 1.0) / FADE
        self.alpha += (-speed if self.leaving else speed) * dt
        self.alpha = max(0.0, min(1.0, self.alpha))
        if self.leaving and self.alpha <= 0:
            self.visible = False

    def draw(self, surface):
        if not self.visible or self.alpha <= 0 or self.sheet is None:
            return
        bob = math.sin(self.time * 1.8) * 6 + 10      # flutua acima do chão
        frame = self.sheet.frame_at(self.time)
        self.sheet.draw(surface, frame, self.facing, self.x, self.y, self.facing, lift=bob,
                        alpha=round(255 * self.alpha))
