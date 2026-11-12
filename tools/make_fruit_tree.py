"""Recorta a árvore de frutas (e as frutas) da folha world/natal/arvores.png.

Rode:  .venv\\Scripts\\python tools\\make_fruit_tree.py [pasta_de_previa]

Saída: assets/sprites/world/fruit_tree/
         full.png       a árvore com frutas (parada)
         hit_0..3.png   balançando com o golpe (neve e folhas voando, frutas caindo)
         empty.png      sem frutas
         fruit_0..N.png as cerejas (a fruta que cai no chão)
       assets/sprites/world/library/natal_2/arvore_frutas.png  (miniatura no editor)

As poses têm tamanhos e enquadramentos diferentes: cada uma é alinhada à árvore cheia
pela BASE DO TRONCO (maior sobreposição da parte de baixo do desenho) e salva numa tela
do mesmo tamanho, com a base no centro de baixo. Assim a animação não pula.
Os retângulos (x, y, w, h) são da folha; o fundo cinza sai como no slice_sheet.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from slice_sheet import cut_background  # noqa: E402

SPRITES = Path(__file__).resolve().parent.parent / "assets" / "sprites"
SHEET = SPRITES / "world" / "natal" / "arvores.png"
OUT = SPRITES / "world" / "fruit_tree"
THUMB = SPRITES / "world" / "library" / "natal_2" / "arvore_frutas.png"

FRAMES = {                                   # ordem do golpe: impacto -> balanço -> frutas -> folhas
    "full": (846, 108, 144, 204),
    "hit_0": (412, 344, 158, 206),
    "hit_1": (657, 110, 151, 203),
    "hit_2": (582, 349, 127, 201),
    "hit_3": (730, 366, 121, 186),
    "empty": (870, 352, 141, 198),
}
FRUITS = [(546, 36, 26, 33), (605, 33, 30, 38), (666, 30, 40, 46), (739, 26, 46, 52), (817, 26, 52, 54),
          (898, 28, 44, 50)]
SEARCH = 30                                  # px procurados em volta para alinhar


def base_mask(img):
    """Só a parte de baixo (tronco e montinho de neve), para alinhar pela base."""
    m = pygame.mask.from_surface(img, 100)
    w, h = img.get_size()
    cut = pygame.mask.Mask((w, h))
    cut.draw(m, (0, 0))
    top = pygame.mask.Mask((w, int(h * 0.62)), fill=True)
    cut.erase(top, (0, 0))
    return cut


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    sheet = cut_background(pygame.image.load(str(SHEET)).convert())
    crops = {k: sheet.subsurface(r).copy() for k, r in FRAMES.items()}
    ref = crops["full"]
    rm = base_mask(ref)
    pos = {"full": (0, 0)}
    for k, img in crops.items():
        if k == "full":
            continue
        m = base_mask(img)
        bx = (ref.get_width() - img.get_width()) // 2
        by = ref.get_height() - img.get_height()
        best, best_p = -1, (bx, by)
        for dy in range(-SEARCH, SEARCH + 1, 2):
            for dx in range(-SEARCH, SEARCH + 1, 2):
                a = rm.overlap_area(m, (bx + dx, by + dy))
                if a > best:
                    best, best_p = a, (bx + dx, by + dy)
        pos[k] = best_p
    # tela comum (todas as poses cabem), base da árvore cheia no centro de baixo
    x0 = min(p[0] for p in pos.values())
    y0 = min(p[1] for p in pos.values())
    x1 = max(p[0] + crops[k].get_width() for k, p in pos.items())
    y1 = max(p[1] + crops[k].get_height() for k, p in pos.items())
    base_x = ref.get_width() / 2 - x0
    half = max(base_x, (x1 - x0) - base_x)
    W, H = round(half * 2), y1 - y0
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    for k, img in crops.items():
        c = pygame.Surface((W, H), pygame.SRCALPHA)
        c.blit(img, (round(pos[k][0] - x0 + (half - base_x)), pos[k][1] - y0))
        pygame.image.save(c, str(OUT / f"{k}.png"))
    for n, r in enumerate(FRUITS):
        f = sheet.subsurface(r).copy()
        f = f.subsurface(f.get_bounding_rect()).copy()
        pygame.image.save(f, str(OUT / f"fruit_{n}.png"))
    THUMB.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(ref.subsurface(ref.get_bounding_rect()).copy(), str(THUMB))
    print(f"árvore: {len(crops)} poses {W}x{H}, frutas: {len(FRUITS)}")
    if len(sys.argv) > 1:
        prev = pygame.Surface((W * len(crops) + 10 * len(crops), H))
        prev.fill((200, 90, 160))
        for i, k in enumerate(crops):
            img = pygame.image.load(str(OUT / f"{k}.png")).convert_alpha()
            prev.blit(img, (i * (W + 10), 0))
            pygame.draw.line(prev, (255, 255, 0), (i * (W + 10) + W // 2, H - 12), (i * (W + 10) + W // 2, H), 2)
        pygame.image.save(prev, str(Path(sys.argv[1]) / "fruit_tree.png"))


if __name__ == "__main__":
    main()
