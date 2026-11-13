"""Editor de cenário: colocar, mover, redimensionar e remover objetos dentro do jogo e
salvar como padrão.

Tecla O liga/desliga. Com o editor ligado (os personagens ficam parados):
  L                      abre/fecha a BIBLIOTECA (itens de assets/sprites/world/library/);
                         clique num item para colocá-lo na ilha (roda do mouse rola a lista)
  clicar e arrastar      move o objeto
  roda do mouse / + -    tamanho
  setas                  ajuste fino (Shift = 10x)
  Tab                    próximo objeto
  Delete                 remove o objeto selecionado
  F ou H                 inverte horizontalmente (espelhar esquerda/direita)
  K                      sólido / atravessável (se bloqueia a passagem)
  Backspace              volta o objeto ao que está em scene.py (só os de lá)
  Ctrl+S ou Enter        salva em layout.json (vira o padrão ao abrir o jogo)
  O ou Esc               sai (sem salvar, as mudanças valem só até fechar o jogo)

layout.json (raiz do projeto) guarda a lista COMPLETA de objetos de cada área, separada
por estação ("lago@natal", "lago@normal"): a decoração de Natal fica só no Natal.
O World carrega isso por cima de scene.py (world.load_layout).

Biblioteca: cada pasta em library/ é um conjunto (ex.: natal, gerado por
tools/slice_sheet.py); qualquer PNG que estiver lá aparece. Itens cujo nome começa com
"banco" viram bancos de verdade (dá para sentar).
"""
import json
import logging

import pygame

from .config import SPRITES_DIR
from .props import make_prop
from .scene import AREAS
from .world import LAYOUT_FILE, layout_key

log = logging.getLogger(__name__)

LIBRARY = SPRITES_DIR / "world" / "library"
ITEM_SCALE = 0.3          # tamanho inicial dos itens da biblioteca (relativo à ilha)
PANEL_W = 300
CELL = 92

HELP = ("EDITOR | arrastar: mover | roda, + -: tamanho | setas: ajuste (Shift x10) | F/H: inverter | Tab: próximo | "
        "Del: remover | K: sólido | L: biblioteca | Ctrl+S/Enter: salvar | O/Esc: sair")


def library_items():
    """[(conjunto, nome, caminho relativo a sprites/)] de tudo que está em library/."""
    out = []
    if LIBRARY.exists():
        for folder in sorted(p for p in LIBRARY.iterdir() if p.is_dir()):
            for f in sorted(folder.glob("*.png")):
                out.append((folder.name, f.stem, f.relative_to(SPRITES_DIR).as_posix()))
    return out


class Editor:
    def __init__(self, game):
        self.game = game
        self.active = False
        self.sel = 0
        self.drag = None        # deslocamento (dx, dy) do mouse até a base do objeto
        self.dirty = False
        self.font = pygame.font.Font(None, 24)
        self.small = pygame.font.Font(None, 18)
        self.panel = False      # biblioteca aberta
        self.scroll = 0
        self._items = None      # [(conjunto, nome, arquivo, miniatura)]

    # ---------- ligar / desligar ----------
    def toggle(self):
        g = self.game
        self.active = not self.active
        if self.active:
            for ch in g.characters:           # ninguém sentado/andando enquanto edita
                ch.brain._drop_task()
                ch.brain.leave_bench()
                ch.brain.leave_bed()
                ch.brain.task_name = "editor"
                if ch.state not in ("sleep", "lie_down"):
                    ch.state = "idle"
            self.sel = min(self.sel, max(0, len(self.world.props) - 1))
            g.show(f"editor de cenário ligado  (estação: {self.world.season})")
        else:
            self.drag = None
            self.panel = False
            self.world.build_nav(g.character.feet_rect)   # colisões novas
            for ch in g.characters:
                ch.brain.task_name = "-"
                ch.brain.__dict__.pop("_spots_cache", None)
                if self.world.blocked(ch.feet_rect()):
                    ch.x, ch.y = self.world.nav_point((ch.x, ch.y))
            g.show("editor desligado" + ("  (não salvo!)" if self.dirty else ""))

    @property
    def world(self):
        return self.game.world

    # ---------- objetos ----------
    def _rect(self, p):
        img = p.image()
        return img.get_rect(midbottom=(round(p.x), round(p.y + p.base_offset)))

    def _rebuild(self, i):
        """Recria o objeto i a partir da definição (posição/tamanho novos)."""
        w = self.world
        w.props[i] = make_prop(w._place(w.prop_defs[i]))
        w.props[i].world = w

    def _to_img(self, x, y):
        w = self.world
        return (round((x - w.ground_pos[0]) / w.k, 1), round((y - w.ground_pos[1]) / w.k, 1))

    def _move(self, i, x, y):
        """Base do objeto i para (x, y) de tela."""
        self.world.prop_defs[i]["img_pos"] = self._to_img(x, y)
        self._rebuild(i)
        self.dirty = True

    def _scale(self, i, factor):
        d = self.world.prop_defs[i]
        d["scale"] = round(max(0.05, min(5.0, d.get("scale", 1) * factor)), 3)
        self._rebuild(i)
        self.dirty = True

    def _reset(self, i):
        w = self.world
        scene = w.spec.get("props", AREAS[w.name].get("props", []))
        if i < len(scene) and scene[i]["kind"] == w.prop_defs[i]["kind"] \
                and scene[i].get("file") == w.prop_defs[i].get("file"):
            w.prop_defs[i] = dict(scene[i])
            self._rebuild(i)
            self.dirty = True
        else:
            self.game.show("esse objeto não está em scene.py")

    def _remove(self, i):
        w = self.world
        del w.prop_defs[i]
        del w.props[i]
        self.sel = max(0, min(self.sel, len(w.props) - 1))
        self.dirty = True

    def _toggle_solid(self, i):
        d = self.world.prop_defs[i]
        solid = not (d.get("solid", True) and tuple(d.get("footprint", (1, 1)))[0] != 0)
        d["solid"] = solid
        d.pop("footprint", None)
        if not solid:
            d["footprint"] = (0, 0)
        self._rebuild(i)
        self.dirty = True
        self.game.show("sólido (bloqueia)" if solid else "atravessável")

    def _toggle_flip(self, i):
        d = self.world.prop_defs[i]
        flipped = not bool(d.get("flip", False))
        if flipped:
            d["flip"] = True
        else:
            d.pop("flip", None)
        self._rebuild(i)
        self.dirty = True
        self.game.show("invertido horizontalmente" if flipped else "orientação original")

    def add(self, name, file, at=None):
        """Coloca um item da biblioteca (no meio da tela, ou em `at`)."""
        w = self.world
        x, y = at or (self.game.screen.get_width() / 2 - PANEL_W / 2, self.game.screen.get_height() * 0.55)
        d = {"kind": "item", "file": file, "img_pos": self._to_img(x, y), "scale": ITEM_SCALE, "name": name}
        if name.startswith("banco"):          # banco da biblioteca: dá para sentar
            d.update(kind="bench", seats_rel=[-0.2, 0.2], approach_rel=0.4)
        elif name.startswith("arvore_frutas"):  # árvore de frutas: comida (bater -> fruta cai)
            d.update(kind="fruit_tree", scale=1.2)
        elif name.startswith("pinheiro"):       # pinheiro enfeitado: também dá fruta
            d.update(kind="fruit_tree", scale=1.0)
        elif name.startswith("boneco_zote"):    # boneco de treino
            d.update(kind="zote", scale=1.0)
        elif name.startswith("boneco_neve"):    # boneco de neve (bater / montar)
            d.update(kind="snowman", scale=1.0)
        elif name.lower().startswith("fogueira"):  # fogueira (acender / apagar / luz)
            d.update(kind="campfire", scale=0.9)
        elif name.lower().startswith(("grub_natal", "group-natal", "group_natal")):
            d.update(kind="grub_natal", scale=0.85)
        elif name.lower().startswith("cama"):
            d.update(kind="bed", scale=0.54, approach_rel=0.20)
        w.prop_defs.append(d)
        w.props.append(make_prop(w._place(d)))
        w.props[-1].world = w
        self.sel = len(w.props) - 1
        self.dirty = True
        self.game.show(f"colocado: {name}  (arraste para posicionar)")

    # ---------- biblioteca ----------
    def _library(self):
        if self._items is None:
            self._items = []
            for group, name, file in library_items():
                path = SPRITES_DIR / file
                try:
                    img = pygame.image.load(str(path)).convert_alpha()
                except (pygame.error, OSError) as exc:
                    log.warning("não foi possível carregar item da biblioteca %s: %s", file, exc)
                    continue
                k = min((CELL - 10) / img.get_width(), (CELL - 22) / img.get_height(), 1.0)
                self._items.append((group, name, file, pygame.transform.smoothscale_by(img, k)))
        return self._items

    def _panel_rect(self):
        s = self.game.screen
        return pygame.Rect(s.get_width() - PANEL_W, 0, PANEL_W, s.get_height() - 60)

    def _cells(self):
        """[(retângulo, item)] das miniaturas visíveis, com títulos por conjunto."""
        r = self._panel_rect()
        cols = PANEL_W // CELL
        out, titles, y, col, group = [], [], r.y + 36 - self.scroll, 0, None
        for it in self._library():
            if it[0] != group:
                if col:
                    y += CELL
                group, col = it[0], 0
                titles.append((group, y))
                y += 22
            out.append((pygame.Rect(r.x + 6 + col * CELL, y, CELL - 4, CELL - 4), it))
            col += 1
            if col == cols:
                col, y = 0, y + CELL
        return out, titles

    # ---------- eventos ----------
    def handle(self, event) -> bool:
        """True se o editor usou o evento (aí a janela/jogo não recebem)."""
        g, w = self.game, self.world
        win = g.window
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if win._hovered():
                return False                    # botões da janela continuam valendo
            pos = win.to_canvas(event.pos)
            if self.panel and self._panel_rect().collidepoint(pos):
                for rect, (_, name, file, _) in self._cells()[0]:
                    if rect.collidepoint(pos):
                        self.add(name, file)
                        break
                return True
            hits = [i for i, p in enumerate(w.props) if self._rect(p).collidepoint(pos)]
            if hits:
                self.sel = max(hits, key=lambda i: w.props[i].y)   # o da frente
                p = w.props[self.sel]
                self.drag = (pos[0] - p.x, pos[1] - p.y)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if win._hovered():
                return False
            pos = win.to_canvas(event.pos)
            if self.panel and self._panel_rect().collidepoint(pos):
                return True
            if w.props:
                hits = [i for i, p in enumerate(w.props) if self._rect(p).collidepoint(pos)]
                if hits:
                    self.sel = max(hits, key=lambda i: w.props[i].y)
                self._toggle_flip(self.sel)
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.drag = None
            return True
        if event.type == pygame.MOUSEMOTION and self.drag and w.props:
            x, y = win.to_canvas(event.pos)
            self._move(self.sel, x - self.drag[0], y - self.drag[1])
            return True
        if event.type == pygame.MOUSEWHEEL:
            mouse = win.to_canvas(pygame.mouse.get_pos())
            if self.panel and self._panel_rect().collidepoint(mouse):
                self.scroll = max(0, self.scroll - event.y * 40)
            elif w.props:
                self._scale(self.sel, 1.05 if event.y > 0 else 1 / 1.05)
            return True
        if event.type != pygame.KEYDOWN:
            return False
        key, mods = event.key, pygame.key.get_mods()
        if key in (pygame.K_o, pygame.K_ESCAPE):
            self.toggle()
            return True
        if (key == pygame.K_s and mods & pygame.KMOD_CTRL) or key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.save()
            return True
        if key == pygame.K_l:
            self.panel = not self.panel
            if self.panel and not self._library():
                g.show("biblioteca vazia: coloque PNGs em assets/sprites/world/library/<conjunto>/")
            return True
        if key in (pygame.K_F2, pygame.K_F3, pygame.K_F4, pygame.K_F11):
            return False                        # teclas da janela
        if not w.props:
            return True
        p = w.props[self.sel]
        step = 10 if mods & pygame.KMOD_SHIFT else 1
        moves = {pygame.K_LEFT: (-step, 0), pygame.K_RIGHT: (step, 0),
                 pygame.K_UP: (0, -step), pygame.K_DOWN: (0, step)}
        if key in moves:
            dx, dy = moves[key]
            self._move(self.sel, p.x + dx * w.k, p.y + dy * w.k)
        elif key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self._scale(self.sel, 1.05)
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self._scale(self.sel, 1 / 1.05)
        elif key == pygame.K_TAB:
            self.sel = (self.sel + 1) % len(w.props)
        elif key == pygame.K_DELETE:
            self._remove(self.sel)
        elif key in (pygame.K_f, pygame.K_h):
            self._toggle_flip(self.sel)
        elif key == pygame.K_k:
            self._toggle_solid(self.sel)
        elif key == pygame.K_BACKSPACE:
            self._reset(self.sel)
        return True

    # ---------- salvar ----------
    def save(self):
        """Grava a lista de objetos de cada área (na estação atual) em layout.json."""
        data = {}
        if LAYOUT_FILE.exists():
            try:
                data = json.loads(LAYOUT_FILE.read_text(encoding="utf-8"))
            except ValueError:
                log.warning("layout.json inválido: será sobrescrito")

        def plain(v):
            return [plain(x) for x in v] if isinstance(v, (list, tuple)) else v

        for name, w in self.game.worlds.items():
            data[layout_key(name, w.season)] = [{k: plain(v) for k, v in d.items()} for d in w.prop_defs]
        LAYOUT_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        self.dirty = False
        self.game.show(f"salvo em layout.json (padrão da estação {self.world.season})")
        log.info("layout salvo: %s", LAYOUT_FILE)

    # ---------- desenho ----------
    def draw(self, surface):
        if not self.active:
            return
        w = self.world
        for i, p in enumerate(w.props):
            r = self._rect(p)
            sel = i == self.sel
            pygame.draw.rect(surface, (255, 220, 60) if sel else (200, 200, 255), r, 2 if sel else 1)
            if p.solid is not None:
                pygame.draw.rect(surface, (255, 70, 70), p.solid, 1)
            if sel:
                bx, by = round(p.x), round(p.y)
                pygame.draw.line(surface, (255, 80, 80), (bx - 8, by), (bx + 8, by), 2)
                pygame.draw.line(surface, (255, 80, 80), (bx, by - 8), (bx, by + 8), 2)
        if self.panel:
            self._draw_panel(surface)
        lines = [HELP]
        if w.props:
            d = w.prop_defs[self.sel]
            x, y = d["img_pos"]
            label = d.get("name") or d.get("kind")
            solid = "sólido" if w.props[self.sel].solid is not None else "atravessável"
            flip_txt = "   invertido" if d.get("flip") else ""
            lines.append(f"[{self.sel + 1}/{len(w.props)}] {label}   posição ({x:.0f}, {y:.0f})   "
                         f"tamanho {d.get('scale', 1):.2f}   {solid}{flip_txt}   estação: {w.season}"
                         + ("   * não salvo" if self.dirty else ""))
        else:
            lines.append(f"esta área não tem objetos (L abre a biblioteca)   estação: {w.season}")
        y = surface.get_height() - 8
        for text in reversed(lines):
            img = self.font.render(text, True, (255, 255, 255))
            bg = pygame.Surface((img.get_width() + 14, img.get_height() + 6), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 170))
            y -= bg.get_height()
            surface.blit(bg, (6, y))
            surface.blit(img, (13, y + 3))

    def _draw_panel(self, surface):
        r = self._panel_rect()
        bg = pygame.Surface(r.size, pygame.SRCALPHA)
        bg.fill((20, 22, 32, 225))
        surface.blit(bg, r.topleft)
        old = surface.get_clip()
        surface.set_clip(r)
        cells, titles = self._cells()
        for group, ty in titles:
            surface.blit(self.font.render(group, True, (255, 220, 120)), (r.x + 8, ty))
        mouse = self.game.window.to_canvas(pygame.mouse.get_pos())
        for rect, (_, name, _, thumb) in cells:
            hover = rect.collidepoint(mouse)
            pygame.draw.rect(surface, (70, 75, 100) if hover else (40, 44, 60), rect, border_radius=6)
            surface.blit(thumb, thumb.get_rect(midbottom=(rect.centerx, rect.bottom - 16)))
            lbl = self.small.render(name[:14], True, (230, 230, 240))
            surface.blit(lbl, lbl.get_rect(midbottom=(rect.centerx, rect.bottom - 2)))
        surface.set_clip(old)
        title = self.font.render("BIBLIOTECA  (clique para colocar)", True, (255, 255, 255))
        surface.blit(title, (r.x + 8, r.y + 8))
