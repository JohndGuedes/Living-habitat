"""Gera os quadros de uma "skin" a partir dos quadros do Knight.

Rode:  .venv\\Scripts\\python tools\\make_skin.py

A pasta character/daughter_of_hollownest/ é uma skin: Knight.png tem exatamente a
disposição do atlas original do jogo (the_knight/Knight_full_0.png), só com a arte
trocada. Como cada quadro do Knight (the_knight/<animação>/*.png, tela de 349x186)
saiu desse atlas, dá para achar onde ele está lá e recortar o MESMO lugar da skin:

  1) para cada quadro, recorta a parte visível e testa as 8 orientações possíveis
     (o atlas guarda quadros girados). Em cada uma, pega uma tira de pixels bem
     variada e procura essa sequência nos bytes do atlas; cada achado é conferido
     comparando as cores do desenho inteiro;
  2) recorta esse retângulo do Knight.png da skin, desfaz o giro e cola na mesma
     posição da tela do quadro;
  3) salva em <skin>/frames/<animação>/<mesmo nome>.png.

Assim a personagem tem as mesmas animações do Knight (o sprite_def é o mesmo, só
muda o frames_root). Os outros PNGs da skin (Hornet, Quirrel, feitiços...) não são
quadros dela e não entram aqui.
"""
import os
import shutil
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent / "assets" / "sprites" / "character"
VANILLA = ROOT / "the_knight"
ATLAS = VANILLA / "Knight_full_0.png"
SKIN_DIR = ROOT / "daughter_of_hollownest"
SKIN = SKIN_DIR / "Knight.png"
OUT = SKIN_DIR / "frames"

STRIP = 8           # largura da tira procurada (px)
MAX_TRIES = 40      # achados a conferir por tira


def orientations(img):
    """As 8 orientações: [(rot, flip, imagem)]; rot em graus (sentido anti-horário)."""
    out = []
    for flip in (False, True):
        base = pygame.transform.flip(img, False, True) if flip else img
        for rot in (0, 90, 270, 180):
            out.append((rot, flip, pygame.transform.rotate(base, rot) if rot else base))
    return out


def undo(img, rot, flip):
    """Desfaz o que orientations() fez."""
    if rot:
        img = pygame.transform.rotate(img, -rot)
    if flip:
        img = pygame.transform.flip(img, False, True)
    return img


def color_score(atlas, img, pos, step=2):
    """Fração de pixels visíveis com a mesma cor no atlas (amostrado)."""
    w, h = img.get_size()
    same = total = 0
    for y in range(0, h, step):
        for x in range(0, w, step):
            c = img.get_at((x, y))
            if c.a < 40:
                continue
            a = atlas.get_at((pos[0] + x, pos[1] + y))
            total += 1
            same += abs(a.r - c.r) < 12 and abs(a.g - c.g) < 12 and abs(a.b - c.b) < 12 and abs(a.a - c.a) < 40
    return same / total if total else 0.0


def best_strips(img, how_many=4):
    """Tiras horizontais opacas com mais cores diferentes: [(x, y, bytes)]."""
    w, h = img.get_size()
    if w < STRIP:
        return []
    data = pygame.image.tobytes(img, "RGBA")
    found = []
    for y in range(0, h, max(1, h // 24)):
        for x in range(0, w - STRIP + 1, max(1, STRIP // 2)):
            raw = data[(y * w + x) * 4:(y * w + x + STRIP) * 4]
            pixels = {raw[i:i + 4] for i in range(0, len(raw), 4)}
            alpha = min(raw[3::4])
            if alpha < 30 or len(pixels) < 3:      # (efeitos são semitransparentes)
                continue
            found.append((alpha >= 250, len(pixels), x, y, raw))
    found.sort(key=lambda s: (-s[0], -s[1]))
    return [(x, y, raw) for _, _, x, y, raw in found[:how_many]]


class Finder:
    def __init__(self, atlas):
        self.atlas = atlas
        self.w, self.h = atlas.get_size()
        self.data = pygame.image.tobytes(atlas, "RGBA")

    def _search(self, img, strip):
        """Todas as posições onde o desenho está no atlas, a partir de uma tira."""
        sx, sy, raw = strip
        iw, ih = img.get_size()
        start, tries = 0, 0
        while tries < MAX_TRIES:
            i = self.data.find(raw, start)
            if i < 0:
                return
            start = i + 1
            if i % 4:
                continue
            tries += 1
            y, x = divmod(i // 4, self.w)
            pos = (x - sx, y - sy)
            if pos[0] < 0 or pos[1] < 0 or pos[0] + iw > self.w or pos[1] + ih > self.h:
                continue
            if color_score(self.atlas, img, pos) > 0.97:
                yield pos

    def find(self, crop, skin):
        """Acha o quadro no atlas e devolve o pedaço da skin já desvirado.
        O atlas guarda alguns desenhos duplicados e a skin pode ter pintado só um:
        se o pedaço achado ainda é igual ao original, continua procurando uma cópia
        pintada (e fica com a mais diferente do original)."""
        best, best_same, seen = None, 2.0, set()
        for rot, flip, img in orientations(crop):
            for strip in best_strips(img):
                for pos in self._search(img, strip):
                    if (pos, rot, flip) in seen:
                        continue
                    seen.add((pos, rot, flip))
                    piece = undo(skin.subsurface(pygame.Rect(pos, img.get_size())).copy(), rot, flip)
                    same = similarity(piece, crop)
                    if same < 0.85:
                        return piece
                    if same < best_same:
                        best, best_same = piece, same
        return best


def similarity(piece, ref, step=2):
    """Fração dos pixels visíveis do original que continuam iguais em `piece`."""
    w, h = ref.get_size()
    same = total = 0
    for y in range(0, h, step):
        for x in range(0, w, step):
            c = ref.get_at((x, y))
            if c.a < 40:
                continue
            p = piece.get_at((x, y))
            total += 1
            same += abs(p.r - c.r) < 12 and abs(p.g - c.g) < 12 and abs(p.b - c.b) < 12 and abs(p.a - c.a) < 40
    return same / total if total else 0.0


def fill_gaps(files, folder):
    """Quadro sem par numa animação quase completa: repete o vizinho da skin, para a
    animação manter o número de quadros (e não misturar arte do Knight)."""
    have = [(folder / f.name).exists() for f in files]
    if not any(have) or sum(have) * 2 < len(files):
        return
    for i, f in enumerate(files):
        if have[i]:
            continue
        near = min((j for j in range(len(files)) if have[j]), key=lambda j: abs(j - i))
        shutil.copy(folder / files[near].name, folder / f.name)
        print(f"  preenchido com o vizinho: {f.name}")


def replace_unpainted(files, folder, limit=0.6):
    """O autor da skin deixou alguns quadros quase sem pintar (acima de `limit` iguais
    ao Knight; os pintados ficam bem abaixo): repete o vizinho pintado, para não
    aparecer um clarão do Knight no meio da animação."""
    painted = []
    for f in files:
        target = folder / f.name
        if not target.exists():
            painted.append(False)
            continue
        a = pygame.image.load(str(f)).convert_alpha()
        box = a.get_bounding_rect()
        b = pygame.image.load(str(target)).convert_alpha()
        painted.append(not box.w or similarity(b.subsurface(box), a.subsurface(box)) < limit)
    if not any(painted):
        return
    for i, f in enumerate(files):
        if not painted[i] and (folder / f.name).exists():
            near = min((j for j in range(len(files)) if painted[j]), key=lambda j: abs(j - i))
            shutil.copy(folder / files[near].name, folder / f.name)
            print(f"  sem pintura na skin, usei o vizinho: {f.name}")


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    atlas = pygame.image.load(str(ATLAS)).convert_alpha()
    skin = pygame.image.load(str(SKIN)).convert_alpha()
    finder = Finder(atlas)
    folders = sorted({f.parent for f in VANILLA.rglob("*.png") if f.parent != VANILLA})
    total = done = empty = 0
    missing = []
    for folder in folders:
        rel = folder.relative_to(VANILLA)
        (OUT / rel).mkdir(parents=True, exist_ok=True)
        ok = 0
        files = sorted(folder.glob("*.png"))
        for f in files:
            total += 1
            img = pygame.image.load(str(f)).convert_alpha()
            box = img.get_bounding_rect()
            target = OUT / rel / f.name
            if box.w == 0:
                empty += 1
                ok += 1
                pygame.image.save(pygame.Surface(img.get_size(), pygame.SRCALPHA), str(target))
                continue
            crop = img.subsurface(box).copy()
            if target.exists():                     # já gerado: só refaz se ficou igual ao Knight
                old = pygame.image.load(str(target)).convert_alpha()
                if similarity(old.subsurface(box), crop) < 0.85:
                    done += 1
                    ok += 1
                    continue
            piece = finder.find(crop, skin)
            if piece is None:
                if rel.parts[0] == "_ effects":     # brilhos brancos: usa o efeito original
                    shutil.copy(f, target)
                    ok += 1
                missing.append(str(rel / f.name))
                continue
            out = pygame.Surface(img.get_size(), pygame.SRCALPHA)
            out.blit(piece, box.topleft)
            pygame.image.save(out, str(target))
            done += 1
            ok += 1
        fill_gaps(files, OUT / rel)
        if not rel.parts[0].startswith("_"):      # (efeitos e sobras podem ser iguais mesmo)
            replace_unpainted(files, OUT / rel)
        print(f"{rel}: {ok}/{len(files)}", flush=True)
    print(f"\nquadros: {total}  gerados: {done}  vazios: {empty}  sem par no atlas: {len(missing)}")
    for m in missing:
        print("  faltou:", m)


if __name__ == "__main__":
    main()
