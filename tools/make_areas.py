"""Prepara as áreas (ilhas) a partir das imagens do usuário.

Rode:  .venv\\Scripts\\python tools\\make_areas.py [pasta_de_previas]

Fonte: assets/sprites/world/areas/<área>/source/<arquivo>.png
Saída: assets/sprites/world/areas/<área>/
         ground.png    a ilha com fundo transparente
         walkable.png  onde dá para andar (branco), 1 célula = CELL px da imagem
         water.png     o lago (branco), mesma grade (onde dá para nadar)
         cave.png      (só se a área tiver "cave") a caverna recortada
         meta.json     pontos das florzinhas brilhantes (comida), em px de ground.png

1) Fundo: preto, removido por balde de tinta a partir das bordas (pixels bem escuros).
2) Andável: grama (verde-azulada) e trilhas de pedra (cinza claro). Fechamento para
   engolir pedrinhas/plantas, só a maior região e uma folga da borda.
3) Lago: água (azul) a partir de um ponto dentro dele ("lake"), porque a cor das
   paredes dos barrancos é parecida; buracos (vitórias-régias) preenchidos.
4) Caverna ("cave"): recorte separado; "erase" apaga as setas da imagem de referência.
Dá para retocar walkable.png/water.png à mão (branco/preto). Rodar de novo sobrescreve.
"""
import json
import os
import sys
from collections import deque
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
AREAS_DIR = ROOT / "assets" / "sprites" / "world" / "areas"

CELL = 4        # resolução dos mapas (px da imagem por célula)
CLOSE = 2       # raio (células) do fechamento
MARGIN = 3      # células de folga entre a área andável e a borda

# px da imagem de origem
AREAS = {
    "lago": {
        "source": "source/island.png",
        "lake": (1200, 320),
    },
    "caverna": {
        "source": "source/island_cave.png",
        "lake": (1150, 600),
        "island_top": 290,                         # a ilha começa aqui (acima: caverna e setas)
        "cave": (380, 0, 780, 288),                # retângulo da caverna (x, y, w, h)
        "erase": [(498, 270, 42, 100), (986, 270, 42, 100)],   # as setas
    },
}


def is_background(r, g, b):
    return max(r, g, b) <= 24


def is_ground(r, g, b):
    grass = g > r + 18 and g >= b - 14 and g > 55
    path = min(r, g, b) > 85 and max(r, g, b) - min(r, g, b) < 35
    return grass or path


def is_water(r, g, b):
    # água ~(30,55,75): bem mais azul que verde. Paredes ~(32,47,72) têm pouco verde;
    # a grama azulada da caverna ~(40,67,81) tem azul quase igual ao verde.
    return b > g + 16 and g > r + 15 and g < 72 and 40 < b < 115


def remove_background(src):
    W, H = src.get_size()
    rgb = pygame.image.tobytes(src, "RGB")
    bg = bytearray(W * H)
    q = deque(range(W))
    q.extend((H - 1) * W + x for x in range(W))
    q.extend(y * W for y in range(H))
    q.extend(y * W + W - 1 for y in range(H))
    while q:
        i = q.popleft()
        if bg[i]:
            continue
        if not is_background(rgb[3 * i], rgb[3 * i + 1], rgb[3 * i + 2]):
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
    return pygame.image.frombytes(bytes(rgba), (W, H), "RGBA"), rgb


def cut_cave(src):
    """A caverna tem o interior escuro (parecido com o fundo): em cada coluna fica
    opaco tudo entre o primeiro e o último pixel do desenho (o fundo de fora some)."""
    W, H = src.get_size()
    out = pygame.Surface((W, H), pygame.SRCALPHA)
    for x in range(W):
        ys = [y for y in range(H) if not is_background(*src.get_at((x, y))[:3])]
        if len(ys) < 3:
            continue
        for y in range(ys[0], ys[-1] + 1):
            r, g, b, _ = src.get_at((x, y))
            out.set_at((x, y), (r, g, b, 255))
    return out.subsurface(out.get_bounding_rect()).copy()


def grid_of(rgb, W, H, test):
    gw, gh = W // CELL, H // CELL
    grid = [[False] * gw for _ in range(gh)]
    for gy in range(gh):
        for gx in range(gw):
            n = 0
            for dy in range(CELL):
                base = ((gy * CELL + dy) * W + gx * CELL) * 3
                for dx in range(CELL):
                    j = base + dx * 3
                    n += test(rgb[j], rgb[j + 1], rgb[j + 2])
            grid[gy][gx] = n * 2 >= CELL * CELL
    return grid, gw, gh


def morph(grid, gw, gh, r, grow):
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


def region(grid, gw, gh, seed=None):
    """Maior região conectada (ou a que contém `seed`, em células)."""
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
                if seed is not None and seed in comp:
                    best = comp
                    break
                if seed is None and len(comp) > len(best):
                    best = comp
            if seed is not None and best:
                break
        if seed is not None and best:
            break
    out = [[False] * gw for _ in range(gh)]
    for x, y in best:
        out[y][x] = True
    return out


def fill_holes(grid, gw, gh, max_cells=300):
    """Preenche buracos PEQUENOS (vitórias-régias, pedrinhas): pedaços sem água
    cercados de água, com até `max_cells` células."""
    out = [row[:] for row in grid]
    seen = [[False] * gw for _ in range(gh)]
    for y in range(gh):
        for x in range(gw):
            if grid[y][x] or seen[y][x]:
                continue
            comp, q, edge = [], deque([(x, y)]), False
            seen[y][x] = True
            while q:
                cx, cy = q.popleft()
                comp.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if not (0 <= nx < gw and 0 <= ny < gh):
                        edge = True
                    elif not grid[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        q.append((nx, ny))
            if not edge and len(comp) <= max_cells:
                for cx, cy in comp:
                    out[cy][cx] = True
    return out


def save_grid(grid, gw, gh, path):
    img = pygame.Surface((gw, gh))
    for y in range(gh):
        for x in range(gw):
            if grid[y][x]:
                img.set_at((x, y), (255, 255, 255))
    pygame.image.save(img, str(path))
    return img


def food_spots(ground, walk, gw, gh):
    """Florzinhas brilhantes (pixels quase brancos) perto da área andável."""
    W, H = ground.get_size()
    S = 12
    cells = set()
    for y in range(0, H, 3):
        for x in range(0, W, 3):
            c = ground.get_at((x, y))
            if c.a > 200 and min(c.r, c.g, c.b) > 165:
                cells.add((x // S, y // S))
    spots, used = [], set()
    for cx, cy in sorted(cells):
        if (cx, cy) in used:
            continue
        group = [(a, b) for a in range(cx - 2, cx + 3) for b in range(cy - 2, cy + 3) if (a, b) in cells]
        used.update(group)
        x = sum(a for a, _ in group) / len(group) * S + S / 2
        y = max(b for _, b in group) * S + S
        gx, gy = int(x // CELL), int(y // CELL)
        near = any(0 <= gy + dy < gh and 0 <= gx + dx < gw and walk[gy + dy][gx + dx]
                   for dy in range(-8, 9, 2) for dx in range(-8, 9, 2))
        if near:
            spots.append((round(x), round(y)))
    return spots


def make(name, spec, preview_dir=None):
    folder = AREAS_DIR / name
    src = pygame.image.load(str(folder / spec["source"])).convert()
    for rect in spec.get("erase", []):
        src.fill((0, 0, 0), rect)
    if "cave" in spec:
        cave = cut_cave(src.subsurface(spec["cave"]).copy())
        pygame.image.save(cave, str(folder / "cave.png"))
        print(f"  cave.png: {cave.get_size()}")
    top = spec.get("island_top", 0)
    if top:
        src = src.subsurface((0, top, src.get_width(), src.get_height() - top)).copy()
    W, H = src.get_size()
    ground, rgb = remove_background(src)
    pygame.image.save(ground, str(folder / "ground.png"))
    print(f"  ground.png: {W}x{H}")

    walk, gw, gh = grid_of(rgb, W, H, is_ground)
    walk = morph(morph(walk, gw, gh, CLOSE, True), gw, gh, CLOSE, False)
    walk = region(walk, gw, gh)
    walk = morph(walk, gw, gh, MARGIN, False)
    wimg = save_grid(walk, gw, gh, folder / "walkable.png")

    lx, ly = spec["lake"]
    water, _, _ = grid_of(rgb, W, H, is_water)
    water = morph(morph(water, gw, gh, CLOSE, True), gw, gh, CLOSE, False)   # fecha
    water = morph(morph(water, gw, gh, 2, False), gw, gh, 2, True)           # abre: corta pontes finas
    water = region(water, gw, gh, seed=(lx // CELL, (ly - top) // CELL))
    water = fill_holes(water, gw, gh)
    aimg = save_grid(water, gw, gh, folder / "water.png")
    print(f"  walkable.png / water.png: {gw}x{gh} (1 célula = {CELL}px)")

    food = food_spots(ground, walk, gw, gh)
    meta = {"food": food, "island_top": top}
    if "cave" in spec:
        meta["cave_rect"] = spec["cave"]
    (folder / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"  meta.json: {len(food)} florzinhas (comida)")

    if preview_dir:
        prev = pygame.Surface((W, H))
        prev.fill((60, 90, 130))
        prev.blit(ground, (0, 0))
        for img, col in ((wimg, (255, 60, 60)), (aimg, (60, 140, 255))):
            tint = pygame.transform.scale(img, (gw * CELL, gh * CELL))
            tint.set_colorkey((0, 0, 0))
            tint.fill(col, special_flags=pygame.BLEND_RGB_MULT)
            tint.set_alpha(110)
            prev.blit(tint, (0, 0))
        for x, y in food:
            pygame.draw.circle(prev, (255, 255, 0), (x, y), 6, 2)
        pygame.image.save(pygame.transform.smoothscale_by(prev, 0.6), str(Path(preview_dir) / f"area_{name}.png"))


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    preview = sys.argv[1] if len(sys.argv) > 1 else None
    for name, spec in AREAS.items():
        print(name)
        make(name, spec, preview)


if __name__ == "__main__":
    main()
