"""Tira quadros escolhidos de atlas compactados do jogo para pastas de frames.

Rode:  .venv\\Scripts\\python tools\\extract_atlas.py

Os atlas do Hollow Knight/Silksong vêm compactados (quadros fora de ordem,
alguns girados, sem lista de onde está cada um). Aqui cada desenho é achado
como região conectada de pixels visíveis e escolhido pelo ÍNDICE: ordem de
cima para baixo em faixas de `band` px, depois da esquerda para a direita
(mesma numeração das prévias usadas para escolher).

Cada entrada de EXTRACTS: (atlas, alpha mínimo, área mínima, band, {pasta_saída: [índices]}, opções)
Caminhos relativos a assets/sprites/. Opções (dict, opcional):
  "unrotate"  desvira os quadros guardados deitados no atlas (girados 90° no
              sentido horário: a cabeça fica à DIREITA do vestido). Detecta
              pela posição da cabeça (branco) em relação ao vestido (vinho).
  "pivot"     salva cada quadro numa tela de tamanho fixo com os PÉS no
              CENTRO (use "pivot": "center" no sprite_def). Valores:
              "register" = loops (idle, andar...): alinha cada quadro ao anterior
                           pela maior sobreposição, e os pés vêm do 1º quadro;
              "each"     = cada quadro acha os próprios pés (pulo, poses diferentes).
  Sem "pivot", o quadro é salvo recortado, como sai do atlas.
Os índices estão na ORDEM da animação (achada por semelhança entre os quadros,
porque a ordem original se perde no atlas).
"""
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

SPRITES = Path(__file__).resolve().parent.parent / "assets" / "sprites"

MAIN = "character/Hornet/Hornet main sprites - atlas2 #34870.png"
NEEDOLIN = "character/Hornet/Hornet needolin - atlas0 #34857.png"

EXTRACTS = [
    # Hornet sentada no banco (de frente, agulha no colo)
    ("character/Hornet/Hornet sitting - atlas0 #92576.png", 40, 2000, 80,
     {"character/Hornet/frames/bench_sit": [17, 18]}),
    # A Sombra flutuando (em pé, base esfiapada)
    ("character/NPCs/atlas0 #10777.png", 60, 3000, 80,
     {"character/Shade/frames/idle": [15, 16, 23, 24, 31, 51]}),
    # Hornet: parada, andando, correndo e pulando (atlas principal)
    (MAIN, 40, 1500, 80, {
        "character/Hornet/frames/idle": [
            253, 261, 346, 348, 349, 321, 312, 296, 285, 286, 330, 331, 329, 427, 391, 392,
            387, 389, 399, 414, 383, 425, 351, 429, 428, 422, 408, 397, 411, 385, 416, 415,
            400, 413, 386, 384, 382, 377, 338, 360, 361, 367, 339, 376, 374, 366, 365, 337,
            336, 356, 358, 340, 355, 359, 341, 345, 313, 319, 325, 230, 222, 276, 347, 283],
        "character/Hornet/frames/walk": [0, 83, 214, 247, 305, 196, 213, 154, 438, 388, 41, 1],
        "character/Hornet/frames/run": [
            189, 161, 129, 229, 250, 251, 235, 193, 211, 258, 257, 216, 227, 217, 182, 192,
            191, 131, 130],
        # pulo: subindo (agulha para baixo) / agachada (impulso e pouso)
        "character/Hornet/frames/jump_up": [4, 118, 86, 87, 88, 90, 111, 100, 109, 124, 102],
        "character/Hornet/frames/crouch": [353, 352, 421, 407, 307, 375, 274, 335],
    }, {"unrotate": True, "pivot": "register"}),
    # Hornet tocando a agulha como instrumento (needolin)
    (NEEDOLIN, 40, 2000, 80, {
        "character/Hornet/frames/needolin": [45, 49, 48, 56, 55, 51, 54, 57, 47, 50, 52, 46],
    }, {"unrotate": True, "pivot": "register"}),
]


def components(atlas, alpha, min_area, band):
    mask = pygame.mask.from_surface(atlas, alpha)
    rects = [r for r in mask.get_bounding_rects() if r.w * r.h > min_area]
    return sorted(rects, key=lambda r: (r.y // band, r.x))


# ---------------------------------------------------------------- orientação
def _centroid(img, test, step=2):
    w, h = img.get_size()
    sx = sy = n = 0
    for y in range(0, h, step):
        for x in range(0, w, step):
            c = img.get_at((x, y))
            if c.a > 200 and test(c):
                sx += x
                sy += y
                n += 1
    return (sx / n, sy / n, n) if n else None


def _white(c):
    return c.r > 220 and c.g > 220 and c.b > 220


def _dress(c):
    return c.r > 90 and c.g < 80 and c.b < 90 and c.r > c.g + 30


def is_rotated(img) -> bool:
    """Deitado no atlas = a cabeça está à direita do vestido (e não acima)."""
    import math
    head, body = _centroid(img, _white), _centroid(img, _dress)
    if not head or not body or head[2] < 40 or body[2] < 40:
        return False
    ang = math.degrees(math.atan2(body[1] - head[1], head[0] - body[0]))  # 90 = cabeça em cima
    return -40 < ang < 45


# ---------------------------------------------------------------- pés / alinhamento
def feet(img):
    """Pés: x = centro do vestido; y = ponto visível mais baixo perto desse x."""
    body = _centroid(img, _dress) or (img.get_width() / 2, 0, 1)
    fx = round(body[0])
    w, h = img.get_size()
    for y in range(h - 1, -1, -1):
        for x in range(max(0, fx - 18), min(w, fx + 19)):
            if img.get_at((x, y)).a > 120:
                return fx, y + 1
    return fx, h


def register(prev_mask, prev_pos, img):
    """Posição de `img` que mais se sobrepõe ao quadro anterior."""
    m = pygame.mask.from_surface(img, 120)
    pw, ph = prev_mask.get_size()
    w, h = img.get_size()
    # começa alinhando a base-centro e procura em volta (grosso, depois fino)
    bx, by = prev_pos[0] + (pw - w) // 2, prev_pos[1] + ph - h
    best, best_xy = -1, (bx, by)
    for step, rng, cx, cy in ((4, 48, bx, by), (1, 4, None, None)):
        if cx is None:
            cx, cy = best_xy
        for dy in range(-rng, rng + 1, step):
            for dx in range(-rng, rng + 1, step):
                x, y = cx + dx, cy + dy
                a = prev_mask.overlap_area(m, (x - prev_pos[0], y - prev_pos[1]))
                if a > best:
                    best, best_xy = a, (x, y)
    return m, best_xy


def place(imgs, mode):
    """Coloca os quadros em telas iguais com os pés no centro."""
    if mode == "register":
        pos = [(0, 0)]
        mask = pygame.mask.from_surface(imgs[0], 120)
        for img in imgs[1:]:
            mask, p = register(mask, pos[-1], img)
            pos.append(p)
        fx, fy = feet(imgs[0])
        pivots = [(fx, fy)] * len(imgs)        # os pés do 1º, no espaço comum
    else:  # "each"
        pos = [(0, 0)] * len(imgs)
        pivots = [feet(img) for img in imgs]
    # extensão em volta dos pés (simétrica, para o pé ficar no centro)
    ex = ey = 0
    for img, (px, py), (fx, fy) in zip(imgs, pos, pivots):
        w, h = img.get_size()
        ex = max(ex, abs(px - fx), abs(px + w - fx))
        ey = max(ey, abs(py - fy), abs(py + h - fy))
    out = []
    for img, (px, py), (fx, fy) in zip(imgs, pos, pivots):
        c = pygame.Surface((2 * ex, 2 * ey), pygame.SRCALPHA)
        c.blit(img, (ex + px - fx, ey + py - fy))
        out.append(c)
    return out


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    for entry in EXTRACTS:
        atlas_path, alpha, area, band, outputs = entry[:5]
        opts = entry[5] if len(entry) > 5 else {}
        atlas = pygame.image.load(str(SPRITES / atlas_path)).convert_alpha()
        rects = components(atlas, alpha, area, band)
        for out, idxs in outputs.items():
            imgs = []
            for i in idxs:
                img = atlas.subsurface(rects[i]).copy()
                if opts.get("unrotate") and is_rotated(img):
                    img = pygame.transform.rotate(img, 90)   # desfaz o giro horário
                imgs.append(img)
            if opts.get("pivot"):
                imgs = place(imgs, opts["pivot"])
            folder = SPRITES / out
            folder.mkdir(parents=True, exist_ok=True)
            for old in folder.glob("*.png"):
                old.unlink()
            for n, img in enumerate(imgs):
                pygame.image.save(img, str(folder / f"{n:03d}.png"))
            print(f"{out}: {len(imgs)} quadros")


if __name__ == "__main__":
    main()
