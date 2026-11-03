"""Carregamento de sprites. Arquivo/pasta faltando nunca é erro: a animação
fica de fora (com aviso no terminal) e o jogo usa fallback/placeholder.
Precisa ser chamado DEPOIS de abrir a janela (convert_alpha exige o display)."""
import logging
import re
from pathlib import Path

import pygame

from .config import ROOT, SPRITES_DIR
from .spritesheet import SpriteSheet, _scale

log = logging.getLogger(__name__)


def _shown(path: Path):
    return path.relative_to(ROOT) if path.is_relative_to(ROOT) else path


def load_image(path: Path) -> pygame.Surface | None:
    if not path.exists():
        log.warning("não encontrado: %s", _shown(path))
        return None
    return pygame.image.load(path).convert_alpha()


def _common_opts(definition: dict, anim: dict) -> dict:
    return dict(
        frame_duration=anim.get("frame_duration", 0.12),
        loop=anim.get("loop", True),
        next_state=anim.get("next", "idle"),
        hop=anim.get("hop", 0),
        hit_frame=anim.get("hit_frame"),
        art_faces=anim.get("art_faces", definition.get("art_faces")),
    )


def load_sprite_set(definition: dict) -> dict[str, SpriteSheet]:
    """Carrega as animações de uma entrada de CHARACTER_SPRITES.
    Retorna {nome: SpriteSheet} só com as que existem."""
    if "frames_root" in definition:
        return _load_frame_folders(definition)

    folder = SPRITES_DIR / definition["folder"]
    sheets = {}
    for name, anim in definition["animations"].items():
        image = load_image(folder / anim["file"])
        if image is None:
            continue
        sheets[name] = SpriteSheet.from_grid(
            image, name, frames=anim["frames"], rows=anim.get("rows", 1),
            scale=definition.get("scale", 1), offset_y=anim.get("offset_y", 0),
            direction_order=anim.get("direction_order"), **_common_opts(definition, anim))
    return sheets


def _anim_files(root: Path, anim: dict) -> list[Path]:
    """PNGs de uma animação.
      "dir":   pasta (ou lista de pastas, tocadas em sequência)
      "files": prefixo de arquivo na própria raiz (ou lista), ex. "weaver_hornet_sew"
               -> weaver_hornet_sew0000.png, 0001... (só prefixo + número)
      "start"/"end": recorte (índices, end exclusivo); "reverse": de trás p/ frente;
      "pick": lista de índices escolhidos (aplicado por último; permite repetir)."""
    files = []
    if "dir" in anim:
        for d in anim["dir"] if isinstance(anim["dir"], list) else [anim["dir"]]:
            found = sorted((root / d).glob("*.png"))
            if not found:
                log.warning("pasta vazia ou não encontrada: %s", _shown(root / d))
            files += found
    if "files" in anim:
        for prefix in anim["files"] if isinstance(anim["files"], list) else [anim["files"]]:
            rx = re.compile(re.escape(prefix) + r"\d+\.png$")
            found = sorted(f for f in root.glob(prefix + "*.png") if rx.fullmatch(f.name))
            if not found:
                log.warning("nenhum quadro '%s*' em %s", prefix, _shown(root))
            files += found
    files = files[anim.get("start", 0):anim.get("end")]
    if anim.get("reverse"):
        files = files[::-1]
    if "pick" in anim:
        files = [files[i] for i in anim["pick"] if i < len(files)]
    return files


def _load_frame_folders(definition: dict) -> dict[str, SpriteSheet]:
    """Modo "pasta de frames": um PNG por quadro.

    align "union" (padrão — rips com tamanho de tela e posição constantes, como
    o Knight): todas as animações recortadas pelo mesmo retângulo, pés na base
    do 1º quadro de `anchor_anim` (padrão idle).

    align "per_anim" (sequências de origens diferentes, como Hornet/Grub): cada
    animação tem o próprio recorte; os pés ficam no centro-base do 1º quadro
    dela, ajustáveis por animação com "foot" (px da arte original para CIMA,
    p.ex. quando a agulha passa abaixo dos pés), "shift_x" e "scale" (multiplica
    a escala do personagem, para sequências desenhadas em outro tamanho).
    Quadros de tamanhos diferentes dentro da mesma animação são alinhados pela
    base-centro de cada um.

    "pivot": "center" (por animação): os pés ficam no CENTRO de cada imagem
    (quadros salvos assim por tools/extract_atlas.py, já alinhados entre si)."""
    root = SPRITES_DIR / definition["frames_root"]
    scale = definition.get("scale", 1)

    raw = {}
    for name, anim in definition["animations"].items():
        imgs = [pygame.image.load(f).convert_alpha() for f in _anim_files(root, anim)]
        if imgs:
            raw[name] = imgs
    if not raw:
        return {}

    def union_of(imgs):
        u = None
        for img in imgs:
            r = img.get_bounding_rect()
            if r.w:
                u = r if u is None else u.union(r)
        return u or pygame.Rect(0, 0, 1, 1)

    sheets = {}
    if definition.get("align", "union") == "union":
        union = union_of([img for imgs in raw.values() for img in imgs])
        anchor_imgs = raw.get(definition.get("anchor_anim", "idle")) or next(iter(raw.values()))
        feet = anchor_imgs[0].get_bounding_rect()
        anchor = ((feet.centerx - union.x) * scale, (feet.bottom - union.y) * scale)
        for name, imgs in raw.items():
            anim = definition["animations"][name]
            cells = [[_scale(img.subsurface(union), scale) for img in imgs]]
            sheets[name] = SpriteSheet(cells, name, anchor=anchor,
                                       source_size=imgs[0].get_size(), **_common_opts(definition, anim))
        return sheets

    for name, imgs in raw.items():
        anim = definition["animations"][name]
        foot, shift = anim.get("foot", 0), anim.get("shift_x", 0)
        if anim.get("pivot") == "center":  # pés no centro de cada imagem
            w, h = max(i.get_width() for i in imgs), max(i.get_height() for i in imgs)
            full = []
            for img in imgs:
                c = pygame.Surface((w, h), pygame.SRCALPHA)
                c.blit(img, ((w - img.get_width()) // 2, (h - img.get_height()) // 2))
                full.append(c)
            union = union_of(full)
            frames = [img.subsurface(union) for img in full]
            ax, ay = w // 2 - union.x + shift, h // 2 - union.y - foot
        elif len({img.get_size() for img in imgs}) == 1:
            union = union_of(imgs)
            feet = imgs[0].get_bounding_rect()
            frames = [img.subsurface(union) for img in imgs]
            ax, ay = feet.centerx - union.x + shift, feet.bottom - union.y - foot
        else:  # tamanhos diferentes: empilha pela base-centro de cada quadro
            rects = [img.get_bounding_rect() for img in imgs]
            w, h = max(r.w for r in rects), max(r.h for r in rects)
            frames = []
            for img, r in zip(imgs, rects):
                c = pygame.Surface((w, h), pygame.SRCALPHA)
                c.blit(img, ((w - r.w) // 2, h - r.h), r)
                frames.append(c)
            ax, ay = w / 2 + shift, h - foot
        k = scale * anim.get("scale", 1)  # "scale" na animação = ajuste extra (outra escala na origem)
        cells = [[_scale(f, k) for f in frames]]
        sheets[name] = SpriteSheet(cells, name, anchor=(ax * k, ay * k),
                                   source_size=imgs[0].get_size(), **_common_opts(definition, anim))
    return sheets


def load_prop_frames(kind: str, scale: float = 1, file: str | None = None) -> list[pygame.Surface] | None:
    """Arte de um objeto do cenário: `file` (caminho relativo a assets/sprites/)
    se dado; senão pasta assets/sprites/world/<kind>/ (quadros, em ordem
    alfabética) ou imagem assets/sprites/world/<kind>.png.
    None = não tem arte (o objeto usa o desenho provisório)."""
    if file:
        path = SPRITES_DIR / file
        if not path.exists():
            log.warning("não encontrado: %s", _shown(path))
            return None
        return [_scale(pygame.image.load(path).convert_alpha(), scale)]
    folder = SPRITES_DIR / "world" / kind
    files = sorted(folder.glob("*.png")) if folder.is_dir() else []
    if not files and (SPRITES_DIR / "world" / f"{kind}.png").exists():
        files = [SPRITES_DIR / "world" / f"{kind}.png"]
    if not files:
        return None
    return [_scale(pygame.image.load(f).convert_alpha(), scale) for f in files]
