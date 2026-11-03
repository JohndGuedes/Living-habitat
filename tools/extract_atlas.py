"""Tira quadros escolhidos de atlas compactados do jogo para pastas de frames.

Rode:  .venv\\Scripts\\python tools\\extract_atlas.py

Os atlas do Hollow Knight/Silksong vêm compactados (quadros fora de ordem,
alguns girados, sem lista de onde está cada um). Aqui cada desenho é achado
como região conectada de pixels visíveis e escolhido pelo ÍNDICE: ordem de
cima para baixo em faixas de `band` px, depois da esquerda para a direita
(mesma numeração das prévias usadas para escolher).

Cada entrada de EXTRACTS: (atlas, alpha mínimo, área mínima, band, {pasta_saída: [índices]})
Caminhos relativos a assets/sprites/.
"""
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

SPRITES = Path(__file__).resolve().parent.parent / "assets" / "sprites"

EXTRACTS = [
    # Hornet no ar (salto)
    ("character/Hornet/Hornet jumping - atlas0 #92498.png", 30, 2000, 60,
     {"character/Hornet/frames/air": [0, 1]}),
    # Hornet sentada no banco (de frente, agulha no colo)
    ("character/Hornet/Hornet sitting - atlas0 #92576.png", 40, 2000, 80,
     {"character/Hornet/frames/bench_sit": [17, 18]}),
    # A Sombra flutuando (em pé, base esfiapada)
    ("character/NPCs/atlas0 #10777.png", 60, 3000, 80,
     {"character/Shade/frames/idle": [15, 16, 23, 24, 31, 51]}),
]


def components(atlas, alpha, min_area, band):
    mask = pygame.mask.from_surface(atlas, alpha)
    rects = [r for r in mask.get_bounding_rects() if r.w * r.h > min_area]
    return sorted(rects, key=lambda r: (r.y // band, r.x))


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    for atlas_path, alpha, area, band, outputs in EXTRACTS:
        atlas = pygame.image.load(str(SPRITES / atlas_path)).convert_alpha()
        rects = components(atlas, alpha, area, band)
        for out, idxs in outputs.items():
            folder = SPRITES / out
            folder.mkdir(parents=True, exist_ok=True)
            for old in folder.glob("*.png"):
                old.unlink()
            for n, i in enumerate(idxs):
                pygame.image.save(atlas.subsurface(rects[i]).copy(), str(folder / f"{n:03d}.png"))
            print(f"{out}: {len(idxs)} quadros")


if __name__ == "__main__":
    main()
