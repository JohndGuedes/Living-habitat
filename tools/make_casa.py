"""Prepara a área interna da casa (assets/sprites/world/areas/casa/) e as camas da biblioteca
(assets/sprites/world/library/casa/cama_azul.png e cama_vermelha.png).

Rode:  .venv\\Scripts\\python tools\\make_casa.py
"""
import json
import os
import shutil
from collections import deque
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CASA_DIR = ROOT / "assets" / "sprites" / "world" / "areas" / "casa"
LIB_CASA = ROOT / "assets" / "sprites" / "world" / "library" / "casa"


def build_room(src_path: Path):
    CASA_DIR.mkdir(parents=True, exist_ok=True)
    src_dir = CASA_DIR / "source"
    src_dir.mkdir(parents=True, exist_ok=True)
    local_src = src_dir / "ground.jpg"
    if src_path.resolve() != local_src.resolve():
        shutil.copy2(src_path, local_src)

    raw = pygame.image.load(str(local_src)).convert_alpha()
    w, h = raw.get_size()

    # 1) Máscara dos pixels não-pretos da casa (tudo com brilho > 14), apagando os 3 vagalumes soltos fora da casa
    non_black = pygame.Mask((w, h))
    for y in range(h):
        for x in range(w):
            c = raw.get_at((x, y))
            if max(c.r, c.g, c.b) > 14:
                non_black.set_at((x, y), 1)
    main_comp = max(non_black.connected_components(), key=lambda c: c.count())
    bbox = main_comp.get_bounding_rects()[0].inflate(8, 8).clip(pygame.Rect(0, 0, w, h))

    # 2) Preenche qualquer buraco interno da silhueta da casa (flood-fill do exterior do main_comp)
    # e expande 3px para preservar 100% do contorno preto externo original
    ext = pygame.Mask((w, h))
    q = deque()
    for x in range(w):
        q.append((x, 0))
        q.append((x, h - 1))
    for y in range(h):
        q.append((0, y))
        q.append((w - 1, y))
    while q:
        x, y = q.popleft()
        if ext.get_at((x, y)) or main_comp.get_at((x, y)):
            continue
        ext.set_at((x, y), 1)
        if x > 0:
            q.append((x - 1, y))
        if x + 1 < w:
            q.append((x + 1, y))
        if y > 0:
            q.append((x, y - 1))
        if y + 1 < h:
            q.append((x, y + 1))

    # Interior sólido = tudo que não é exterior; dilata 3px para incluir a linha preta de contorno
    solid = ext. callback if False else pygame.Mask((w, h), fill=True)
    solid.erase(ext, (0, 0))
    solid_surf = solid.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))
    dilated = pygame.Surface((w, h), pygame.SRCALPHA)
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            if dx * dx + dy * dy <= 10:
                dilated.blit(solid_surf, (dx, dy))

    room = raw.subsurface(bbox).copy()
    room.blit(dilated.subsurface(bbox), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    rw, rh = room.get_size()
    pygame.image.save(room, str(CASA_DIR / "ground.png"))

    # 3) Gera walkable.png (polígono isométrico do piso de madeira e lajotas, excluindo paredes e lareira)
    # Em coordenadas normalizadas (0..1) do recorte `room` (rw x rh):
    #   Topo do piso (canto entre as duas paredes): ~(0.50, 0.335)
    #   Canto esquerdo do piso (junto à parede esq.): ~(0.085, 0.585)
    #   Canto inferior do piso (frente): ~(0.495, 0.905)
    #   Canto direito do piso (junto à parede dir.): ~(0.885, 0.615)
    #   Recorte da lareira (saliente na parede esquerda): polígono que avança um pouco no piso
    walk = pygame.Surface((rw, rh))
    walk.fill((0, 0, 0))
    floor_poly = [
        (round(rw * 0.500), round(rh * 0.340)),   # canto norte do piso
        (round(rw * 0.875), round(rh * 0.612)),   # canto leste (perto da porta)
        (round(rw * 0.500), round(rh * 0.895)),   # canto sul
        (round(rw * 0.095), round(rh * 0.585)),   # canto oeste
    ]
    pygame.draw.polygon(walk, (255, 255, 255), floor_poly)

    # Bloqueia a base saliente da lareira na parede esquerda
    hearth_block = [
        (round(rw * 0.215), round(rh * 0.485)),
        (round(rw * 0.375), round(rh * 0.390)),
        (round(rw * 0.425), round(rh * 0.455)),
        (round(rw * 0.275), round(rh * 0.550)),
    ]
    pygame.draw.polygon(walk, (0, 0, 0), hearth_block)

    pygame.image.save(walk, str(CASA_DIR / "walkable.png"))
    (CASA_DIR / "meta.json").write_text(json.dumps({"food": []}, indent=2), encoding="utf-8")
    print(f"casa ground.png: {rw}x{rh} (recortado de {w}x{h} em {bbox})")


def build_beds(src_path: Path):
    LIB_CASA.mkdir(parents=True, exist_ok=True)
    raw = pygame.image.load(str(src_path)).convert_alpha()
    w, h = raw.get_size()

    # Remove fundo branco externo E frestas brancas (grades da cabeceira de ferro / vão sob a cama)
    # Nenhuma parte interna das camas é branco puro (> 244 nos 3 canais): o travesseiro é creme (~230, 223, 205).
    vis = bytearray(w * h)
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
        if vis[idx]:
            continue
        c = raw.get_at((x, y))
        if c.r < 238 or c.g < 238 or c.b < 238:
            continue
        vis[idx] = 1
        raw.set_at((x, y), (0, 0, 0, 0))
        if x > 0:
            q.append((x - 1, y))
        if x + 1 < w:
            q.append((x + 1, y))
        if y > 0:
            q.append((x, y - 1))
        if y + 1 < h:
            q.append((x, y + 1))

    # Também remove frestas brancas fechadas dentro da grade de ferro da cabeceira
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            idx = y * w + x
            if vis[idx]:
                continue
            c = raw.get_at((x, y))
            if c.r >= 242 and c.g >= 242 and c.b >= 242:
                vis[idx] = 1
                raw.set_at((x, y), (0, 0, 0, 0))

    # Suaviza a borda escura externa contra o fundo transparente
    for _pass in range(2):
        edge = []
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if vis[y * w + x] == 1:
                    continue
                c = raw.get_at((x, y))
                if c.a == 0:
                    continue
                if any(vis[ny * w + nx] == 1 for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))):
                    v = (c.r + c.g + c.b) // 3
                    if v > 155 and max(c.r, c.g, c.b) - min(c.r, c.g, c.b) < 22:
                        alpha = max(0, min(255, int((255 - v) * 2.1)))
                        edge.append((x, y, alpha))
        for x, y, alpha in edge:
            c = raw.get_at((x, y))
            if alpha < 25:
                vis[y * w + x] = 1
                raw.set_at((x, y), (0, 0, 0, 0))
            else:
                raw.set_at((x, y), (c.r // 3, c.g // 3, c.b // 3, alpha))

    m = pygame.mask.from_surface(raw, 20)
    rects = [r for r in m.get_bounding_rects() if r.w > 120 and r.h > 120]
    rects.sort(key=lambda r: r.x)
    names = ["cama_azul", "cama_vermelha"]
    for name, r in zip(names, rects):
        sub = raw.subsurface(r).copy()
        # Redimensiona para um tamanho proporcional ao mundo (~320px de largura na arte base)
        k = 320.0 / sub.get_width()
        scaled = pygame.transform.smoothscale_by(sub, k)
        out_path = LIB_CASA / f"{name}.png"
        pygame.image.save(scaled, str(out_path))
        print(f"  {out_path.relative_to(ROOT)}: {scaled.get_size()}")


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    room_src = Path(r"C:\Users\johng\.gemini\antigravity\brain\ab544670-eb25-4957-9637-ec596f82e37a\cottage_interior_ground_1794530551826.jpg")
    beds_src = Path(r"C:\Users\johng\.gemini\antigravity\brain\ab544670-eb25-4957-9637-ec596f82e37a\source_beds_1794530597340.jpg")
    build_room(room_src)
    build_beds(beds_src)


if __name__ == "__main__":
    main()
