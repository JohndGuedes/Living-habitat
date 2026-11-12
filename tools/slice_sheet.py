"""Recorta folhas de itens (fundo liso) em imagens soltas para a biblioteca do editor.

Rode:  .venv\\Scripts\\python tools\\slice_sheet.py [pasta_de_previa]

Cada entrada de SHEETS: folha -> pasta da biblioteca (assets/sprites/world/library/<nome>/).
  1) o fundo (a cor do canto da folha) é tirado por balde de tinta a partir das bordas
     e também nos "buracos" fechados (dentro da guirlanda, do braço do poste...);
  2) cada desenho vira uma região; pedaços muito próximos (a lanterna pendurada, os
     presentes empilhados, o fio do pisca-pisca) são juntados num item só;
  3) salva <pasta>/<nome>.png, recortado justo. NAMES dá nomes aos itens (na ordem de
     cima para baixo, esquerda para direita); os sem nome viram item_NN.
O editor de cenário (tecla O, depois L) mostra tudo que estiver em library/.
"""
import os
import sys
from collections import deque
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

SPRITES = Path(__file__).resolve().parent.parent / "assets" / "sprites"
LIBRARY = SPRITES / "world" / "library"

SHEETS = {
    "world/natal/assets terreno natal.png": "natal",
    "world/natal/arvores.png": "natal_2",
}
EDGE_TOL = 14      # diferença de cor aceita como fundo (a partir das bordas)
HOLE_TOL = 6       # mais rígido para buracos fechados (não comer pedra cinza)
JOIN = 5           # px: pedaços mais perto que isso viram o mesmo item
MIN_AREA = 120     # px²: menor que isso é sujeira

# nomes (na ordem dos itens achados; veja a prévia)
NAMES = {
    "natal": ["poste_guirlanda", "poste", "pilar_lanterna", "pilar_lanterna_2", "pedras_grandes",
              "presentes", "pedras_neve", "pedra_azevinho", "poste_curvo", "banco_neve", "pisca_pisca",
              "pedras_baixas", "guirlanda_pequena", "estatua_lanterna", "plantas_neve", "presentes_2",
              "pedras_longas", "guirlanda", "guirlanda_2"],
    # None = não vai para a biblioteca (a árvore de frutas e as cerejas são recortadas por
    # tools/make_fruit_tree.py, como animação)
    "natal_2": ["muro_pedra", "pedra_pequena", "pedras_altas", "pinheiro_enfeitado", None, None, None, None,
                None, None, None, None, "pedras_deitadas", "pedra_inclinada", "folhas_secas", "arbusto_neve",
                "arbusto_neve_2", "arbusto_escuro", "pedra_capim", None, None, None, "pedras_monte", "capim_gelo",
                "capim_gelo_2", "capim_gelo_3", "pedra_neve", None, None, None, "monte_terra", "monte_neve", None],
}


def close(c, bg, tol):
    return abs(c[0] - bg[0]) <= tol and abs(c[1] - bg[1]) <= tol and abs(c[2] - bg[2]) <= tol


def cut_background(src):
    W, H = src.get_size()
    rgb = pygame.image.tobytes(src, "RGB")
    bg = tuple(rgb[0:3])
    out = bytearray(W * H)            # 1 = fundo
    q = deque(list(range(W)) + [(H - 1) * W + x for x in range(W)]
              + [y * W for y in range(H)] + [y * W + W - 1 for y in range(H)])
    while q:
        i = q.popleft()
        if out[i] or not close(rgb[3 * i:3 * i + 3], bg, EDGE_TOL):
            continue
        out[i] = 1
        x, y = i % W, i // W
        if x > 0: q.append(i - 1)
        if x < W - 1: q.append(i + 1)
        if y > 0: q.append(i - W)
        if y < H - 1: q.append(i + W)
    rgba = bytearray(W * H * 4)
    for i in range(W * H):
        if out[i] or close(rgb[3 * i:3 * i + 3], bg, HOLE_TOL):
            continue
        rgba[4 * i:4 * i + 3] = rgb[3 * i:3 * i + 3]
        rgba[4 * i + 3] = 255
    return pygame.image.frombytes(bytes(rgba), (W, H), "RGBA")


def items(img):
    """Retângulos dos itens: os desenhos são "engordados" JOIN/2 px; pedaços que se
    tocam assim (a lanterna e o poste, os presentes) viram um item só."""
    mask = pygame.mask.from_surface(img, 1)
    r = JOIN // 2
    fat = mask.convolve(pygame.mask.Mask((2 * r + 1, 2 * r + 1), fill=True))
    rects = []
    for comp in fat.connected_components(MIN_AREA):
        box = comp.get_bounding_rects()[0].move(-r, -r)
        box = box.clip(img.get_rect())
        area = mask.overlap_area(pygame.mask.Mask(box.size, fill=True), box.topleft)
        if area >= MIN_AREA:
            sub = img.subsurface(box)
            rects.append(sub.get_bounding_rect().move(box.topleft))
    return sorted(rects, key=lambda r: (r.y // 120, r.x))


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    preview = sys.argv[1] if len(sys.argv) > 1 else None
    for sheet, name in SHEETS.items():
        img = cut_background(pygame.image.load(str(SPRITES / sheet)).convert())
        folder = LIBRARY / name
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob("*.png"):
            if not old.name.startswith(("boneco_", "fogueira", "lenha_neve", "espeto_fogueira", "grub_natal")):
                old.unlink()
        rects = items(img)
        names = NAMES.get(name, [])
        for n, r in enumerate(rects):
            label = names[n] if n < len(names) else f"item_{n + 1:02d}"
            if label is None:
                continue
            pygame.image.save(img.subsurface(r).copy(), str(folder / f"{label}.png"))
        print(f"{name}: {len(rects)} itens")
        if preview:
            p = pygame.Surface(img.get_size())
            p.fill((200, 90, 160))
            p.blit(img, (0, 0))
            font = pygame.font.SysFont("arial", 16, bold=True)
            for n, r in enumerate(rects):
                pygame.draw.rect(p, (255, 255, 0), r, 1)
                p.blit(font.render(str(n), True, (255, 255, 0), (0, 0, 0)), r.topleft)
            pygame.image.save(p, str(Path(preview) / f"lib_{name}.png"))


if __name__ == "__main__":
    main()
