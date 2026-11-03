"""Prepara o chão (ilha) a partir da imagem de referência.

Rode:  .venv\\Scripts\\python tools\\make_ground.py [preview.png]
Fonte: assets/sprites/world/ground/source/island_reference.png
Saída: assets/sprites/world/ground/ground.png    (a ilha com fundo transparente)
       assets/sprites/world/ground/walkable.png  (mapa de onde dá para andar:
                                                  branco = anda, preto = não)

1) Fundo: a imagem tem o "xadrez" de transparência DESENHADO (não é alpha).
   Removemos por balde de tinta a partir das bordas, só sobre pixels claros e
   cinzentos (sem cor) — a ilha tem contorno colorido, então o balde para nela.
2) Andável: pixels de GRAMA (verde dominante). Terra dos barrancos (marrom) e
   água (azul-esverdeado) ficam de fora. O mapa é feito em blocos de CELL px,
   com "fechamento" para engolir florzinhas/pedrinhas, só a maior região
   conectada (some com as vitórias-régias do lago) e uma margem da borda.
   Dá para retocar walkable.png à mão em qualquer editor (pintar de branco/preto).
"""
import os
import sys
from collections import deque
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / "assets" / "sprites" / "world" / "ground"
SOURCE = FOLDER / "source" / "island_reference.png"

CELL = 4        # resolução do mapa andável (px da imagem original por célula)
CLOSE = 2       # raio (células) do fechamento que engole flores/pedrinhas
MARGIN = 3      # células de folga entre a área andável e a borda da grama


def is_background(r, g, b):
    return min(r, g, b) >= 190 and max(r, g, b) - min(r, g, b) <= 14


def is_grass(r, g, b):
    # grama ~(105,156,46); água rasa ~(65,147,115) é verde também, mas com muito azul
    return g > r + 8 and g > b + 55


def remove_background(src):
    W, H = src.get_size()
    rgb = pygame.image.tobytes(src, "RGB")
    bg = bytearray(W * H)
    q = deque(i for i in range(W))  # borda de cima
    q.extend((H - 1) * W + x for x in range(W))
    q.extend(y * W for y in range(H))
    q.extend(y * W + W - 1 for y in range(H))
    while q:
        i = q.popleft()
        if bg[i]:
            continue
        r, g, b = rgb[3 * i], rgb[3 * i + 1], rgb[3 * i + 2]
        if not is_background(r, g, b):
            continue
        bg[i] = 1
        x, y = i % W, i // W
        if x > 0: q.append(i - 1)
        if x < W - 1: q.append(i + 1)
        if y > 0: q.append(i - W)
        if y < H - 1: q.append(i + W)

    rgba = bytearray(W * H * 4)
    for i in range(W * H):
        if not bg[i]:
            rgba[4 * i:4 * i + 3] = rgb[3 * i:3 * i + 3]
            rgba[4 * i + 3] = 255
    # Suaviza a franja clara (antialias misturado com o xadrez) perto do fundo
    for i in range(W * H):
        if bg[i]:
            continue
        x, y = i % W, i // W
        near = ((x > 0 and bg[i - 1]) or (x < W - 1 and bg[i + 1]) or
                (y > 0 and bg[i - W]) or (y < H - 1 and bg[i + W]))
        if near and min(rgb[3 * i:3 * i + 3]) > 150:
            rgba[4 * i + 3] = 90
    return pygame.image.frombytes(bytes(rgba), (W, H), "RGBA"), rgb


def walkable_grid(rgb, W, H):
    gw, gh = W // CELL, H // CELL
    grid = [[False] * gw for _ in range(gh)]
    for gy in range(gh):
        for gx in range(gw):
            n = 0
            for dy in range(CELL):
                base = ((gy * CELL + dy) * W + gx * CELL) * 3
                for dx in range(CELL):
                    j = base + dx * 3
                    if is_grass(rgb[j], rgb[j + 1], rgb[j + 2]):
                        n += 1
            grid[gy][gx] = n * 2 >= CELL * CELL
    return grid, gw, gh


def morph(grid, gw, gh, r, grow):
    """Dilata (grow=True) ou erode (grow=False) com raio r (quadrado)."""
    out = [[False] * gw for _ in range(gh)]
    for y in range(gh):
        for x in range(gw):
            vals = (grid[yy][xx]
                    for yy in range(max(0, y - r), min(gh, y + r + 1))
                    for xx in range(max(0, x - r), min(gw, x + r + 1)))
            out[y][x] = any(vals) if grow else all(vals)
            if not grow and (x < r or y < r or x >= gw - r or y >= gh - r):
                out[y][x] = False
    return out


def largest_region(grid, gw, gh):
    seen = [[False] * gw for _ in range(gh)]
    best = []
    for y in range(gh):
        for x in range(gw):
            if grid[y][x] and not seen[y][x]:
                comp, q = [], deque([(x, y)])
                seen[y][x] = True
                while q:
                    cx, cy = q.popleft()
                    comp.append((cx, cy))
                    for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                        if 0 <= nx < gw and 0 <= ny < gh and grid[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx] = True
                            q.append((nx, ny))
                if len(comp) > len(best):
                    best = comp
    out = [[False] * gw for _ in range(gh)]
    for x, y in best:
        out[y][x] = True
    return out


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    src = pygame.image.load(str(SOURCE)).convert()
    W, H = src.get_size()

    ground, rgb = remove_background(src)
    pygame.image.save(ground, str(FOLDER / "ground.png"))
    print(f"ground.png: {W}x{H}")

    grid, gw, gh = walkable_grid(rgb, W, H)
    grid = morph(morph(grid, gw, gh, CLOSE, True), gw, gh, CLOSE, False)  # fechamento
    grid = largest_region(grid, gw, gh)
    grid = morph(grid, gw, gh, MARGIN, False)                            # folga da borda
    mask_img = pygame.Surface((gw, gh))
    for y in range(gh):
        for x in range(gw):
            if grid[y][x]:
                mask_img.set_at((x, y), (255, 255, 255))
    pygame.image.save(mask_img, str(FOLDER / "walkable.png"))
    print(f"walkable.png: {gw}x{gh} (1 célula = {CELL}px da imagem)")

    if len(sys.argv) > 1:  # prévia: ilha + área andável em vermelho por cima
        prev = pygame.Surface((W, H))
        prev.fill((40, 50, 70))
        prev.blit(ground, (0, 0))
        tint = pygame.transform.scale(mask_img, (W, H))
        tint.set_colorkey((0, 0, 0))
        tint.fill((255, 60, 60), special_flags=pygame.BLEND_RGB_MULT)
        tint.set_alpha(90)
        prev.blit(tint, (0, 0))
        pygame.image.save(pygame.transform.smoothscale_by(prev, 0.6), sys.argv[1])


if __name__ == "__main__":
    main()
