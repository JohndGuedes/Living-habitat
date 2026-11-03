"""Recorta a folha do Grub (Spriters Resource) em pastas de frames.

Rode:  .venv\\Scripts\\python tools\\slice_grub.py
Fonte: assets/sprites/character/Grup/<a folha .png>
Saída: assets/sprites/character/Grup/frames/<animação>/000.png, 001.png, ...

A folha tem fundo azul-petróleo e cada quadro numa CAIXA BRANCA. As caixas
são achadas como regiões que não são a cor de fundo, agrupadas em linhas. O
branco de dentro da caixa é removido por balde de tinta a partir da borda da
caixa (o Grub tem contorno escuro, então o branco dos olhos fica).
"""
import os
from collections import deque
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / "assets" / "sprites" / "character" / "Grup"
OUT = FOLDER / "frames"

# linha(s) da folha -> nome da animação
ROWS = {
    "idle": [0],
    "cry": [1],
    "turn": [2],
    "freed": [3, 4],        # comemora, se enrola e se enterra
    "home_bounce": [5],
    "home_look": [6],
    "home_wave": [7, 8],
}


def boxes(sheet):
    bg = tuple(sheet.get_at((0, 0)))
    m = pygame.mask.from_threshold(sheet, bg, (6, 6, 6, 255))
    m.invert()
    rects = [r for r in m.get_bounding_rects() if r.w > 40 and r.h > 40]
    rows = []
    for r in sorted(rects, key=lambda r: r.y):
        if rows and abs(rows[-1][0].y - r.y) < 20:
            rows[-1].append(r)
        else:
            rows.append([r])
    return [sorted(row, key=lambda r: r.x) for row in rows]


def clear_white(img):
    """Fundo branco ligado à borda -> transparente (com franja suavizada)."""
    w, h = img.get_size()
    seen = [[False] * w for _ in range(h)]
    q = deque([(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)])
    while q:
        x, y = q.popleft()
        if not (0 <= x < w and 0 <= y < h) or seen[y][x]:
            continue
        r, g, b, a = img.get_at((x, y))
        if min(r, g, b) < 225:
            continue
        seen[y][x] = True
        img.set_at((x, y), (0, 0, 0, 0))
        q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    # franja: pixels muito claros encostados no fundo ficam semitransparentes
    for y in range(h):
        for x in range(w):
            if seen[y][x]:
                continue
            r, g, b, a = img.get_at((x, y))
            if min(r, g, b) > 190 and any(0 <= x + dx < w and 0 <= y + dy < h and seen[y + dy][x + dx]
                                          for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                img.set_at((x, y), (r, g, b, 110))
    return img


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    src = next(p for p in FOLDER.glob("*.png"))
    sheet = pygame.image.load(str(src)).convert_alpha()
    rows = boxes(sheet)
    for name, idxs in ROWS.items():
        folder = OUT / name
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob("*.png"):
            old.unlink()
        n = 0
        for i in idxs:
            for r in rows[i]:
                # 1px para dentro: tira a linha da borda da caixa
                img = clear_white(sheet.subsurface(r.inflate(-2, -2)).copy())
                pygame.image.save(img, str(folder / f"{n:03d}.png"))
                n += 1
        print(f"{name}: {n} quadros")


if __name__ == "__main__":
    main()
