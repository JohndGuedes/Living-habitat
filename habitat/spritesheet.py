"""Animações: quadros (por direção) e controle de tempo."""
import logging

import pygame

log = logging.getLogger(__name__)

DIRECTIONS_8 = ["down", "down_right", "right", "up_right", "up", "up_left", "left", "down_left"]
DIRECTIONS_4 = ["down", "left", "right", "up"]


def dir_from_vector(x: int, y: int) -> str:
    """Converte um vetor (-1/0/1) em nome de direção, ex.: (1, -1) -> 'up_right'."""
    v = "up" if y < 0 else "down" if y > 0 else ""
    h = "left" if x < 0 else "right" if x > 0 else ""
    if v and h:
        return f"{v}_{h}"
    return v or h or "down"


class SpriteSheet:
    """Uma animação. `cells[linha][quadro]`, uma linha por direção.

    Opções (vêm de sprite_defs.py):
      frame_duration  segundos por quadro
      loop            False = toca uma vez; ao terminar o personagem vai para `next`
      next            animação seguinte quando loop=False (padrão: "idle")
      hop             altura (px) de um pulo em arco desenhado durante a animação
      hit_frame       quadro em que um ataque acerta (gera o evento de golpe)
      art_faces       vista lateral: lado para onde a arte olha ('left'/'right');
                      o outro lado é espelhado
      anchor          (ax, ay) ponto do quadro que fica sobre os pés do personagem;
                      None = centro da base do quadro
    """

    def __init__(self, cells: list[list[pygame.Surface]], name: str, frame_duration: float = 0.12,
                 loop: bool = True, next_state: str = "idle", hop: float = 0,
                 hit_frame: int | None = None,
                 art_faces: str | None = None, anchor: tuple[float, float] | None = None,
                 direction_order: list[str] | None = None, source_size=None):
        self.name = name
        self.cells = cells
        self.rows = len(cells)
        self.frames = len(cells[0])
        self.frame_duration = frame_duration
        self.loop = loop
        self.next_state = next_state
        self.hop = hop
        self.hit_frame = hit_frame  # quadro em que o golpe "acerta" (ataques)
        self.art_faces = art_faces
        self.fw, self.fh = cells[0][0].get_size()
        self.anchor = anchor if anchor is not None else (self.fw / 2, self.fh)
        self.image_size = source_size or (self.fw * self.frames, self.fh * self.rows)
        if direction_order is None:
            direction_order = {8: DIRECTIONS_8, 4: DIRECTIONS_4}.get(self.rows)
        self.direction_order = direction_order
        self.flipped = ([[pygame.transform.flip(c, True, False) for c in row] for row in cells]
                        if art_faces else None)
        self.glow = None     # [(x, y) da luz em cada quadro (lanterna), em px do quadro] ou None
        self.effect = None   # efeito desenhado por cima (golpes): veja assets._attach_effect

    @classmethod
    def from_grid(cls, image: pygame.Surface, name: str, frames: int, rows: int = 1,
                  scale: float = 1, offset_y: int = 0, **kw):
        """Corta uma imagem em grade (colunas = quadros, linhas = direções)."""
        w, h = image.get_size()
        if w % frames or h % rows:
            log.warning("sprite '%s': %dx%d não divide em %d frames x %d rows — "
                        "confira habitat/sprite_defs.py", name, w, h, frames, rows)
        fw, fh = w // frames, h // rows
        cells = [[_scale(image.subsurface((c * fw, r * fh, fw, fh)), scale) for c in range(frames)]
                 for r in range(rows)]
        sw, sh = cells[0][0].get_size()
        return cls(cells, name, anchor=(sw / 2, sh - offset_y * scale), source_size=(w, h), **kw)

    @property
    def duration(self) -> float:
        return self.frames * self.frame_duration

    def row_for(self, direction: str) -> int:
        if not self.direction_order:
            return 0
        if direction in self.direction_order:
            return self.direction_order.index(direction)
        # Folha sem diagonais: usa o lado (left/right)
        side = direction.split("_")[-1]
        return self.direction_order.index(side) if side in self.direction_order else 0

    def frame_at(self, time: float) -> int:
        f = int(time / self.frame_duration)
        return f % self.frames if self.loop else min(f, self.frames - 1)

    def lift_at(self, time: float) -> float:
        """Altura do pulo (arco) no instante `time`."""
        if not self.hop:
            return 0.0
        t = min(1.0, time / self.duration)
        return self.hop * 4 * t * (1 - t)

    def frame_image(self, frame: int, direction: str, facing: str = "right"):
        """(imagem, ax, ay): o quadro já virado para o lado certo e onde ficam os pés nele."""
        cells, ax = self.cells, self.anchor[0]
        if self.art_faces:
            side = "right" if "right" in direction else "left" if "left" in direction else facing
            if side != self.art_faces:
                cells, ax = self.flipped, self.fw - ax
        return cells[self.row_for(direction)][frame], ax, self.anchor[1]

    def draw(self, surface: pygame.Surface, frame: int, direction: str, x: float, y: float,
             facing: str = "right", lift: float = 0, tint: float = 1.0, alpha: int = 255):
        """(x, y) = pés do personagem. `facing` = último lado horizontal, usado
        por animações de vista lateral quando a direção é só cima/baixo.
        `alpha` < 255 = meio transparente (ex.: a Sombra aparecendo)."""
        cells, ax = self.cells, self.anchor[0]
        if self.art_faces:
            side = "right" if "right" in direction else "left" if "left" in direction else facing
            if side != self.art_faces:
                cells, ax = self.flipped, self.fw - ax
        img = cells[self.row_for(direction)][frame]
        if tint < 1:  # escurece (ex.: na sombra da árvore), mantendo a transparência
            img = img.copy()
            v = round(255 * tint)
            img.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
        if alpha < 255:
            img = img.copy()
            img.set_alpha(max(0, alpha))
        surface.blit(img, (round(x - ax), round(y - self.anchor[1] - lift)))


def _scale(img: pygame.Surface, scale: float) -> pygame.Surface:
    if scale == 1:
        return img
    if float(scale).is_integer():  # pixel art: vizinho mais próximo
        return pygame.transform.scale_by(img, scale)
    return pygame.transform.smoothscale_by(img, scale)  # arte HD: suavizado


class Animator:
    """Guarda qual animação está tocando e há quanto tempo."""

    def __init__(self):
        self.name: str | None = None
        self.time = 0.0

    def play(self, name: str | None):
        if name != self.name:
            self.name = name
            self.time = 0.0

    def update(self, dt: float):
        self.time += dt
