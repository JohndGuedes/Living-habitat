"""Tela inicial e menu central de configurações (estilo Hollow Knight).

- Tela Inicial ("title"): transparente por cima do habitat já rodando ao vivo no
  fundo, com vinheta suave, partículas de luz, título ornamentado e opções
  (Entrar no Habitat, Configurações, Sair).
- Painel de Configurações ("settings"): abre com Esc ou pelo botão no canto
  superior esquerdo. Reúne controles de Janela (Tela Cheia, Sem Borda/Popup,
  Fixar por Cima, Transparência, Tamanho da Janela) e Áudio (Volume/Mudo).
"""
import math
import random

import pygame

from .window import OPACITIES, SIZE_PRESETS

# Paleta inspirada em Hollow Knight (tons noturnos, prata/marfim e azul-alma)
INK_BG = (10, 14, 24)
PANEL_BG = (13, 18, 30, 236)
SILVER = (218, 224, 236)
IVORY = (246, 246, 240)
MUTED = (146, 156, 176)
ACCENT = (145, 208, 255)
ACCENT_FILL = (42, 74, 112)
HOVER_FILL = (44, 54, 76)
IDLE_FILL = (24, 30, 44)


def _load_font(names, size, bold=False):
    for name in names:
        try:
            f = pygame.font.SysFont(name, size, bold=bold)
            if f is not None:
                return f
        except Exception:
            pass
    return pygame.font.Font(None, round(size * 1.3))


class Menu:
    def __init__(self, game, start_on_title: bool = True):
        self.game = game
        self.w, self.h = game.screen.get_size()
        self.mode = "title" if start_on_title else None     # "title", "settings" ou None
        self.return_to = None                               # para onde voltar ao fechar "settings"
        self.fade = 1.0 if start_on_title else 0.0          # opacidade da tela de título (fade suave)
        self.time = 0.0
        self.title_sel = 0
        self.dragging_vol = False

        # Fontes (serifada nobre para títulos, sans limpa para controles)
        serif = ("constantia", "palatinolinotype", "georgia")
        sans = ("segoeui", "candara", "arial")
        self.f_title = _load_font(serif, 56, bold=True)
        self.f_sub = _load_font(serif, 19)
        self.f_menu = _load_font(serif, 28, bold=True)
        self.f_h2 = _load_font(serif, 28, bold=True)
        self.f_sec = _load_font(serif, 15, bold=True)
        self.f_label = _load_font(sans, 18)
        self.f_btn = _load_font(sans, 16, bold=True)
        self.f_small = _load_font(sans, 14)

        self.title_items = [
            ("Entrar no Habitat", self.start_game),
            ("Configurações", self.open_settings),
            ("Sair", self.quit_game),
        ]

        # Vinheta pré-renderizada para a tela de título
        self._vignette = self._make_vignette()
        self._backdrop = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self._backdrop.fill((6, 9, 16, 175))

        # Partículas sutis flutuando no menu
        self.rng = random.Random(19)
        self.motes = [self._new_mote(random_y=True) for _ in range(28)]

        # Regiões clicáveis atualizadas a cada desenho: [(rect, id, ação)]
        self._hotspots = []
        self._vol_bar_rect = None

    # ---------- estado ----------
    @property
    def active(self) -> bool:
        return self.mode is not None or self.fade > 0.02

    @property
    def on_title(self) -> bool:
        return self.mode == "title"

    @property
    def in_settings(self) -> bool:
        return self.mode == "settings"

    def start_game(self):
        self.mode = None
        self.return_to = None

    def open_title(self):
        self.mode = "title"
        self.return_to = None
        self.title_sel = 0

    def open_settings(self):
        if self.mode == "title":
            self.return_to = "title"
        else:
            self.return_to = None
        self.mode = "settings"

    def close_settings(self):
        self.mode = self.return_to
        self.return_to = None
        self.dragging_vol = False

    def toggle(self):
        """Alterna o menu de configurações durante o jogo (tecla Esc ou botão no canto)."""
        if self.mode == "title":
            self.open_settings()
        elif self.mode == "settings":
            self.close_settings()
        else:
            self.open_settings()

    def quit_game(self):
        self.game.running = False

    # ---------- atualização ----------
    def _new_mote(self, random_y=False):
        return [
            self.rng.uniform(120, self.w - 120),
            self.rng.uniform(60, self.h - 60) if random_y else self.h + self.rng.uniform(10, 60),
            self.rng.uniform(-12, 12),
            self.rng.uniform(14, 32),
            self.rng.uniform(1.5, 3.6),
            self.rng.uniform(0, math.tau),
        ]

    def update(self, dt: float):
        self.time += dt
        target = 1.0 if self.mode is not None else 0.0
        speed = 6.0 if target > self.fade else 3.2
        self.fade += (target - self.fade) * min(1.0, dt * speed)
        if abs(self.fade - target) < 0.01:
            self.fade = target

        if not self.active:
            return
        for m in self.motes:
            m[0] += (m[2] + math.sin(self.time * 1.4 + m[5]) * 8) * dt
            m[1] -= m[3] * dt
            if m[1] < -20:
                m[:] = self._new_mote(random_y=False)

    # ---------- eventos ----------
    def handle_event(self, event) -> bool:
        """Retorna True se o menu consumiu o evento."""
        win = self.game.window
        if self.mode is None:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.open_settings()
                return True
            return False

        # Teclas globais da janela (F2/F3/F4/F11) continuam funcionando dentro do menu
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_F2, pygame.K_F3, pygame.K_F4, pygame.K_F11):
            return False

        if self.mode == "title":
            return self._handle_title(event, win)
        if self.mode == "settings":
            return self._handle_settings(event, win)
        return False

    def _handle_title(self, event, win) -> bool:
        if event.type == pygame.MOUSEMOTION:
            pos = win.to_canvas(event.pos)
            for i, (r, _, _) in enumerate(self._title_rects()):
                if r.collidepoint(pos):
                    self.title_sel = i
                    break
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = win.to_canvas(event.pos)
            for i, (r, _, fn) in enumerate(self._title_rects()):
                if r.collidepoint(pos):
                    self.title_sel = i
                    fn()
                    return True
            return False   # permite arrastar a janela clicando fora dos botões
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.title_sel = (self.title_sel - 1) % len(self.title_items)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.title_sel = (self.title_sel + 1) % len(self.title_items)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.title_items[self.title_sel][1]()
            elif event.key == pygame.K_ESCAPE:
                self.open_settings()
            return True
        return False

    def _handle_settings(self, event, win) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = win.to_canvas(event.pos)
            if self._vol_bar_rect and self._vol_bar_rect.inflate(8, 12).collidepoint(pos):
                self.dragging_vol = True
                self._set_vol_from_x(pos[0])
                return True
            for r, _, fn in self._hotspots:
                if r.collidepoint(pos):
                    fn()
                    return True
            # Clicar fora do painel fecha as configurações (se veio do jogo)
            if not self._panel_rect().collidepoint(pos):
                self.close_settings()
                return True
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging_vol = False
            return True
        if event.type == pygame.MOUSEMOTION:
            if self.dragging_vol:
                pos = win.to_canvas(event.pos)
                self._set_vol_from_x(pos[0])
                return True
            return False
        if event.type == pygame.MOUSEWHEEL:
            pos = win.to_canvas(pygame.mouse.get_pos())
            if self._vol_bar_rect and self._vol_bar_rect.inflate(24, 24).collidepoint(pos):
                self.game.music.change(0.05 if event.y > 0 else -0.05)
                return True
            return True   # evita redimensionar a janela sem querer com o modal aberto
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close_settings()
            return True
        return False

    def _set_vol_from_x(self, x: float):
        r = self._vol_bar_rect
        if not r or not self.game.music:
            return
        v = max(0.0, min(1.0, (x - r.x) / max(1, r.w)))
        self.game.music.state["music_volume"] = round(v, 2)
        self.game.music.state["music_muted"] = False
        self.game.music._apply()

    # ---------- geometria ----------
    def _title_rects(self):
        cx = self.w // 2
        y0 = 370
        gap = 58
        out = []
        for i, (label, fn) in enumerate(self.title_items):
            r = pygame.Rect(0, 0, 320, 46)
            r.center = (cx, y0 + i * gap)
            out.append((r, label, fn))
        return out

    def _panel_rect(self) -> pygame.Rect:
        r = pygame.Rect(0, 0, 760, 548)
        r.center = (self.w // 2, self.h // 2)
        return r

    # ---------- desenho ----------
    def draw(self, surface: pygame.Surface):
        if not self.active:
            return
        layer = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        if self.mode == "settings":
            self._draw_settings(layer)
        else:
            self._draw_title(layer)

        if self.fade < 0.99:
            layer.set_alpha(round(255 * self.fade))
        surface.blit(layer, (0, 0))

    def _draw_motes(self, surface: pygame.Surface):
        for x, y, _, _, rad, phase in self.motes:
            pulse = 0.55 + 0.45 * math.sin(self.time * 2.2 + phase)
            a = round(95 * pulse)
            r = max(1, round(rad))
            glow = pygame.Surface((r * 6, r * 6), pygame.SRCALPHA)
            pygame.draw.circle(glow, (185, 220, 255, a // 3), (r * 3, r * 3), r * 3)
            pygame.draw.circle(glow, (245, 250, 255, a), (r * 3, r * 3), r)
            surface.blit(glow, (round(x - r * 3), round(y - r * 3)))

    def _draw_title(self, surface: pygame.Surface):
        surface.blit(self._vignette, (0, 0))
        self._draw_motes(surface)

        cx = self.w // 2
        # Ornamento superior estilo Hallownest
        self._draw_crest(surface, cx, 132, width=340, top=True)

        # Sombra + Título principal
        sh = self.f_title.render("LIVING HABITAT", True, (6, 8, 14))
        tx = self.f_title.render("LIVING HABITAT", True, IVORY)
        surface.blit(sh, sh.get_rect(center=(cx + 2, 188)))
        surface.blit(tx, tx.get_rect(center=(cx, 185)))

        # Subtítulo e divisor ornamental
        sub = self.f_sub.render("Um refúgio vivo em Hallownest", True, (195, 206, 226))
        surface.blit(sub, sub.get_rect(center=(cx, 236)))
        self._draw_divider(surface, cx, 268, width=420)

        # Botões do menu inicial
        mouse = self.game.window.to_canvas(pygame.mouse.get_pos()) if pygame.mouse.get_focused() else (-1, -1)
        for i, (r, label, _) in enumerate(self._title_rects()):
            sel = i == self.title_sel or r.collidepoint(mouse)
            if sel:
                # Brilho suave atrás da opção selecionada
                hl = pygame.Surface((r.w + 40, r.h + 6), pygame.SRCALPHA)
                pygame.draw.ellipse(hl, (145, 208, 255, 28), hl.get_rect())
                pygame.draw.ellipse(hl, (240, 246, 255, 18), hl.get_rect().inflate(-60, -10))
                surface.blit(hl, hl.get_rect(center=r.center))

            col = IVORY if sel else (182, 192, 210)
            sh_lbl = self.f_menu.render(label, True, (8, 10, 18))
            lbl = self.f_menu.render(label, True, col)
            surface.blit(sh_lbl, sh_lbl.get_rect(center=(r.centerx + 1, r.centery + 2)))
            surface.blit(lbl, lbl.get_rect(center=r.center))

            if sel:
                spread = lbl.get_width() // 2 + 28 + round(math.sin(self.time * 5.0) * 3)
                self._draw_pointer(surface, r.centerx - spread, r.centery, side="left")
                self._draw_pointer(surface, r.centerx + spread, r.centery, side="right")

        # Rodapé discreto com dica de comando
        hint = self.f_small.render("Setas / Mouse para escolher  ·  Enter ou Clique para confirmar", True, (140, 152, 175))
        surface.blit(hint, hint.get_rect(center=(cx, self.h - 32)))

    def _draw_settings(self, surface: pygame.Surface):
        surface.blit(self._backdrop, (0, 0))
        self._draw_motes(surface)

        self._hotspots = []
        self._vol_bar_rect = None
        win = self.game.window
        mus = self.game.music
        mouse = win.to_canvas(pygame.mouse.get_pos()) if pygame.mouse.get_focused() else (-1, -1)

        pr = self._panel_rect()
        pygame.draw.rect(surface, PANEL_BG, pr, border_radius=14)
        pygame.draw.rect(surface, (*SILVER, 150), pr, 2, border_radius=14)
        pygame.draw.rect(surface, (*SILVER, 55), pr.inflate(-10, -10), 1, border_radius=10)
        self._draw_corner_ornaments(surface, pr.inflate(-14, -14))

        # Cabeçalho
        cx = pr.centerx
        title = self.f_h2.render("CONFIGURAÇÕES", True, IVORY)
        surface.blit(title, title.get_rect(center=(cx, pr.top + 38)))
        self._draw_divider(surface, cx, pr.top + 64, width=460)

        # Botão fechar (X) no canto superior direito do painel
        close_r = pygame.Rect(pr.right - 48, pr.top + 18, 30, 30)
        close_hot = close_r.collidepoint(mouse)
        pygame.draw.rect(surface, (140, 48, 56) if close_hot else IDLE_FILL, close_r, border_radius=7)
        pygame.draw.rect(surface, (*SILVER, 120), close_r, 1, border_radius=7)
        cx_b, cy_b = close_r.center
        pygame.draw.line(surface, IVORY, (cx_b - 5, cy_b - 5), (cx_b + 5, cy_b + 5), 2)
        pygame.draw.line(surface, IVORY, (cx_b - 5, cy_b + 5), (cx_b + 5, cy_b - 5), 2)
        self._hotspots.append((close_r, "close", self.close_settings))

        # Layout das linhas de configuração
        left_x = pr.left + 44
        right_x = pr.right - 44
        y = pr.top + 82

        # --- SEÇÃO 1: JANELA E EXIBIÇÃO ---
        sec1 = self.f_sec.render("EXIBIÇÃO E JANELA", True, ACCENT)
        surface.blit(sec1, (left_x, y))
        y += 28

        # 1. Modo de Tela (Janela / Tela Cheia)
        self._draw_row_label(surface, left_x, y, "Modo de Exibição", "Alterna entre janela e tela cheia (F11)")
        self._draw_choice_pills(surface, right_x, y, mouse, [
            ("Janela", not win.fullscreen, lambda: win.toggle_fullscreen() if win.fullscreen else None),
            ("Tela Cheia", win.fullscreen, lambda: win.toggle_fullscreen() if not win.fullscreen else None),
        ], pill_w=124)
        y += 52

        # 2. Estilo da Janela (Com Borda / Sem Borda - Popup)
        self._draw_row_label(surface, left_x, y, "Bordas da Janela", "Modo popup remove a barra de título do Windows (F3)")
        bl = bool(win.state.get("borderless"))
        self._draw_choice_pills(surface, right_x, y, mouse, [
            ("Com Borda", not bl and not win.fullscreen, lambda: win.toggle_border() if bl else None),
            ("Sem Borda (Popup)", bl and not win.fullscreen, lambda: win.toggle_border() if not bl else None),
        ], widths=[124, 168])
        y += 52

        # 3. Fixar por Cima (Sempre Visível)
        self._draw_row_label(surface, left_x, y, "Fixar no Topo", "Mantém o habitat sempre visível sobre outras janelas (F2)")
        pinned = bool(win.state.get("pinned"))
        self._draw_choice_pills(surface, right_x, y, mouse, [
            ("Ativado", pinned, lambda: win.toggle_pin() if not pinned else None),
            ("Desativado", not pinned, lambda: win.toggle_pin() if pinned else None),
        ], pill_w=124)
        y += 52

        # 4. Transparência da Janela
        self._draw_row_label(surface, left_x, y, "Transparência", "Opacidade da janela para observar em segundo plano (F4)")
        cur_op = round(float(win.state.get("opacity", 1.0)), 2)
        op_items = [(f"{round(op * 100)}%", abs(cur_op - op) < 0.03, lambda v=op: win.set_opacity(v)) for op in OPACITIES]
        self._draw_choice_pills(surface, right_x, y, mouse, op_items, pill_w=68)
        y += 52

        # 5. Tamanho da Janela
        cur_w, cur_h = win.current_size
        size_desc = "Tela Cheia ativa" if win.fullscreen else f"Atual: {cur_w}×{cur_h}  (use também a roda do mouse)"
        self._draw_row_label(surface, left_x, y, "Tamanho da Janela", size_desc)
        size_items = []
        for sw, sh in SIZE_PRESETS:
            active_sz = (not win.fullscreen) and abs(cur_w - sw) < 25 and abs(cur_h - sh) < 25
            size_items.append((f"{sw}×{sh}", active_sz, lambda w=sw, h=sh: win.set_size(w, h)))
        size_items.append(("−", False, lambda: win.resize(1 / 1.15)))
        size_items.append(("+", False, lambda: win.resize(1.15)))
        self._draw_choice_pills(surface, right_x, y, mouse, size_items, widths=[88, 88, 96, 36, 36])
        y += 58

        # Linha divisória
        pygame.draw.line(surface, (*SILVER, 45), (left_x, y - 6), (right_x, y - 6), 1)

        # --- SEÇÃO 2: ÁUDIO ---
        sec2 = self.f_sec.render("ÁUDIO", True, ACCENT)
        surface.blit(sec2, (left_x, y + 2))
        y += 30

        vol_pct = 0 if (not mus or mus.muted) else round(mus.volume * 100)
        self._draw_row_label(surface, left_x, y, "Música Ambiente", f"Volume atual: {vol_pct}%  (atalho: U para mudo)")
        if mus:
            self._draw_audio_controls(surface, right_x, y, mouse, mus)

        # --- RODAPÉ DO PAINEL ---
        foot_y = pr.bottom - 42
        pygame.draw.line(surface, (*SILVER, 50), (left_x, foot_y - 26), (right_x, foot_y - 26), 1)

        if self.return_to == "title":
            btns = [
                ("Voltar à Tela Inicial", self.close_settings, 210, False),
                ("Entrar no Habitat", self.start_game, 210, True),
            ]
        else:
            btns = [
                ("Voltar ao Jogo (Esc)", self.close_settings, 200, True),
                ("Tela Inicial", self.open_title, 165, False),
                ("Sair do Jogo", self.quit_game, 165, False),
            ]

        total_w = sum(b[2] for b in btns) + 16 * (len(btns) - 1)
        bx = cx - total_w // 2
        for label, fn, bw, primary in btns:
            br = pygame.Rect(bx, foot_y - 16, bw, 36)
            hot = br.collidepoint(mouse)
            is_quit = "Sair" in label
            if is_quit and hot:
                fill = (145, 48, 56)
            elif primary:
                fill = (56, 94, 138) if hot else ACCENT_FILL
            else:
                fill = HOVER_FILL if hot else IDLE_FILL
            pygame.draw.rect(surface, fill, br, border_radius=8)
            bcol = ACCENT if (primary or hot) else (*SILVER, 110)
            pygame.draw.rect(surface, bcol, br, 1, border_radius=8)
            txt = self.f_btn.render(label, True, IVORY if (primary or hot) else SILVER)
            surface.blit(txt, txt.get_rect(center=br.center))
            self._hotspots.append((br, label, fn))
            bx += bw + 16

    def _draw_row_label(self, surface, x, y, title, subtitle):
        t = self.f_label.render(title, True, IVORY)
        s = self.f_small.render(subtitle, True, MUTED)
        surface.blit(t, (x, y))
        surface.blit(s, (x, y + 22))

    def _draw_choice_pills(self, surface, right_x, y, mouse, items, pill_w=100, widths=None):
        """Desenha uma fileira de botões alinhada à direita."""
        ws = widths or [pill_w] * len(items)
        gap = 8
        total = sum(ws) + gap * (len(items) - 1)
        x = right_x - total
        for (label, active, fn), w in zip(items, ws):
            r = pygame.Rect(x, y + 4, w, 34)
            hot = r.collidepoint(mouse)
            fill = (58, 98, 144) if (active and hot) else ACCENT_FILL if active else HOVER_FILL if hot else IDLE_FILL
            pygame.draw.rect(surface, fill, r, border_radius=7)
            bcol = ACCENT if active else (*SILVER, 140 if hot else 75)
            pygame.draw.rect(surface, bcol, r, 1 if not active else 2, border_radius=7)
            txt = self.f_btn.render(label, True, IVORY if (active or hot) else SILVER)
            surface.blit(txt, txt.get_rect(center=r.center))
            self._hotspots.append((r, label, fn))
            x += w + gap

    def _draw_audio_controls(self, surface, right_x, y, mouse, mus):
        # Botão Mudo + [-] [barra de volume] [+]
        mute_w, step_w, bar_w, gap = 92, 32, 160, 8
        total = mute_w + step_w * 2 + bar_w + gap * 3
        x = right_x - total

        # Botão Mudo / Som
        mr = pygame.Rect(x, y + 4, mute_w, 34)
        m_hot = mr.collidepoint(mouse)
        muted = mus.muted or mus.volume <= 0.01
        fill = (128, 52, 60) if muted else ACCENT_FILL if not m_hot else (58, 98, 144)
        pygame.draw.rect(surface, fill, mr, border_radius=7)
        pygame.draw.rect(surface, (235, 130, 135) if muted else ACCENT, mr, 1, border_radius=7)
        m_txt = self.f_btn.render("Mudo" if muted else "Ligada", True, IVORY)
        surface.blit(m_txt, m_txt.get_rect(center=mr.center))
        self._hotspots.append((mr, "mute", mus.toggle_mute))
        x += mute_w + gap

        # Botão -
        r_minus = pygame.Rect(x, y + 4, step_w, 34)
        hot_m = r_minus.collidepoint(mouse)
        pygame.draw.rect(surface, HOVER_FILL if hot_m else IDLE_FILL, r_minus, border_radius=7)
        pygame.draw.rect(surface, (*SILVER, 120 if hot_m else 75), r_minus, 1, border_radius=7)
        t_m = self.f_btn.render("−", True, IVORY)
        surface.blit(t_m, t_m.get_rect(center=r_minus.center))
        self._hotspots.append((r_minus, "vol_down", lambda: mus.change(-0.1)))
        x += step_w + gap

        # Barra de volume clicável/arrastável
        bar_r = pygame.Rect(x, y + 15, bar_w, 12)
        self._vol_bar_rect = bar_r
        pygame.draw.rect(surface, (20, 26, 38), bar_r, border_radius=6)
        v = 0.0 if mus.muted else mus.volume
        if v > 0:
            fill_r = pygame.Rect(bar_r.x, bar_r.y, max(8, round(bar_r.w * v)), bar_r.h)
            pygame.draw.rect(surface, ACCENT, fill_r, border_radius=6)
        pygame.draw.rect(surface, (*SILVER, 110), bar_r, 1, border_radius=6)
        knob_x = bar_r.x + round(bar_r.w * v)
        pygame.draw.circle(surface, IVORY, (knob_x, bar_r.centery), 8)
        pygame.draw.circle(surface, ACCENT_FILL, (knob_x, bar_r.centery), 8, 2)
        x += bar_w + gap

        # Botão +
        r_plus = pygame.Rect(x, y + 4, step_w, 34)
        hot_p = r_plus.collidepoint(mouse)
        pygame.draw.rect(surface, HOVER_FILL if hot_p else IDLE_FILL, r_plus, border_radius=7)
        pygame.draw.rect(surface, (*SILVER, 120 if hot_p else 75), r_plus, 1, border_radius=7)
        t_p = self.f_btn.render("+", True, IVORY)
        surface.blit(t_p, t_p.get_rect(center=r_plus.center))
        self._hotspots.append((r_plus, "vol_up", lambda: mus.change(0.1)))

    # ---------- ornamentos estilo Hollow Knight ----------
    def _make_vignette(self) -> pygame.Surface:
        """Vinheta transparente: escurece o topo/centro e as bordas mantendo a ilha viva ao fundo."""
        vw, vh = 320, 180
        small = pygame.Surface((vw, vh), pygame.SRCALPHA)
        cx, cy = vw / 2, vh * 0.45
        for y in range(vh):
            for x in range(vw):
                dx = (x - cx) / (vw * 0.52)
                dy = (y - cy) / (vh * 0.55)
                edge = min(1.0, (dx * dx + dy * dy) ** 0.65)
                # Leve véu central para leitura do título + bordas mais escuras
                center_veil = max(0.0, 1.0 - (dx * dx * 1.4 + ((y - vh * 0.42) / (vh * 0.38)) ** 2))
                alpha = round(min(220, 95 * center_veil + 165 * edge))
                small.set_at((x, y), (8, 11, 20, alpha))
        return pygame.transform.smoothscale(small, (self.w, self.h))

    def _draw_crest(self, surface, cx, y, width=320, top=True):
        """Arco ornamental acima do título."""
        col = (*SILVER, 210)
        half = width // 2
        pygame.draw.line(surface, col, (cx - half, y), (cx - 28, y), 1)
        pygame.draw.line(surface, col, (cx + 28, y), (cx + half, y), 1)
        # Losango central + pontas
        pts = [(cx, y - 9), (cx + 9, y), (cx, y + 9), (cx - 9, y)]
        pygame.draw.polygon(surface, col, pts, 2)
        pygame.draw.circle(surface, ACCENT, (cx, y), 3)
        for s in (-1, 1):
            pygame.draw.polygon(surface, col, [(cx + s * 22, y), (cx + s * 16, y - 4), (cx + s * 16, y + 4)])
        if top:
            arc_r = pygame.Rect(cx - 90, y - 22, 180, 36)
            pygame.draw.arc(surface, (*SILVER, 140), arc_r, 0.35, math.pi - 0.35, 2)

    def _draw_divider(self, surface, cx, y, width=400):
        col = (*SILVER, 185)
        half = width // 2
        pygame.draw.line(surface, col, (cx - half, y), (cx - 18, y), 1)
        pygame.draw.line(surface, col, (cx + 18, y), (cx + half, y), 1)
        pygame.draw.polygon(surface, col, [(cx, y - 6), (cx + 12, y), (cx, y + 6), (cx - 12, y)], 2)
        for s in (-1, 1):
            pygame.draw.circle(surface, col, (cx + s * (half + 6), y), 2)

    def _draw_pointer(self, surface, x, y, side="left"):
        """Ponteiro lateral que indica o item selecionado no menu inicial."""
        s = -1 if side == "left" else 1
        pts = [
            (x, y),
            (x + s * 12, y - 6),
            (x + s * 8, y),
            (x + s * 12, y + 6),
        ]
        pygame.draw.polygon(surface, IVORY, pts)
        pygame.draw.line(surface, (*SILVER, 190), (x + s * 12, y), (x + s * 28, y), 2)
        pygame.draw.circle(surface, ACCENT, (x + s * 4, y), 2)

    def _draw_corner_ornaments(self, surface, rect: pygame.Rect):
        """Cantoneiras geométricas estilo Hollow Knight nos 4 cantos do painel."""
        col = (*SILVER, 180)
        L = 18
        for x, sx in ((rect.left, 1), (rect.right, -1)):
            for y, sy in ((rect.top, 1), (rect.bottom, -1)):
                pygame.draw.line(surface, col, (x, y), (x + sx * L, y), 2)
                pygame.draw.line(surface, col, (x, y), (x, y + sy * L), 2)
                pygame.draw.polygon(surface, col, [
                    (x + sx * 5, y + sy * 5),
                    (x + sx * 10, y + sy * 5),
                    (x + sx * 5, y + sy * 10),
                ])
