"""Janela "popup" para deixar o habitat aberto num canto do monitor.

- O jogo desenha sempre numa tela interna de WIDTHxHEIGHT; aqui ela é
  escalada (suave) para o tamanho que a janela tiver, mantendo a proporção.
- Barrinha de botões (aparece ao passar o mouse): fixar por cima, sem borda,
  transparência, diminuir, aumentar, fechar.
- Arrastar com o botão esquerdo em qualquer lugar move a janela (útil sem borda).
- Roda do mouse muda o tamanho.
- Atalhos: F2 fixar, F3 sem borda, F4 transparência, F11 tela cheia.
- Posição, tamanho e opções são lembrados em window_state.json.
"""
import json
import logging

import pygame

from .config import ROOT

log = logging.getLogger(__name__)

STATE_FILE = ROOT / "window_state.json"
DEFAULTS = {"size": [640, 360], "pos": None, "pinned": True, "borderless": False, "opacity": 1.0}
OPACITIES = [1.0, 0.85, 0.7, 0.55]
MIN_W = 320
BTN, GAP = 26, 4
ACCENT = (120, 200, 255)


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
        self.font = pygame.font.Font(None, 18)
        self.buttons = [            # (id, dica)
            ("pin", "Fixar por cima (F2)"),
            ("border", "Sem borda / popup (F3)"),
            ("opacity", "Transparência (F4)"),
            ("smaller", "Diminuir (roda do mouse)"),
            ("bigger", "Aumentar (roda do mouse)"),
            ("close", "Fechar (Esc)"),
        ]
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
        return [pygame.Rect(GAP + i * (BTN + GAP), GAP, BTN, BTN) for i in range(len(self.buttons))]

    def _toolbar_visible(self) -> bool:
        now = pygame.time.get_ticks() / 1000
        return pygame.mouse.get_focused() and (now - self.last_mouse < 2.5 or self.drag_offset is None and
                                               self._hovered() is not None)

    def _hovered(self):
        if not pygame.mouse.get_focused():
            return None
        pos = pygame.mouse.get_pos()
        for (bid, tip), r in zip(self.buttons, self._button_rects()):
            if r.collidepoint(pos):
                return bid, tip
        return None

    # ---------- ações ----------
    def toggle_pin(self):
        self.state["pinned"] = not self.state["pinned"]
        self._try("always_on_top", self.state["pinned"])

    def toggle_border(self):
        self.state["borderless"] = not self.state["borderless"]
        self._try("borderless", self.state["borderless"])

    def cycle_opacity(self):
        i = OPACITIES.index(self.state["opacity"]) if self.state["opacity"] in OPACITIES else 0
        self.state["opacity"] = OPACITIES[(i + 1) % len(OPACITIES)]
        self._try("opacity", self.state["opacity"])

    def resize(self, factor: float):
        """Muda o tamanho mantendo a proporção e o centro da janela no lugar."""
        if self.fullscreen:
            return
        w, h = self.win.size
        x, y = self.win.position
        nw = max(MIN_W, min(round(w * factor), self.cw * 2))
        nh = round(nw * self.ch / self.cw)
        self._try("size", (nw, nh))
        self._try("position", (x + (w - nw) // 2, y + (h - nh) // 2))

    def toggle_fullscreen(self):
        try:
            if self.fullscreen:
                self.win.set_windowed()
            else:
                self.win.set_fullscreen(desktop=True)
            self.fullscreen = not self.fullscreen
        except Exception as e:
            log.debug("tela cheia indisponível: %s", e)

    # ---------- eventos ----------
    def handle_event(self, event) -> bool | str:
        """Trata eventos da janela. Retorna True se consumiu o evento,
        "quit" se pediu para fechar, False se o jogo deve tratar."""
        if event.type == pygame.MOUSEMOTION:
            self.last_mouse = pygame.time.get_ticks() / 1000
        elif event.type == pygame.MOUSEWHEEL:
            self.resize(1.1 if event.y > 0 else 1 / 1.1)
            return True
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hit = self._hovered() if self._toolbar_visible() else None
            if hit:
                return self._click(hit[0])
            self._press = (pygame.mouse.get_pos(desktop=True), event.pos)
            if not self.fullscreen:  # começa a arrastar a janela
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
        {"pin": self.toggle_pin, "border": self.toggle_border, "opacity": self.cycle_opacity,
         "smaller": lambda: self.resize(1 / 1.15), "bigger": lambda: self.resize(1.15)}[bid]()
        return True

    def pop_click(self):
        """Clique pendente (coordenadas do jogo) ou None."""
        c, self.click = self.click, None
        return c

    # ---------- desenho ----------
    def present(self, canvas: pygame.Surface):
        """Escala a tela do jogo para a janela, desenha a barra e mostra."""
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
        if self._toolbar_visible():
            self._draw_toolbar()
        pygame.display.flip()

    def _draw_toolbar(self):
        hovered = self._hovered()
        rects = self._button_rects()
        bar = pygame.Rect(0, 0, rects[-1].right + GAP, BTN + 2 * GAP)
        bg = pygame.Surface(bar.size, pygame.SRCALPHA)
        bg.fill((10, 14, 22, 170))
        self.display.blit(bg, bar)
        for (bid, tip), r in zip(self.buttons, rects):
            active = (bid == "pin" and self.state["pinned"]) or (bid == "border" and self.state["borderless"]) \
                or (bid == "opacity" and self.state["opacity"] < 1)
            hot = hovered is not None and hovered[0] == bid
            fill = (60, 90, 130) if active else (40, 46, 58)
            if hot:
                fill = tuple(min(255, c + 30) for c in fill)
            pygame.draw.rect(self.display, fill, r, border_radius=5)
            self._icon(bid, r, ACCENT if active else (225, 230, 238))
        if hovered:
            tip = hovered[1]
            if hovered[0] == "opacity":
                tip += f" — {round(self.state['opacity'] * 100)}%"
            txt = self.font.render(tip, True, (235, 238, 245))
            box = pygame.Rect(GAP, bar.bottom + 2, txt.get_width() + 10, txt.get_height() + 6)
            tb = pygame.Surface(box.size, pygame.SRCALPHA)
            tb.fill((10, 14, 22, 200))
            self.display.blit(tb, box)
            self.display.blit(txt, (box.x + 5, box.y + 3))

    def _icon(self, bid, r, c):
        d = self.display
        cx, cy = r.center
        if bid == "pin":  # alfinete
            pygame.draw.circle(d, c, (cx, cy - 4), 5)
            pygame.draw.line(d, c, (cx, cy), (cx, cy + 8), 2)
            pygame.draw.line(d, c, (cx - 6, cy + 1), (cx + 6, cy + 1), 2)
        elif bid == "border":  # janela sem barra de título
            pygame.draw.rect(d, c, (cx - 8, cy - 6, 16, 12), 2, border_radius=2)
            pygame.draw.line(d, c, (cx - 8, cy - 2), (cx + 7, cy - 2), 2)
        elif bid == "opacity":  # círculo meio cheio
            pygame.draw.circle(d, c, (cx, cy), 7, 2)
            pygame.draw.polygon(d, c, [(cx, cy - 7), (cx, cy + 7), (cx - 5, cy + 5), (cx - 7, cy), (cx - 5, cy - 5)])
        elif bid == "smaller":
            pygame.draw.line(d, c, (cx - 6, cy), (cx + 6, cy), 3)
        elif bid == "bigger":
            pygame.draw.line(d, c, (cx - 6, cy), (cx + 6, cy), 3)
            pygame.draw.line(d, c, (cx, cy - 6), (cx, cy + 6), 3)
        elif bid == "close":
            pygame.draw.line(d, c, (cx - 5, cy - 5), (cx + 5, cy + 5), 3)
            pygame.draw.line(d, c, (cx - 5, cy + 5), (cx + 5, cy - 5), 3)

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
