"""Recorta a fogueira (poses, partículas, fumaça e itens extras) de world/natal/fogueira.png.

Rode:  .venv\\Scripts\\python tools\\make_campfire.py [pasta_de_previa]

Saída:
  assets/sprites/world/campfire/
    unlit_snow.png     fogueira apagada coberta de neve
    extinguished.png   fogueira apagada (lenha queimada)
    kindling.png       começando a pegar fogo (neve derretendo nas pedras)
    fire_0..4.png      chamas acesas dançando e soltando fumaça
    flame.png          língua de fogo solta (partícula)
    smoke_0..2.png     nuvens de fumaça (pequena, média, grande)
    spark_0..3.png     fagulhas / brasas soltas
  assets/sprites/world/library/natal/fogueira.png         (miniatura da fogueira no editor)
  assets/sprites/world/library/natal/lenha_neve.png       (pilha de lenha com neve)
  assets/sprites/world/library/natal/espeto_fogueira.png  (espeto para assar perto do fogo)
"""
import os
import shutil
import sys
from collections import deque
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

SPRITES = Path(__file__).resolve().parent.parent / "assets" / "sprites"
SHEET = SPRITES / "world" / "natal" / "fogueira.png"
RAW_IN_LIB = SPRITES / "world" / "library" / "natal" / "Fogueira.png"
OUT = SPRITES / "world" / "campfire"
LIB_NATAL = SPRITES / "world" / "library" / "natal"

EDGE_TOL = 14
SEARCH = 24

# Poses da fogueira na folha (x, y, w, h)
POSES = {
    "unlit_snow": (260, 30, 200, 142),
    "extinguished": (560, 40, 185, 125),
    "kindling": (25, 172, 168, 205),
    "fire_0": (196, 172, 156, 205),
    "fire_1": (358, 172, 156, 205),
    "fire_2": (520, 172, 156, 205),
    "fire_3": (682, 172, 156, 205),
    "fire_4": (844, 165, 156, 212),
}

# Peças soltas de fogo/fumaça/brasas
LOOSE = {
    "flame": (182, 424, 44, 110),
    "smoke_0": (358, 484, 45, 48),
    "smoke_1": (418, 455, 58, 76),
    "smoke_2": (494, 405, 80, 126),
    "spark_0": (95, 494, 20, 38),
    "spark_1": (299, 454, 22, 33),
    "spark_2": (268, 509, 21, 24),
    "spark_3": (58, 502, 16, 20),
}

# Itens extras na linha inferior que também vão para a biblioteca do editor
EXTRA_LIB = {
    "lenha_neve": (745, 436, 124, 96),
    "espeto_fogueira": (872, 426, 124, 106),
}


def close(c, bg, tol):
    return abs(c[0] - bg[0]) <= tol and abs(c[1] - bg[1]) <= tol and abs(c[2] - bg[2]) <= tol


def cut_sheet_bg(src):
    """Remove o fundo cinza a partir das bordas sem comer as pedras cinza-escuras da fogueira."""
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


def base_mask(img, keep_bottom=58):
    """Faixa inferior (anel de pedras) para alinhar todas as poses sem pular."""
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
    # Se Fogueira.png na biblioteca for a folha bruta (1024x572), remove para salvar só a miniatura
    if RAW_IN_LIB.exists():
        try:
            raw_sz = pygame.image.load(str(RAW_IN_LIB)).get_size()
            if raw_sz[0] > 500:
                RAW_IN_LIB.unlink()
        except pygame.error:
            pass

    sheet = cut_sheet_bg(pygame.image.load(str(SHEET)).convert())
    crops = {}
    for k, r in POSES.items():
        c = sheet.subsurface(r).copy()
        c = c.subsurface(c.get_bounding_rect()).copy()
        if k in ("unlit_snow", "extinguished"):
            # Na folha original, a linha 1 (apagadas) foi desenhada ~18% maior que a linha 2;
            # iguala a escala do anel de pedras ao das poses acesas (145 px de largura)
            c = pygame.transform.smoothscale_by(c, 145.0 / 172.0)
        crops[k] = c

    ref = crops["fire_0"]
    rm = base_mask(ref)
    pos = {"fire_0": (0, 0)}
    for k, img in crops.items():
        if k == "fire_0":
            continue
        m = base_mask(img)
        bx = (ref.get_width() - img.get_width()) // 2
        by = ref.get_height() - img.get_height()
        if k in ("unlit_snow", "kindling"):
            # Têm borda de neve ao redor das pedras (5 px mais baixa que as pedras sem neve)
            pos[k] = (bx, by + 4)
            continue
        if k == "extinguished":
            pos[k] = (bx, by)
            continue
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
    pygame.image.save(ref, str(LIB_NATAL / "fogueira.png"))
    for k, r in EXTRA_LIB.items():
        c = sheet.subsurface(r).copy()
        pygame.image.save(c.subsurface(c.get_bounding_rect()).copy(), str(LIB_NATAL / f"{k}.png"))

    print(f"campfire: {len(crops)} poses {W}x{H}, {len(LOOSE)} partículas, +{len(EXTRA_LIB)} itens na biblioteca")

    if len(sys.argv) > 1:
        names = list(crops)
        prev = pygame.Surface(((W + 8) * len(names), H))
        prev.fill((190, 80, 150))
        font = pygame.font.SysFont("arial", 12, bold=True)
        for i, k in enumerate(names):
            ox = i * (W + 8)
            prev.blit(pygame.image.load(str(OUT / f"{k}.png")).convert_alpha(), (ox, 0))
            pygame.draw.line(prev, (255, 255, 0), (ox + W // 2, H - 12), (ox + W // 2, H), 2)
            pygame.draw.line(prev, (0, 255, 255), (ox, H - 4), (ox + W, H - 4), 1)
            prev.blit(font.render(k, True, (255, 255, 255), (0, 0, 0)), (ox + 4, 4))
        pygame.image.save(prev, str(Path(sys.argv[1]) / "campfire_poses.png"))


if __name__ == "__main__":
    main()
