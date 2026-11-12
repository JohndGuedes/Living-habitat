"""Recorta os dois bonecos de neve (Knight e Hornet) de world/natal/bonecos-neve.png.

Rode:  .venv\\Scripts\\python tools\\make_snowmen.py [pasta_de_previa]

Saída:
  assets/sprites/world/snowman_knight/
  assets/sprites/world/snowman_hornet/
    build_0..2.png   etapas de montagem (base -> corpo -> cabeça/chifres)
    idle_0..2.png    montado completo (cachecol/manto balançando ao vento)
    hit_0..1.png     levando golpe / rachando e desmontando
    destroyed.png    pilha de neve desmontada no chão
    piece_*.png      bolas de neve, flocos, galhos, cachecol/manto soltos
  assets/sprites/world/library/natal/boneco_neve_knight.png
  assets/sprites/world/library/natal/boneco_neve_hornet.png
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from slice_sheet import cut_background  # noqa: E402

SPRITES = Path(__file__).resolve().parent.parent / "assets" / "sprites"
SHEET = SPRITES / "world" / "natal" / "bonecos-neve.png"
LIB_NATAL = SPRITES / "world" / "library" / "natal"

KNIGHT_POSES = {
    "build_0": (35, 5, 125, 130),
    "build_1": (175, 5, 135, 130),
    "build_2": (320, 5, 140, 130),
    "idle_0": (35, 140, 125, 132),
    "idle_1": (175, 140, 135, 132),
    "idle_2": (320, 140, 140, 132),
    "hit_0": (25, 285, 145, 135),
    "hit_1": (175, 285, 145, 135),
    "destroyed": (318, 285, 165, 135),
}

KNIGHT_LOOSE = {
    "piece_0": (38, 456, 38, 36),     # bola de neve
    "piece_1": (38, 503, 42, 35),     # torrão de neve
    "piece_2": (89, 457, 36, 36),     # floco pequeno
    "piece_3": (92, 505, 31, 31),     # pedaço pequeno de neve
    "piece_4": (170, 467, 60, 59),    # floco grande
    "piece_5": (324, 460, 70, 74),    # montinho de neve
    "piece_6": (405, 460, 66, 76),    # galhos quebrados
    "piece_7": (860, 456, 112, 72),   # cachecol vermelho
}

HORNET_POSES = {
    "build_0": (540, 5, 135, 132),
    "build_1": (685, 5, 140, 132),
    "build_2": (840, 5, 145, 132),
    "idle_0": (540, 140, 135, 136),
    "idle_1": (685, 140, 140, 136),
    "idle_2": (840, 140, 145, 136),
    "hit_0": (530, 285, 155, 140),
    "hit_1": (685, 285, 160, 140),
    "destroyed": (845, 285, 155, 140),
}

HORNET_LOOSE = {
    "piece_0": (546, 454, 49, 37),    # bolinhas de neve
    "piece_1": (38, 456, 38, 36),     # bola de neve
    "piece_2": (89, 457, 36, 36),     # floco pequeno
    "piece_3": (559, 495, 75, 42),    # galho deitado
    "piece_4": (604, 454, 46, 68),    # galho em pé
    "piece_5": (665, 454, 85, 84),    # montinho de neve com flocos
    "piece_6": (763, 457, 86, 78),    # cachecol enrolado
    "piece_7": (860, 456, 112, 72),   # manto vermelho
}

SEARCH = 24


def base_mask(img, keep_bottom=38):
    """Mantém apenas a faixa inferior (base de neve) para alinhar as poses sem pular."""
    m = pygame.mask.from_surface(img, 100)
    w, h = img.get_size()
    cut = pygame.mask.Mask((w, h))
    cut.draw(m, (0, 0))
    erase_h = max(0, h - keep_bottom)
    if erase_h > 0:
        cut.erase(pygame.mask.Mask((w, erase_h), fill=True), (0, 0))
    return cut


def export_snowman(sheet, name, poses_def, loose_def, thumb_name, preview_dir=None):
    out_dir = SPRITES / "world" / f"snowman_{name}"
    crops = {}
    for k, r in poses_def.items():
        c = sheet.subsurface(r).copy()
        crops[k] = c.subsurface(c.get_bounding_rect()).copy()

    ref = crops["idle_0"]
    rm = base_mask(ref)
    pos = {"idle_0": (0, 0)}
    for k, img in crops.items():
        if k == "idle_0":
            continue
        bx = (ref.get_width() - img.get_width()) // 2
        by = ref.get_height() - img.get_height()
        if k in ("destroyed", "hit_1"):
            # Pose desmontando/pilha no chão: centraliza horizontalmente pela base de referência
            pos[k] = (bx, by)
            continue
        m = base_mask(img)
        best, best_p = -1, (bx, by)
        for dy in range(-SEARCH, SEARCH + 1, 1):
            for dx in range(-SEARCH, SEARCH + 1, 1):
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

    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.png"):
        old.unlink()

    for k, img in crops.items():
        c = pygame.Surface((W, H), pygame.SRCALPHA)
        c.blit(img, (round(pos[k][0] - x0 + (half - base_x)), pos[k][1] - y0))
        pygame.image.save(c, str(out_dir / f"{k}.png"))

    for k, r in loose_def.items():
        c = sheet.subsurface(r).copy()
        pygame.image.save(c.subsurface(c.get_bounding_rect()).copy(), str(out_dir / f"{k}.png"))

    LIB_NATAL.mkdir(parents=True, exist_ok=True)
    pygame.image.save(ref, str(LIB_NATAL / f"{thumb_name}.png"))
    print(f"snowman_{name}: {len(crops)} poses {W}x{H}, {len(loose_def)} peças -> {thumb_name}.png")

    if preview_dir:
        names = list(crops)
        prev = pygame.Surface(((W + 8) * len(names), H))
        prev.fill((190, 80, 150))
        font = pygame.font.SysFont("arial", 12, bold=True)
        for i, k in enumerate(names):
            ox = i * (W + 8)
            prev.blit(pygame.image.load(str(out_dir / f"{k}.png")).convert_alpha(), (ox, 0))
            pygame.draw.line(prev, (255, 255, 0), (ox + W // 2, H - 12), (ox + W // 2, H), 2)
            pygame.draw.line(prev, (0, 255, 255), (ox, H - 1), (ox + W, H - 1), 1)
            prev.blit(font.render(k, True, (255, 255, 255), (0, 0, 0)), (ox + 4, 4))
        pygame.image.save(prev, str(Path(preview_dir) / f"snowman_{name}_poses.png"))


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    sheet = cut_background(pygame.image.load(str(SHEET)).convert())
    preview = sys.argv[1] if len(sys.argv) > 1 else None
    export_snowman(sheet, "knight", KNIGHT_POSES, KNIGHT_LOOSE, "boneco_neve_knight", preview)
    export_snowman(sheet, "hornet", HORNET_POSES, HORNET_LOOSE, "boneco_neve_hornet", preview)


if __name__ == "__main__":
    main()

