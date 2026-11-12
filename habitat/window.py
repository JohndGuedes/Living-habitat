"""Janela "popup" para deixar o habitat aberto num canto do monitor.

- O jogo desenha sempre numa tela interna de WIDTHxHEIGHT; aqui ela é
  escalada (suave) para o tamanho que a janela tiver, mantendo a proporção.
- Botão discreto de Menu no canto superior esquerdo + barra rápida elegante
  (aparece ao mexer o mouse): Menu, Fixar por cima, Sem borda, Tela cheia,
  Transparência, Diminuir, Aumentar, Música, Fechar.
- Arrastar com o botão esquerdo em qualquer lugar move a janela (útil sem borda).
- Roda do mouse muda o tamanho.
- Atalhos: F2 fixar, F3 sem borda, F4 transparência, F11 tela cheia.
- Botão de som (audio.Music): clique = mudo; roda do mouse em cima dele = volume.
- Posição, tamanho e opções são lembrados em window_state.json.
"""
import json
import logging
import math

import pygame

from .config import ROOT

log = logging.getLogger(__name__)

STATE_FILE = ROOT / "window_state.json"
DEFAULTS = {"size": [640, 360], "pos": None, "pinned": True, "borderless": False, "opacity": 1.0}
OPACITIES = [1.0, 0.85, 0.7, 0.55]
SIZE_PRESETS = [(640, 360), (960, 540), (1280, 720)]
MIN_W = 320
BTN, GAP = 28, 5
PAD_X, PAD_Y = 8, 6
ACCENT = (145, 208, 255)
BORDER_COL = (180, 195, 220)


class PopupWindow:
    def __init__(self, canvas_size: tuple[int, int], title: str):
        self.cw, self.ch = canvas_size
        self.state = dict(DEFAULTS)
        try:
            self.state.update(json.loads(STATE_FILE.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass

        self.display = pygame.display.set_mode(tuple(self.state["size"]), pygame.RESIZABLE)
        pygame.display.set_caption(title)
        self.win = pygame.Window.from_display_module()
        self._try("minimum_size", (MIN_W, round(MIN_W * self.ch / self.cw)))
        if self.state["pos"]:
            self._try("position", tuple(self.state["pos"]))
        self._try("always_on_top", self.state["pinned"])
        self._try("borderless", self.state["borderless"])
        self._try("opacity", self.state["opacity"])

        self.fullscreen = False
        self.drag_offset = None     # arrastando a janela?
        self.last_mouse = -10.0     # quando o mouse mexeu por último (mostra a barra)
        self.toolbar_alpha = 0.0    # animação suave da barra rápida (0..1)
        try:
            self.font = pygame.font.SysFont("segoeui", 14)
        except Exception:
            self.font = pygame.font.Font(None, 18)
        self.buttons = [            # (id, dica)
            ("menu", "Menu e configurações (Esc)"),
            ("pin", "Fixar por cima (F2)"),
            ("border", "Sem borda / modo popup (F3)"),
            ("fullscreen", "Tela cheia (F11)"),
            ("opacity", "Transparência da janela (F4)"),
            ("smaller", "Diminuir janela (roda do mouse)"),
            ("bigger", "Aumentar janela (roda do mouse)"),
            ("music", "Música: clique = mudo (U), roda = volume (- / +)"),
            ("close", "Fechar jogo"),
        ]
        self.music = None           # audio.Music (o Game liga): botão de som
        self.on_menu = None         # callback para abrir o painel de menu (ligado pelo Game)
        self.toolbar_enabled = True
        self._scaled = None
        self._view = (0, 0, 1.0)    # (ox, oy, escala) da tela do jogo dentro da janela
        self._press = None          # onde o botão foi apertado (p/ separar clique de arrasto)
        self.click = None           # último clique (sem arrastar), em coordenadas do JOGO

    # ---------- utilidades ----------
    def _try(self, attr, value):
        """Algumas plataformas/drivers não suportam tudo: ignora sem quebrar."""
        try:
            setattr(self.win, attr, value)
        except Exception as e:
            log.debug("janela: não deu para mudar %s (%s)", attr, e)

    def _button_rects(self):
        """Posições dos botões na barra superior com pequenos separadores visuais."""
        rects = []
        x = PAD_X + 6
        y = PAD_Y + 4
        for i, (bid, _) in enumerate(self.buttons):
            rects.append(pygame.Rect(x, y, BTN, BTN))
            x += BTN + GAP
            if bid in ("menu", "opacity", "music"):
                x += 6  # espaço para divisor vertical
        return rects

    def _bar_rect(self, only_menu=False):
        rects = self._button_rects()
        if only_menu:
            r = rects[0]
            return pygame.Rect(PAD_X, PAD_Y, r.width + 12, BTN + 8)
        return pygame.Rect(PAD_X, PAD_Y, rects[-1].right - PAD_X + 6, BTN + 8)

    def _toolbar_expanded(self) -> bool:
        if not self.toolbar_enabled:
            return False
        now = pygame.time.get_ticks() / 1000
        if not pygame.mouse.get_focused():
            return False
        pos = pygame.mouse.get_pos()
        near_top = pos[0] < 360 and pos[1] < 54
        return now - self.last_mouse < 2.2 or (self.drag_offset is None and (near_top or self._hovered() is not None))

    _toolbar_visible = _toolbar_expanded

    def _hovered(self):
        if not self.toolbar_enabled or not pygame.mouse.get_focused():
            return None
        pos = pygame.mouse.get_pos()
        rects = self._button_rects()
        # Mesmo com a barra recolhida, o botão 0 ("menu") no canto continua clicável
        limit = len(self.buttons) if self.toolbar_alpha > 0.25 else 1
        for (bid, tip), r in zip(self.buttons[:limit], rects[:limit]):
            if r.collidepoint(pos):
                return bid, tip
        return None

    # ---------- ações ----------
    def toggle_pin(self):
        self.state["pinned"] = not self.state["pinned"]
        self._try("always_on_top", self.state["pinned"])

    def toggle_border(self):
        if self.fullscreen:
            return
        self.state["borderless"] = not self.state["borderless"]
        self._try("borderless", self.state["borderless"])

    def cycle_opacity(self):
        i = OPACITIES.index(self.state["opacity"]) if self.state["opacity"] in OPACITIES else 0
        self.set_opacity(OPACITIES[(i + 1) % len(OPACITIES)])

    def set_opacity(self, value: float):
        self.state["opacity"] = round(float(value), 2)
        self._try("opacity", self.state["opacity"])

    @property
    def current_size(self) -> tuple[int, int]:
        try:
            return tuple(self.win.size)
        except Exception:
            return tuple(self.state["size"])

    def set_size(self, nw: int, nh: int | None = None):
        """Define o tamanho da janela mantendo a proporção e o centro no lugar."""
        if self.fullscreen:
            self.toggle_fullscreen()
        w, h = self.current_size
        nw = max(MIN_W, min(int(nw), self.cw * 2))
        nh = int(nh) if nh is not None else round(nw * self.ch / self.cw)
        self.state["size"] = [nw, nh]
        try:
            x, y = self.win.position
            self._try("size", (nw, nh))
            self._try("position", (x + (w - nw) // 2, y + (h - nh) // 2))
        except Exception:
            self._try("size", (nw, nh))

    def resize(self, factor: float):
        """Muda o tamanho mantendo a proporção e o centro da janela no lugar."""
        if self.fullscreen:
            return
        w, _ = self.current_size
        self.set_size(round(w * factor))

    def toggle_fullscreen(self):
        try:
            if self.fullscreen:
                self.win.set_windowed()
                self._try("borderless", self.state["borderless"])
                self._try("always_on_top", self.state["pinned"])
            else:
                self.state["size"] = list(self.current_size)
                self.state["pos"] = list(self.win.position)
                self.win.set_fullscreen(desktop=True)
            self.fullscreen = not self.fullscreen
        except Exception as e:
            log.debug("tela cheia indisponível: %s", e)

    # ---------- eventos ----------
    def handle_event(self, event, allow_drag: bool = True, allow_wheel_resize: bool = True) -> bool | str:
        """Trata eventos da janela. Retorna True se consumiu o evento,
        "quit" se pediu para fechar, False se o jogo deve tratar."""
        if event.type == pygame.MOUSEMOTION:
            self.last_mouse = pygame.time.get_ticks() / 1000
        elif event.type == pygame.MOUSEWHEEL:
            hit = self._hovered()
            if hit and hit[0] == "music" and self.music:     # roda em cima do botão de som: volume
                self.music.change(0.05 if event.y > 0 else -0.05)
                return True
            if allow_wheel_resize:
                self.resize(1.1 if event.y > 0 else 1 / 1.1)
                return True
            return False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hit = self._hovered()
            if hit:
                return self._click(hit[0])
            self._press = (pygame.mouse.get_pos(desktop=True), event.pos)
            if allow_drag and not self.fullscreen:  # começa a arrastar a janela
                mx, my = self._press[0]
                wx, wy = self.win.position
                self.drag_offset = (mx - wx, my - wy)
            return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.drag_offset = None
            if self._press:
                (sx, sy), (px, py) = self._press
                mx, my = pygame.mouse.get_pos(desktop=True)
                if abs(mx - sx) + abs(my - sy) < 6:  # não arrastou: é um clique
                    ox, oy, k = self._view
                    self.click = ((px - ox) / k, (py - oy) / k)
            self._press = None
            return True
        elif event.type == pygame.KEYDOWN:
            actions = {pygame.K_F2: self.toggle_pin, pygame.K_F3: self.toggle_border,
                       pygame.K_F4: self.cycle_opacity, pygame.K_F11: self.toggle_fullscreen}
            if event.key in actions:
                actions[event.key]()
                return True
        return False

    def _click(self, bid):
        if bid == "close":
            return "quit"
        if bid == "menu":
            if self.on_menu:
                self.on_menu()
            return True
        if bid == "music":
            if self.music:
                self.music.toggle_mute()
            return True
        {"pin": self.toggle_pin, "border": self.toggle_border, "fullscreen": self.toggle_fullscreen,
         "opacity": self.cycle_opacity, "smaller": lambda: self.resize(1 / 1.15),
         "bigger": lambda: self.resize(1.15)}[bid]()
        return True

    def to_canvas(self, pos):
        """Posição na janela -> posição na tela do jogo (1280x720)."""
        ox, oy, k = self._view
        return ((pos[0] - ox) / k, (pos[1] - oy) / k)

    def pop_click(self):
        """Clique pendente (coordenadas do jogo) ou None."""
        c, self.click = self.click, None
        return c

    # ---------- desenho ----------
    def present(self, canvas: pygame.Surface, show_toolbar: bool = True):
        """Escala a tela do jogo para a janela, desenha a barra e mostra."""
        self.toolbar_enabled = show_toolbar
        if self.drag_offset is not None:
            if pygame.mouse.get_pressed()[0]:
                mx, my = pygame.mouse.get_pos(desktop=True)
                self._try("position", (mx - self.drag_offset[0], my - self.drag_offset[1]))
            else:
                self.drag_offset = None

        self.display = pygame.display.get_surface()
        dw, dh = self.display.get_size()
        k = min(dw / self.cw, dh / self.ch)
        tw, th = max(1, round(self.cw * k)), max(1, round(self.ch * k))
        ox, oy = (dw - tw) // 2, (dh - th) // 2
        self._view = (ox, oy, k)
        if (tw, th) == (self.cw, self.ch):
            self.display.blit(canvas, (ox, oy))
        else:
            if self._scaled is None or self._scaled.get_size() != (tw, th):
                self._scaled = pygame.Surface((tw, th)).convert()
            pygame.transform.smoothscale(canvas, (tw, th), self._scaled)
            if (ox, oy) != (0, 0):
                self.display.fill((10, 12, 18))
            self.display.blit(self._scaled, (ox, oy))

        target = 1.0 if self._toolbar_expanded() else 0.0
        self.toolbar_alpha += (target - self.toolbar_alpha) * 0.22
        if abs(self.toolbar_alpha - target) < 0.02:
            self.toolbar_alpha = target

        if show_toolbar:
            self._draw_toolbar()
        pygame.display.flip()

    def _draw_toolbar(self):
        hovered = self._hovered()
        rects = self._button_rects()
        expanded = self.toolbar_alpha > 0.05

        if not expanded:
            # Apenas um botão discreto de menu no canto quando o mouse está parado
            if not pygame.mouse.get_focused():
                return
            r0 = rects[0]
            pill = pygame.Surface((r0.w + 8, r0.h + 8), pygame.SRCALPHA)
            pygame.draw.rect(pill, (12, 16, 26, 110), pill.get_rect(), border_radius=8)
            pygame.draw.rect(pill, (170, 185, 210, 75), pill.get_rect(), 1, border_radius=8)
            self.display.blit(pill, (r0.x - 4, r0.y - 4))
            self._icon("menu", r0, (210, 220, 235, 160))
            return

        bar = self._bar_rect(only_menu=False)
        layer = pygame.Surface((bar.right + 16, bar.bottom + 42), pygame.SRCALPHA)
        pygame.draw.rect(layer, (11, 15, 24, 215), bar, border_radius=10)
        pygame.draw.rect(layer, (*BORDER_COL, 115), bar, 1, border_radius=10)

        for (bid, _), r in zip(self.buttons, rects):
            active = (
                (bid == "pin" and self.state["pinned"])
                or (bid == "border" and self.state["borderless"])
                or (bid == "fullscreen" and self.fullscreen)
                or (bid == "opacity" and self.state["opacity"] < 1.0)
            )
            hot = hovered is not None and hovered[0] == bid
            if bid == "close" and hot:
                fill = (155, 52, 58, 235)
            elif active:
                fill = (46, 78, 116, 235) if not hot else (62, 100, 146, 245)
            else:
                fill = (28, 34, 48, 200) if not hot else (50, 60, 82, 235)
            pygame.draw.rect(layer, fill, r, border_radius=6)
            if active or hot:
                bcol = (240, 130, 135, 180) if (bid == "close" and hot) else (*ACCENT, 160 if active else 95)
                pygame.draw.rect(layer, bcol, r, 1, border_radius=6)

            ic_col = ACCENT if active else (240, 244, 252) if hot else (210, 218, 230)
            self._icon(bid, r, ic_col, target=layer)

            # divisores verticais sutis entre grupos
            if bid in ("menu", "opacity", "music"):
                dx = r.right + GAP + 2
                pygame.draw.line(layer, (160, 175, 200, 55), (dx, r.top + 4), (dx, r.bottom - 4), 1)

        if hovered:
            tip = hovered[1]
            if hovered[0] == "opacity":
                tip += f" — {round(self.state['opacity'] * 100)}%"
            elif hovered[0] == "music" and self.music:
                tip = self.music.describe().capitalize() + " — clique: mudo, roda: volume"
            txt = self.font.render(tip, True, (238, 242, 250))
            box = pygame.Rect(bar.x, bar.bottom + 5, txt.get_width() + 16, txt.get_height() + 8)
            pygame.draw.rect(layer, (11, 15, 24, 225), box, border_radius=7)
            pygame.draw.rect(layer, (*BORDER_COL, 95), box, 1, border_radius=7)
            layer.blit(txt, (box.x + 8, box.y + 4))

        if self.toolbar_alpha < 0.99:
            layer.set_alpha(round(255 * self.toolbar_alpha))
        self.display.blit(layer, (0, 0))

    def _icon(self, bid, r, c, target=None):
        d = target if target is not None else self.display
        cx, cy = r.center
        if bid == "menu":  # três linhas estilizadas com pequeno losango
            for dy in (-5, 0, 5):
                w = 7 if dy != 0 else 5
                pygame.draw.line(d, c, (cx - 7, cy + dy), (cx + w, cy + dy), 2)
            pygame.draw.polygon(d, ACCENT, [(cx + 6, cy - 2), (cx + 8, cy), (cx + 6, cy + 2), (cx + 4, cy)])
        elif bid == "pin":  # alfinete
            pygame.draw.circle(d, c, (cx, cy - 4), 4, 2)
            pygame.draw.line(d, c, (cx, cy), (cx, cy + 7), 2)
            pygame.draw.line(d, c, (cx - 5, cy + 1), (cx + 5, cy + 1), 2)
        elif bid == "border":  # janela sem barra de título
            pygame.draw.rect(d, c, (cx - 8, cy - 6, 16, 12), 2, border_radius=2)
            pygame.draw.line(d, c, (cx - 8, cy - 2), (cx + 7, cy - 2), 2)
        elif bid == "fullscreen":  # cantoneiras de tela cheia
            for sx in (-1, 1):
                for sy in (-1, 1):
                    x0, y0 = cx + sx * 7, cy + sy * 6
                    pygame.draw.line(d, c, (x0, y0), (x0 - sx * 4, y0), 2)
                    pygame.draw.line(d, c, (x0, y0), (x0, y0 - sy * 4), 2)
        elif bid == "opacity":  # círculo meio cheio
            pygame.draw.circle(d, c, (cx, cy), 7, 2)
            pygame.draw.polygon(d, c, [(cx, cy - 7), (cx, cy + 7), (cx - 5, cy + 5), (cx - 7, cy), (cx - 5, cy - 5)])
        elif bid == "smaller":
            pygame.draw.line(d, c, (cx - 6, cy), (cx + 6, cy), 2)
        elif bid == "bigger":
            pygame.draw.line(d, c, (cx - 6, cy), (cx + 6, cy), 2)
            pygame.draw.line(d, c, (cx, cy - 6), (cx, cy + 6), 2)
        elif bid == "music":  # alto-falante: ondas = volume; X = mudo
            pygame.draw.polygon(d, c, [(cx - 8, cy - 3), (cx - 4, cy - 3), (cx, cy - 7), (cx, cy + 7),
                                       (cx - 4, cy + 3), (cx - 8, cy + 3)])
            m = self.music
            if m is None or m.muted or not m.ok or m.volume <= 0.01:
                pygame.draw.line(d, (235, 110, 110), (cx + 3, cy - 4), (cx + 8, cy + 4), 2)
                pygame.draw.line(d, (235, 110, 110), (cx + 3, cy + 4), (cx + 8, cy - 4), 2)
            else:
                for i, rad in enumerate((5, 8)):
                    if m.volume > i * 0.45:
                        pygame.draw.arc(d, c, (cx - rad + 1, cy - rad, 2 * rad, 2 * rad), -0.85, 0.85, 2)
        elif bid == "close":
            pygame.draw.line(d, c, (cx - 5, cy - 5), (cx + 5, cy + 5), 2)
            pygame.draw.line(d, c, (cx - 5, cy + 5), (cx + 5, cy - 5), 2)

    # ---------- fim ----------
    def save(self):
        """Guarda tamanho/posição/opções para a próxima vez."""
        try:
            if not self.fullscreen:
                self.state["size"] = list(self.win.size)
                self.state["pos"] = list(self.win.position)
            STATE_FILE.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        except Exception as e:
            log.debug("não deu para salvar o estado da janela: %s", e)
