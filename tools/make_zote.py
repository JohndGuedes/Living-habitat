"""Recorta o boneco de treino (Zote) da folha world/natal/boneco-zote.png.

Rode:  .venv\\Scripts\\python tools\\make_zote.py [pasta_de_previa]

Saída: assets/sprites/world/zote/
         idle_0..3.png   parado (balança de leve)
         hit_0..4.png    golpe: inclina -> estoura em lascas -> volta -> poeira -> endireita
         damaged.png     pano rasgado (meia vida)
         nobase.png      base quebrada (quase destruído)
         headless.png    sem cabeça (o corpo que cai quando quebra)
         head.png        a cabeça (voa e fica no chão)
         base.png        só a base (o que sobra até ele voltar)
         piece_*.png     lascas, madeira, poeira, neve (voam a cada golpe)
         spark_*.png     faíscas do impacto;  smoke.png  fumaça;  emote_*.png  balões
       assets/sprites/world/library/natal/boneco_zote.png (miniatura no editor)

As poses inteiras (parado, golpe, damaged, nobase, headless) são alinhadas pela BASE
(maior sobreposição da parte de baixo) numa tela comum, com a base no centro de baixo.
Retângulos (x, y, w, h) da folha; o fundo sai como no slice_sheet.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from slice_sheet import cut_background  # noqa: E402

SPRITES = Path(__file__).resolve().parent.parent / "assets" / "sprites"
SHEET = SPRITES / "world" / "natal" / "boneco-zote.png"
OUT = SPRITES / "world" / "zote"
THUMB = SPRITES / "world" / "library" / "natal" / "boneco_zote.png"

POSES = {
    "idle_0": (51, 5, 102, 173), "idle_1": (179, 4, 102, 174),
    "idle_2": (307, 8, 102, 170), "idle_3": (435, 5, 103, 173),
    "hit_0": (30, 196, 156, 172), "hit_1": (240, 194, 173, 172), "hit_2": (445, 197, 136, 169),
    "hit_3": (630, 193, 159, 173), "hit_4": (860, 186, 108, 180),
    "damaged": (860, 186, 108, 180),
    "nobase": (30, 368, 136, 190),
    "headless": (163, 402, 132, 158),
}
LOOSE = {                       # peças soltas (recortadas justo, sem alinhar)
    "head": (335, 383, 56, 76), "base": (314, 476, 103, 82),
    "piece_0": (446, 412, 53, 57), "piece_1": (516, 411, 46, 58), "piece_2": (577, 418, 48, 45),
    "piece_3": (449, 489, 37, 27), "piece_4": (517, 485, 46, 46), "piece_5": (578, 488, 45, 44),
    "snow_0": (648, 419, 38, 36), "snow_1": (644, 494, 42, 33),
    "spark_0": (705, 415, 46, 52), "spark_1": (703, 489, 49, 43),
    "smoke": (794, 412, 49, 58),
    "emote_0": (861, 412, 54, 58), "emote_1": (927, 411, 55, 57), "emote_2": (862, 480, 53, 53),
}
SEARCH = 30


def base_mask(img):
    m = pygame.mask.from_surface(img, 100)
    w, h = img.get_size()
    cut = pygame.mask.Mask((w, h))
    cut.draw(m, (0, 0))
    cut.erase(pygame.mask.Mask((w, int(h * 0.72)), fill=True), (0, 0))   # só a base
    return cut


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    sheet = cut_background(pygame.image.load(str(SHEET)).convert())
    crops = {}
    for k, r in POSES.items():
        c = sheet.subsurface(r).copy()
        crops[k] = c.subsurface(c.get_bounding_rect()).copy()
    ref = crops["idle_0"]
    rm = base_mask(ref)
    pos = {"idle_0": (0, 0)}
    for k, img in crops.items():
        if k == "idle_0":
            continue
        m = base_mask(img)
        bx, by = (ref.get_width() - img.get_width()) // 2, ref.get_height() - img.get_height()
        if k in ("nobase", "headless"):            # outra base: só centraliza pelo pé
            pos[k] = (bx, by)
            continue
        best, best_p = -1, (bx, by)
        for dy in range(-SEARCH, SEARCH + 1, 2):
            for dx in range(-SEARCH, SEARCH + 1, 2):
                a = rm.overlap_area(m, (bx + dx, by + dy))
                if a > best:
                    best, best_p = a, (bx + dx, by + dy)
        pos[k] = best_p
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
    for k, r in LOOSE.items():
        c = sheet.subsurface(r).copy()
        pygame.image.save(c.subsurface(c.get_bounding_rect()).copy(), str(OUT / f"{k}.png"))
    pygame.image.save(ref, str(THUMB))
    print(f"zote: {len(crops)} poses {W}x{H}, {len(LOOSE)} peças")
    if len(sys.argv) > 1:
        names = list(crops)
        prev = pygame.Surface(((W + 8) * len(names), H))
        prev.fill((200, 90, 160))
        for i, k in enumerate(names):
            prev.blit(pygame.image.load(str(OUT / f"{k}.png")).convert_alpha(), (i * (W + 8), 0))
            pygame.draw.line(prev, (255, 255, 0), (i * (W + 8) + W // 2, H - 10), (i * (W + 8) + W // 2, H), 2)
        pygame.image.save(prev, str(Path(sys.argv[1]) / "zote_poses.png"))


if __name__ == "__main__":
    main()
