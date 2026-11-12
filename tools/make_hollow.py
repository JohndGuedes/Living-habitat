"""Recorta a folha walk.png do Hollow em pastas de quadros com fundo transparente.

Rode:  .venv\\Scripts\\python tools\\make_hollow.py
Fonte: assets/sprites/character/hollow/walk.png
Saída: assets/sprites/character/hollow/frames/<animação>/000.png, 001.png, ...
"""
import os
from collections import deque
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / "assets" / "sprites" / "character" / "hollow"
SRC = FOLDER / "walk.png"
OUT = FOLDER / "frames"

CANVAS_W, CANVAS_H = 120, 186
ANCHOR_X, ANCHOR_Y = 60, 183

# Índices dos 19 quadros da folha (ordenados por linha de 150px e depois por x):
#   Linha 0 (esq): 0, 1, 2, 3   -> frente (parado / andando para baixo)
#   Linha 0 (dir): 4, 5, 6      -> diagonal costas-direita (andando para cima/lado)
#   Linha 1 (esq): 7, 8, 9      -> andando para a esquerda / diagonal costas-esquerda
#   Linha 1 (dir): 10, 11, 12   -> costas (andando para cima)
#   Linha 2 (esq): 13, 14, 15   -> perfil/3-4 direita (andando para os lados)
#   Linha 2 (dir): 16, 17, 18   -> costas passo largo (andando para cima)
GROUPS = {
    "idle":         [0, 1],
    "walk":         [13, 14, 15],
    "walk_down":    [0, 1, 2, 3],
    "walk_up":      [10, 11, 12, 16, 17, 18],
    "walk_up_side": [4, 5, 6],
    "walk_left":    [7, 8, 9],
}


def is_bg(c, bg=(70, 70, 70)):
    """Cor cinza neutra do fundo da folha."""
    return (abs(c.r - bg[0]) < 18 and abs(c.g - bg[1]) < 18 and abs(c.b - bg[2]) < 18
            and max(abs(c.r - c.g), abs(c.g - c.b), abs(c.r - c.b)) < 10)


def remove_background(sheet: pygame.Surface) -> pygame.Surface:
    """Remove o fundo cinza por flood-fill a partir das bordas e de frestas entre as pernas."""
    sheet = sheet.copy()
    w, h = sheet.get_size()
    bg = sheet.get_at((0, 0))[:3]

    visited = bytearray(w * h)
    q = deque()
    for x in range(w):
        q.append((x, 0))
        q.append((x, h - 1))
    for y in range(h):
        q.append((0, y))
        q.append((w - 1, y))

    while q:
        x, y = q.popleft()
        idx = y * w + x
        if visited[idx]:
            continue
        c = sheet.get_at((x, y))
        if not is_bg(c, bg):
            continue
        visited[idx] = 1
        sheet.set_at((x, y), (0, 0, 0, 0))
        if x > 0:
            q.append((x - 1, y))
        if x + 1 < w:
            q.append((x + 1, y))
        if y > 0:
            q.append((x, y - 1))
        if y + 1 < h:
            q.append((x, y + 1))

    # Frestas fechadas do fundo entre as pernas cruzadas (cercadas pelo contorno preto)
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            idx = y * w + x
            if visited[idx]:
                continue
            c = sheet.get_at((x, y))
            if abs(c.r - bg[0]) <= 6 and abs(c.g - bg[1]) <= 6 and abs(c.b - bg[2]) <= 6:
                pocket = []
                border_colors = []
                pq = deque([(x, y)])
                visited[idx] = 2
                while pq:
                    px, py = pq.popleft()
                    pocket.append((px, py))
                    for nx, ny in ((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)):
                        if 0 <= nx < w and 0 <= ny < h:
                            nidx = ny * w + nx
                            nc = sheet.get_at((nx, ny))
                            if not visited[nidx]:
                                if is_bg(nc, bg):
                                    visited[nidx] = 2
                                    pq.append((nx, ny))
                                else:
                                    border_colors.append(nc)
                if (pocket and len(pocket) < 400 and border_colors
                        and sum(max(bc.r, bc.g, bc.b) < 48 for bc in border_colors) / len(border_colors) > 0.85):
                    for px, py in pocket:
                        visited[py * w + px] = 1
                        sheet.set_at((px, py), (0, 0, 0, 0))

    # Suaviza 1px de borda colada no fundo transparente
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if visited[y * w + x] == 1:
                continue
            c = sheet.get_at((x, y))
            if (abs(c.r - bg[0]) < 26 and abs(c.g - bg[1]) < 26 and abs(c.b - bg[2]) < 26
                    and max(abs(c.r - c.g), abs(c.g - c.b)) < 12):
                if any(visited[ny * w + nx] == 1 for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))):
                    sheet.set_at((x, y), (c.r, c.g, c.b, 90))
    return sheet


def find_frame_rects(clean_sheet: pygame.Surface) -> list[pygame.Rect]:
    """Encontra os retângulos dos 19 quadros ordenados por linha e coluna."""
    m = pygame.mask.from_surface(clean_sheet, 20)
    rects = [r for r in m.get_bounding_rects() if r.w > 20 and r.h > 40]
    rects.sort(key=lambda r: (r.y // 150, r.x))
    return rects


def align_on_canvas(clean_sheet: pygame.Surface, r: pygame.Rect) -> pygame.Surface:
    """Centraliza cada quadro na tela 120x186 pelo eixo da cabeça/corpo e apoia os pés em ANCHOR_Y."""
    sub = clean_sheet.subsurface(r)
    xs = [x for y in range(min(80, r.h)) for x in range(r.w)
          if sub.get_at((x, y)).a > 128 and sub.get_at((x, y)).r > 180]
    spine_x = round((min(xs) + max(xs)) / 2) if xs else r.w // 2
    canvas = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
    dx = ANCHOR_X - spine_x
    dy = ANCHOR_Y - r.h
    canvas.blit(sub, (dx, dy))
    return canvas


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    raw = pygame.image.load(str(SRC)).convert_alpha()
    clean = remove_background(raw)
    rects = find_frame_rects(clean)
    print(f"quadros encontrados em {SRC.name}: {len(rects)}")

    for name, idxs in GROUPS.items():
        folder = OUT / name
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob("*.png"):
            old.unlink()
        for n, i in enumerate(idxs):
            frame = align_on_canvas(clean, rects[i])
            pygame.image.save(frame, str(folder / f"{n:03d}.png"))
        print(f"  {name}: {len(idxs)} quadros")


if __name__ == "__main__":
    main()
