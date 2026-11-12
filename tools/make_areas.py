"""Prepara as áreas (ilhas) a partir das imagens do usuário.

Rode:  .venv\\Scripts\\python tools\\make_areas.py [pasta_de_previas]

Fonte: assets/sprites/world/areas/<área>/source/<arquivo>.png
Saída: assets/sprites/world/areas/<área>/
         ground.png    a ilha com fundo transparente
         ground_<v>.png  versões da mesma ilha ("variants", ex.: natal), recortadas pelo
                       contorno da ilha normal (as imagens são alinhadas pixel a pixel)
         walkable_frozen.png  andável com o lago congelado (gelo: dá para andar por cima)
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
        "source": "source/ground.png",          # a ilha com a casinha
        "lake": (760, 190),
        # não andável mesmo tendo cor de grama (x, y, w, h em px da imagem): a casinha
        "block": [(350, 20, 140, 118)],
    },
    # mapa de Natal (outro desenho: dois níveis ligados por escadas, píer, casinha,
    # lago congelado e a cachoeira no alto). Usado em nov/dez (scene.AREAS["lago"]["seasons"]).
    "natal": {
        "source": "source/ground-natal.jpg",
        "cell": 8,                               # imagem grande (2752x1536): células maiores
        "margin": 1,                             # folga da borda (em células): escadas são estreitas
        "bg": "corner", "bg_tol": 14,            # fundo azul-escuro com estrelas
        "ground": "snow",                        # neve, gelo, trilhas, escadas e píer
        "lake": (1960, 820), "lake_test": "ice",
        "frozen": True,                          # o gelo já é chão
        # a cachoeira (branca como a neve): não é chão; os personagens PULAM por cima dela
        "block": [(2008, 133, 225, 600), (2217, 150, 67, 167)],
        # andável à força (x, y, w, h): a escada da direita, que desce da beira da cachoeira
        # (tem uma coluna de pedra escura no meio que cortava o caminho)
        # o halo desenhado em volta da estrela da árvore ficou como um disco escuro sobre o
        # céu: nesse círculo (cx, cy, raio), acima da ponta da árvore, só a estrela fica; o jogo põe o brilho
        "clear_dark": [(686, 95, 62)],
        "allow": [(2393, 411, 89, 111), (2449, 511, 100, 112), (2516, 612, 100, 122), (2482, 712, 112, 101)],
        # comida: as plantinhas brancas (a neve é clara demais para achar sozinho)
        "food": [(1050, 1008), (1200, 1283), (1283, 1292), (1917, 983), (2133, 1183), (1750, 933),
                 (1592, 783), (600, 908), (2683, 883), (1900, 233), (1167, 233), (1350, 158)],
    },
}


def is_background(r, g, b):
    return max(r, g, b) <= 24


def is_snow(r, g, b):
    """Mapa de Natal: neve, gelo, trilhas, escadas e píer (claros); paredões e rochas
    são escuros."""
    return (r + g + b) / 3 >= 95 and b >= r - 6


def is_ice(r, g, b):
    """Gelo do lago: azulado e um pouco mais escuro que a neve em volta."""
    return (r + g + b) / 3 < 140 and b - r >= 38


GROUND_TESTS = {"grass": None, "snow": is_snow}
LAKE_TESTS = {"water": None, "ice": is_ice}


def is_ground(r, g, b):
    grass = g > r + 18 and g >= b - 14 and g > 55
    path = min(r, g, b) > 85 and max(r, g, b) - min(r, g, b) < 35
    return grass or path


def is_water(r, g, b):
    # água ~(30,55,75): bem mais azul que verde. Paredes ~(32,47,72) têm pouco verde;
    # a grama azulada da caverna ~(40,67,81) tem azul quase igual ao verde.
    return b > g + 16 and g > r + 15 and g < 72 and 40 < b < 115


def remove_background(src, tol=None):
    """tol=None: fundo = pixels bem escuros; tol=n: fundo = cor do canto (± n)."""
    W, H = src.get_size()
    rgb = pygame.image.tobytes(src, "RGB")
    if tol is not None:
        c0 = tuple(rgb[0:3])

        def is_background(r, g, b):     # noqa: F811 (só dentro desta chamada)
            return abs(r - c0[0]) <= tol and abs(g - c0[1]) <= tol and abs(b - c0[2]) <= tol
    else:
        is_background = globals()["is_background"]
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
    global CELL
    CELL = spec.get("cell", 4)
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
    ground, rgb = remove_background(src, spec.get("bg_tol") if spec.get("bg") == "corner" else None)
    for cx, cy, r in spec.get("clear_dark", []):     # discos escuros em volta de brilhos
        for yy in range(max(0, cy - top - r), min(H, cy - top + r + 1)):
            for xx in range(max(0, cx - r), min(W, cx + r + 1)):
                if (xx - cx) ** 2 + (yy - cy + top) ** 2 > r * r:
                    continue
                c = ground.get_at((xx, yy))
                ty = yy - (cy - top + 18)                  # abaixo da estrela: a árvore é um triângulo
                tree = ty > 0 and abs(xx - cx) < ty * 0.62 + 3
                if c.a and (c.r + c.g + c.b) / 3 < 150 and not tree:   # só a estrela e a árvore ficam
                    ground.set_at((xx, yy), (0, 0, 0, 0))
    pygame.image.save(ground, str(folder / "ground.png"))
    print(f"  ground.png: {W}x{H}")

    walk, gw, gh = grid_of(rgb, W, H, GROUND_TESTS.get(spec.get("ground", "grass")) or is_ground)
    walk = morph(morph(walk, gw, gh, CLOSE, True), gw, gh, CLOSE, False)
    walk = region(walk, gw, gh)
    walk = morph(walk, gw, gh, spec.get("margin", MARGIN), False)
    for bx, by, bw, bh in spec.get("block", []):
        for cy in range(max(0, (by - top) // CELL), min(gh, (by - top + bh) // CELL + 1)):
            for cx in range(max(0, bx // CELL), min(gw, (bx + bw) // CELL + 1)):
                walk[cy][cx] = False
    for bx, by, bw, bh in spec.get("allow", []):
        for cy in range(max(0, (by - top) // CELL), min(gh, (by - top + bh) // CELL + 1)):
            for cx in range(max(0, bx // CELL), min(gw, (bx + bw) // CELL + 1)):
                walk[cy][cx] = True
    wimg = save_grid(walk, gw, gh, folder / "walkable.png")

    lx, ly = spec["lake"]
    water, _, _ = grid_of(rgb, W, H, LAKE_TESTS.get(spec.get("lake_test", "water")) or is_water)
    water = morph(morph(water, gw, gh, CLOSE, True), gw, gh, CLOSE, False)   # fecha
    water = morph(morph(water, gw, gh, 2, False), gw, gh, 2, True)           # abre: corta pontes finas
    water = region(water, gw, gh, seed=(lx // CELL, (ly - top) // CELL))
    water = fill_holes(water, gw, gh)
    aimg = save_grid(water, gw, gh, folder / "water.png")
    print(f"  walkable.png / water.png: {gw}x{gh} (1 célula = {CELL}px)")

    # lago congelado: o gelo vira chão, ligado à margem (a folga da borda não pode separar)
    if spec.get("frozen"):                   # mapa que já é de inverno: o gelo já é chão
        save_grid(walk, gw, gh, folder / "walkable_frozen.png")
    else:
        raw, _, _ = grid_of(rgb, W, H, lambda r, g, b: is_ground(r, g, b) or is_water(r, g, b))
        near_lake = morph(water, gw, gh, MARGIN + 2, True)
        frozen = [[walk[y][x] or water[y][x] or (near_lake[y][x] and raw[y][x]) for x in range(gw)]
                  for y in range(gh)]
        frozen = region(frozen, gw, gh)
        save_grid(frozen, gw, gh, folder / "walkable_frozen.png")

    # outras épocas da mesma ilha: podem ter outra resolução (mesma proporção e posição);
    # recortadas pelo contorno da normal (com folga para a neve), suavizado na escala delas
    if spec.get("variants"):
        alpha = pygame.mask.from_surface(ground, 1)
        outline = alpha.convolve(pygame.mask.Mask((7, 7), fill=True))   # 3 px mais largo
        outline = outline.overlap_mask(outline, (0, 0))
        cut = pygame.Surface((W + 6, H + 6), pygame.SRCALPHA)
        cut.blit(outline.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(255, 255, 255, 0)), (0, 0))
        cut = cut.subsurface((3, 3, W, H)).copy()
        for vname, vsrc in spec["variants"].items():
            img = pygame.image.load(str(folder / vsrc)).convert_alpha()
            if top:
                k = img.get_height() / (H + top)
                img = img.subsurface((0, round(top * k), img.get_width(), img.get_height() - round(top * k))).copy()
            out = img.copy()
            out.blit(pygame.transform.smoothscale(cut, img.get_size()), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            pygame.image.save(out, str(folder / f"ground_{vname}.png"))
            print(f"  ground_{vname}.png")

    food = [tuple(p) for p in spec["food"]] if "food" in spec else food_spots(ground, walk, gw, gh)
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
