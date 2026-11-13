"""Recorta as folhas walk.png e sentado.png do Hollow em pastas de quadros com fundo transparente.

Rode:  .venv\\Scripts\\python tools\\make_hollow.py
Fontes: assets/sprites/character/hollow/walk.png e sentado.png
Saída:  assets/sprites/character/hollow/frames/<animação>/000.png, 001.png, ...
"""
import os
from collections import deque
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / "assets" / "sprites" / "character" / "hollow"
OUT = FOLDER / "frames"

CANVAS_W, CANVAS_H = 200, 200
ANCHOR_X, ANCHOR_Y = 100, 194


def remove_white_background(sheet: pygame.Surface, keep_sigh_puff: bool = False) -> pygame.Surface:
    """Remove o fundo branco por flood-fill a partir das bordas e frestas entre as pernas,
    preservando o branco interno da máscara (cercado pelo contorno preto)."""
    sheet = sheet.copy()
    w, h = sheet.get_size()

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
        if c.r < 232 or c.g < 232 or c.b < 232:
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

    # Frestas brancas pequenas entre as pernas/braços (< 150 px), preservando o suspiro (💨)
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            idx = y * w + x
            if visited[idx]:
                continue
            c = sheet.get_at((x, y))
            if c.r > 235 and c.g > 235 and c.b > 235:
                pq = deque([(x, y)])
                visited[idx] = 2
                pts = []
                while pq:
                    px, py = pq.popleft()
                    pts.append((px, py))
                    for nx, ny in ((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)):
                        if 0 <= nx < w and 0 <= ny < h and not visited[ny * w + nx]:
                            nc = sheet.get_at((nx, ny))
                            if nc.r > 230 and nc.g > 230 and nc.b > 230:
                                visited[ny * w + nx] = 2
                                pq.append((nx, ny))
                if len(pts) < 150:
                    if keep_sigh_puff and any(260 <= px <= 285 and 290 <= py <= 315 for px, py in pts):
                        continue
                    for px, py in pts:
                        visited[py * w + px] = 1
                        sheet.set_at((px, py), (0, 0, 0, 0))

    # Suaviza a borda externa (pixels cinza-claros do anti-aliasing contra o fundo branco)
    for _pass in range(2):
        edge_pixels = []
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if visited[y * w + x] == 1:
                    continue
                c = sheet.get_at((x, y))
                if c.a == 0:
                    continue
                if any(visited[ny * w + nx] == 1 for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))):
                    v = (c.r + c.g + c.b) // 3
                    if v > 150 and max(c.r, c.g, c.b) - min(c.r, c.g, c.b) < 20:
                        alpha = max(0, min(255, int((255 - v) * 2.1)))
                        edge_pixels.append((x, y, alpha))
        for x, y, alpha in edge_pixels:
            c = sheet.get_at((x, y))
            if alpha < 25:
                visited[y * w + x] = 1
                sheet.set_at((x, y), (0, 0, 0, 0))
            else:
                sheet.set_at((x, y), (c.r // 3, c.g // 3, c.b // 3, alpha))

    return sheet


def extract_components(clean_sheet: pygame.Surface) -> list[tuple[pygame.Rect, pygame.Surface]]:
    """Extrai cada quadro isolando sua componente conexa (sem invadir quadros vizinhos)."""
    m = pygame.mask.from_surface(clean_sheet, 20)
    comps = m.connected_components()
    main = []
    small = []
    for comp in comps:
        r = comp.get_bounding_rects()[0]
        if r.w > 20 and r.h > 20:
            main.append([r, comp])
        elif r.w > 2 and r.h > 2:
            small.append((r, comp))

    for sr, scomp in small:
        if main:
            nearest = min(main, key=lambda item: (item[0].centerx - sr.centerx) ** 2 + (item[0].centery - sr.centery) ** 2)
            nearest[0] = nearest[0].union(sr)
            nearest[1].draw(scomp, (0, 0))

    main.sort(key=lambda item: (item[0].centery // 165, item[0].x))
    out = []
    for r, comp in main:
        sub = clean_sheet.subsurface(r).copy()
        sub_mask = pygame.Mask(r.size)
        sub_mask.draw(comp, (-r.x, -r.y))
        mask_surf = sub_mask.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))
        sub.blit(mask_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        out.append((r, sub))
    return out


def align_frame(r: pygame.Rect, sub: pygame.Surface, scale: float = 1.0,
                center_mode: str = "spine") -> pygame.Surface:
    """Centraliza o quadro em (CANVAS_W, CANVAS_H) com a base apoiada em ANCHOR_Y."""
    img = sub.copy()
    if abs(scale - 1.0) > 1e-3:
        img = pygame.transform.smoothscale_by(img, scale)
    sw, sh = img.get_size()
    if center_mode == "spine":
        # Usa o centro horizontal da máscara branca na metade superior quando em pé
        xs = [x for y in range(min(int(sh * 0.55), sh)) for x in range(sw)
              if img.get_at((x, y)).a > 160 and img.get_at((x, y)).r > 200]
        cx = round((min(xs) + max(xs)) / 2) if xs else sw // 2
    else:
        cx = sw // 2
    canvas = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
    dx = max(0, min(CANVAS_W - sw, ANCHOR_X - cx))
    dy = max(0, min(CANVAS_H - sh, ANCHOR_Y - sh))
    canvas.blit(img, (dx, dy))
    return canvas


def save_group(name: str, frames: list[pygame.Surface]):
    folder = OUT / name
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.png"):
        old.unlink()
    for n, frame in enumerate(frames):
        pygame.image.save(frame, str(folder / f"{n:03d}.png"))
    print(f"  {name}: {len(frames)} quadros")


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))

    sheets = {}
    for fn in ("walk.png", "sentado.png"):
        path = FOLDER / fn
        if not path.exists():
            continue
        raw = pygame.image.load(str(path)).convert_alpha()
        clean = remove_white_background(raw, keep_sigh_puff=True)
        items = extract_components(clean)
        sheets[len(items)] = (fn, items)
        print(f"{fn}: {len(items)} quadros detectados")

    if 48 not in sheets or 37 not in sheets:
        raise RuntimeError(f"Esperava folhas de 48 e 37 quadros, encontrei: {list(sheets.keys())}")

    _, w_items = sheets[48]
    _, s_items = sheets[37]

    # --- Folha de caminhada (48 quadros = 6 linhas x 8 colunas) ---
    walk_down = [align_frame(*w_items[i], scale=1.0, center_mode="spine") for i in range(0, 8)]
    walk_up = [align_frame(*w_items[i], scale=1.0, center_mode="spine") for i in range(8, 16)]
    walk_left = [align_frame(*w_items[i], scale=1.0, center_mode="spine") for i in range(16, 20)]
    walk_profile = [align_frame(*w_items[i], scale=1.0, center_mode="spine") for i in range(20, 24)]
    walk_right_34 = [align_frame(*w_items[i], scale=1.0, center_mode="spine") for i in range(35, 40)]
    walk_up_side = [align_frame(*w_items[i], scale=1.0, center_mode="spine") for i in range(44, 48)]

    # --- Folha sentado / deitando / dormindo / levantando (37 quadros) ---
    SIT_SCALE = 0.85
    sit_down = [
        align_frame(
            *s_items[i],
            scale=156.0 / max(156.0, s_items[i][0].h) if i < 3 else SIT_SCALE,
            center_mode="spine",
        )
        for i in range(0, 8)
    ]
    sit_loop = [align_frame(*s_items[i], scale=SIT_SCALE, center_mode="spine") for i in range(8, 12)]
    sit_to_lie = [align_frame(*s_items[i], scale=SIT_SCALE, center_mode="bbox") for i in range(12, 18)]
    sleep_loop = [align_frame(*s_items[i], scale=SIT_SCALE, center_mode="bbox") for i in range(18, 22)]
    lie_to_sit = [align_frame(*s_items[i], scale=SIT_SCALE, center_mode="bbox") for i in range(22, 29)]
    stand_up = [
        align_frame(
            *s_items[i],
            scale=156.0 / max(156.0, s_items[i][0].h) if i >= 33 else SIT_SCALE,
            center_mode="spine",
        )
        for i in range(29, 37)
    ]

    # Idle: postura em pé 3/4 (coerente com walk / sit_down / stand_up, art_faces="right")
    idle_frames = [sit_down[0], stand_up[7]]

    save_group("idle", idle_frames)
    save_group("walk", walk_right_34)
    save_group("walk_profile", walk_profile)
    save_group("walk_left", walk_left)
    save_group("walk_down", walk_down)
    save_group("walk_up", walk_up)
    save_group("walk_up_side", walk_up_side)
    save_group("sit_down", sit_down)
    save_group("sit", sit_loop)
    save_group("lie_down", [sit_down[1], sit_down[4], sit_down[7]] + sit_to_lie)
    save_group("sleep", sleep_loop)
    save_group("wake", lie_to_sit + [stand_up[2], stand_up[4], stand_up[6], stand_up[7]])
    save_group("stand_up", stand_up)


if __name__ == "__main__":
    main()
