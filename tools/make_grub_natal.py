"""Recorta o Grub de Natal no pote (e fora dele) da folha world/natal/group-natal.png.

Rode:  .venv\\Scripts\\python tools\\make_grub_natal.py [pasta_de_previa]

Saída:
  assets/sprites/world/grub_natal/
    jar_0..5.png       Grub dentro do pote de vidro com gorro de Natal
    hit_0..2.png       pote levando golpes / rachando / tampa soltando
    shatter_0..2.png   pote quebrando em cacos e o Grub pulando para fora
    free_0..2.png      Grub livre pulando feliz com gorro de Natal
    burrow_0..2.png    Grub no montinho de neve / mergulhando / só o gorro aparecendo
    broken_jar.png     base de vidro quebrado na neve
    lid.png            tampa metálica solta
    piece_0..6.png     cacos de vidro, neve, azevinho, gorro, estrelinhas
  assets/sprites/world/library/natal/grub_natal.png  (miniatura na biblioteca do editor)
"""
import os
import shutil
import sys
from collections import deque
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

SPRITES = Path(__file__).resolve().parent.parent / "assets" / "sprites"
SHEET = SPRITES / "world" / "natal" / "group-natal.png"
RAW_IN_LIB = SPRITES / "world" / "library" / "natal" / "group-natal.png"
OUT = SPRITES / "world" / "grub_natal"
LIB_NATAL = SPRITES / "world" / "library" / "natal"

EDGE_TOL = 14

POSES = {
    # Linha 1: dentro do pote
    "jar_0": (50, 8, 108, 126),
    "jar_1": (202, 8, 108, 126),
    "jar_2": (353, 8, 108, 126),
    "jar_3": (557, 8, 108, 126),
    "jar_4": (710, 8, 108, 126),
    "jar_5": (861, 8, 108, 126),
    # Linha 2: golpes e quebra do pote
    "hit_0": (50, 148, 122, 126),
    "hit_1": (190, 148, 128, 126),
    "hit_2": (342, 146, 134, 128),
    "shatter_0": (534, 155, 146, 128),
    "shatter_1": (690, 155, 146, 128),
    "shatter_2": (844, 146, 148, 140),
    # Linha 3: livre e brincando na neve
    "free_0": (60, 292, 88, 132),
    "free_1": (204, 292, 92, 132),
    "free_2": (356, 292, 92, 132),
    "burrow_0": (550, 305, 130, 116),
    "burrow_1": (702, 305, 130, 116),
    "burrow_2": (856, 305, 130, 116),
    # Linha 4 (pose do pote quebrado no chão)
    "broken_jar": (34, 450, 128, 96),
}

LOOSE = {
    "lid": (170, 473, 74, 52),
    "piece_0": (252, 460, 64, 72),    # cacos de vidro 1
    "piece_1": (326, 462, 64, 70),    # cacos de vidro 2
    "piece_2": (400, 460, 72, 74),    # bolas de neve + folhinha
    "piece_3": (560, 458, 92, 78),    # folhas e frutinhas de azevinho
    "piece_4": (668, 468, 78, 56),    # gorro de Natal solto
    "piece_5": (764, 464, 58, 62),    # estrelinhas
    "piece_6": (838, 466, 64, 60),    # poeira de neve
}


def close(c, bg, tol):
    return abs(c[0] - bg[0]) <= tol and abs(c[1] - bg[1]) <= tol and abs(c[2] - bg[2]) <= tol


def cut_sheet_bg(src):
    """Remove o fundo cinza a partir das bordas e de pontos entre cacos, preservando o vidro escuro."""
    W, H = src.get_size()
    rgb = pygame.image.tobytes(src, "RGB")
    bg = tuple(rgb[0:3])
    out = bytearray(W * H)
    q = deque(
        list(range(W))
        + [(H - 1) * W + x for x in range(W)]
        + [y * W for y in range(H)]
        + [y * W + W - 1 for y in range(H)]
    )
    while q:
        i = q.popleft()
        if out[i] or not close(rgb[3 * i : 3 * i + 3], bg, EDGE_TOL):
            continue
        out[i] = 1
        x, y = i % W, i // W
        if x > 0:
            q.append(i - 1)
        if x < W - 1:
            q.append(i + 1)
        if y > 0:
            q.append(i - W)
        if y < H - 1:
            q.append(i + W)
    rgba = bytearray(W * H * 4)
    for i in range(W * H):
        if out[i]:
            continue
        rgba[4 * i : 4 * i + 3] = rgb[3 * i : 3 * i + 3]
        rgba[4 * i + 3] = 255
    return pygame.image.frombytes(bytes(rgba), (W, H), "RGBA")


def base_mask(img, keep_bottom=34):
    """Faixa inferior do pote (base de neve e azevinho) para alinhar sem deslocar nos golpes."""
    m = pygame.mask.from_surface(img, 100)
    w, h = img.get_size()
    cut = pygame.mask.Mask((w, h))
    cut.draw(m, (0, 0))
    erase_h = max(0, h - keep_bottom)
    if erase_h > 0:
        cut.erase(pygame.mask.Mask((w, erase_h), fill=True), (0, 0))
    return cut


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    if not SHEET.exists() and RAW_IN_LIB.exists():
        SHEET.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RAW_IN_LIB, SHEET)
    if RAW_IN_LIB.exists():
        try:
            if pygame.image.load(str(RAW_IN_LIB)).get_size()[0] > 500:
                RAW_IN_LIB.unlink()
        except pygame.error:
            pass

    sheet = cut_sheet_bg(pygame.image.load(str(SHEET)).convert())
    crops = {}
    for k, r in POSES.items():
        c = sheet.subsurface(r).copy()
        crops[k] = c.subsurface(c.get_bounding_rect()).copy()

    ref = crops["jar_0"]
    rm = base_mask(ref)
    pos = {"jar_0": (0, 0)}
    for k, img in crops.items():
        if k == "jar_0":
            continue
        bx = (ref.get_width() - img.get_width()) // 2
        by = ref.get_height() - img.get_height()
        if k.startswith(("jar_", "hit_")):
            m = base_mask(img)
            best, best_p = -1, (bx, by)
            for dy in range(-18, 19, 1):
                for dx in range(-18, 19, 1):
                    a = rm.overlap_area(m, (bx + dx, by + dy))
                    if a > best:
                        best, best_p = a, (bx + dx, by + dy)
            pos[k] = best_p
        else:
            pos[k] = (bx, by)

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

    LIB_NATAL.mkdir(parents=True, exist_ok=True)
    pygame.image.save(crops["jar_0"], str(LIB_NATAL / "grub_natal.png"))
    print(f"grub_natal: {len(crops)} poses {W}x{H}, {len(LOOSE)} peças -> grub_natal.png")

    if len(sys.argv) > 1:
        names = list(crops)
        cols = 6
        rows = (len(names) + cols - 1) // cols
        prev = pygame.Surface(((W + 8) * cols, (H + 8) * rows))
        prev.fill((190, 80, 150))
        font = pygame.font.SysFont("arial", 12, bold=True)
        for i, k in enumerate(names):
            col, row = i % cols, i // cols
            ox, oy = col * (W + 8), row * (H + 8)
            prev.blit(pygame.image.load(str(OUT / f"{k}.png")).convert_alpha(), (ox, oy))
            pygame.draw.line(prev, (255, 255, 0), (ox + W // 2, oy + H - 10), (ox + W // 2, oy + H), 2)
            prev.blit(font.render(k, True, (255, 255, 255), (0, 0, 0)), (ox + 4, oy + 4))
        pygame.image.save(prev, str(Path(sys.argv[1]) / "grub_natal_poses.png"))


if __name__ == "__main__":
    main()
