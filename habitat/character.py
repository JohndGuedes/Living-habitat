"""O personagem que vive no habitat. Quem decide o que ele faz é a rotina
(brain.py) ou o jogador (teclado). Os dois usam a mesma API: um vetor de
movimento em update() + do_action()/toggle_sleep()/say()."""
import math

import pygame

from .assets import load_sprite_set
from .spritesheet import Animator, dir_from_vector


def read_axis(keys) -> tuple[int, int]:
    """WASD / setas -> (x, y) em {-1, 0, 1}."""
    x = int(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - int(keys[pygame.K_a] or keys[pygame.K_LEFT])
    y = int(keys[pygame.K_s] or keys[pygame.K_DOWN]) - int(keys[pygame.K_w] or keys[pygame.K_UP])
    return x, y


class Character:
    def __init__(self, name: str, x: float, y: float, sprite_def: dict, speed: float = 50):
        self.name = name
        self.x = x            # posição dos "pés", em pixels de jogo
        self.y = y
        self.speed = speed    # pixels de jogo por segundo
        self.dir = "down"
        self.facing = "right"  # último lado horizontal (para sprites de vista lateral)
        self.state = "idle"    # nome da animação: idle, walk, run, lie_down, sleep, wake, eat, jump
        self.sheets = load_sprite_set(sprite_def)
        # Como se move: "walk" (anda), "leap" (salta: takeoff -> leap -> land)
        # ou "burrow" (não anda; a rotina o faz viajar por baixo da terra)
        self.locomotion = sprite_def.get("locomotion", "walk")
        # Correr: a rotina liga `running` em trajetos longos; só vale se houver
        # a animação "run" (usa `run_speed` em vez de `speed`)
        self.running = False
        self.run_speed = sprite_def.get("run_speed", speed * 1.8)
        self.pinned = False        # teste de sprites: anda/corre sem sair do lugar
        # Variações escolhidas pela rotina (só valem se a animação existir):
        self.lantern = False       # noite: parado/andando com a lanterna
        self.tired = False         # cansado: idle "tired"
        self.walk_variant = None   # ex.: "walk_map" (andando lendo o mapa)
        self.swimming = False      # no lago: parado/andando viram nadar
        self.world = None          # último mundo recebido em update (cobre o corpo na água)
        self.area = None           # nome da área (ilha) onde está (Game/rotina mudam ao viajar)
        self.in_cave = False       # dentro da caverna: desenhado escurecido
        self.brain = None          # a rotina, se houver (ligada pelo Game)
        self.seat_drop = sprite_def.get("seat_drop", 0)
        self.seated_on = None      # (banco, assento) quando sentado
        self.seat_lift = 0.0       # altura extra do desenho (sentado no banco)
        self.animator = Animator()
        self.hit_now = False
        self.speech = None         # [texto, segundos restantes, duração total]
        self.font = pygame.font.Font(None, 30)

        sw, sh = sprite_def.get("shadow", (16, 5))
        self._shadow = pygame.Surface((sw, sh), pygame.SRCALPHA)
        pygame.draw.ellipse(self._shadow, (0, 0, 0, 56), self._shadow.get_rect())

    # Ações (por enquanto disparadas por tecla para testar os sprites;
    # depois a IA vai chamar estas mesmas funções).
    def do_action(self, name: str):
        """Toca uma animação (sleep/eat/jump). Ignora se não houver sprite."""
        if name in self.sheets:
            self.state = name
            self.animator.play(None)  # força reiniciar mesmo se já estava nela

    def toggle_sleep(self):
        """Dorme (deitando, se houver 'lie_down') ou acorda (com 'wake', se houver)."""
        if self.state in ("sleep", "lie_down"):
            if "wake" in self.sheets:
                self.do_action("wake")
            else:
                self.state = "idle"
        elif "lie_down" in self.sheets:
            self.do_action("lie_down")
        else:
            self.do_action("sleep")

    def say(self, text: str, secs: float | None = None):
        """Mostra um balão de fala acima da cabeça."""
        secs = secs or max(2.2, 1.2 + len(text) * 0.09)
        self.speech = [text, secs, secs]

    def feet_rect(self, x: float | None = None, y: float | None = None) -> pygame.Rect:
        """Área dos pés usada na colisão com objetos sólidos."""
        x = self.x if x is None else x
        y = self.y if y is None else y
        return pygame.Rect(round(x - 14), round(y - 8), 28, 10)

    def anim_name(self) -> str:
        """Animação de verdade para o estado atual (variações: nadar, lanterna,
        cansado, de costas/de frente, mapa). O `state` continua "idle"/"walk"."""
        s, has = self.state, self.sheets
        if self.swimming:
            alt = {"idle": "swim_idle", "walk": "swim", "run": "swim"}.get(s)
            return alt if alt in has else s
        if s in ("walk", "run"):
            if self.dir == "up" and "walk_up" in has:
                return "walk_up"          # andando de costas (para o fundo)
            if self.dir == "down" and "walk_down" in has:
                return "walk_down"        # andando de frente (para a câmera)
            if self.lantern and "lantern_walk" in has:
                return "lantern_walk"
            if s == "walk" and self.walk_variant in has:
                return self.walk_variant
        elif s == "idle":
            if self.lantern and "lantern_idle" in has:
                return "lantern_idle"
            if self.tired and "tired" in has:
                return "tired"
        return s

    def update(self, dt: float, axis: tuple[float, float], world):
        """`axis` = direção de movimento (x, y) — do teclado (read_axis) ou da rotina."""
        self.world = world
        self.hit_now = False  # vira True no quadro em que um ataque acerta
        if self.speech:
            self.speech[1] -= dt
            if self.speech[1] <= 0:
                self.speech = None
        x, y = axis
        length = math.hypot(x, y)
        if self.locomotion == "burrow":
            length = 0.0                     # não anda (a rotina cuida de enterrar/brotar)
        if length > 0.01 and self.locomotion == "leap":
            x, y = x / length, y / length
            self.dir = dir_from_vector(round(x * 1.4), round(y * 1.4))
            if abs(x) > 0.2 and self.state != "leap":
                self.facing = "right" if x > 0 else "left"
            if self.state not in ("takeoff", "leap", "land"):
                self.do_action("takeoff")    # cada salto: agacha -> voa -> aterrissa
            if self.state == "leap":         # só avança enquanto está no ar
                nx = self.x + x * self.speed * dt
                if not world.blocked(self.feet_rect(nx, self.y)):
                    self.x = nx
                ny = self.y + y * self.speed * dt
                if not world.blocked(self.feet_rect(self.x, ny)):
                    self.y = ny
            length = 0.0                     # (pula a parte de "andar" abaixo)
        if length > 0.01:  # andar cancela qualquer ação
            x, y = x / length, y / length  # diagonal não fica mais rápida
            run = self.running and "run" in self.sheets
            # vetor menor que 1 = passo mais curto (a rotina freia ao chegar no ponto)
            speed = (self.run_speed if run else self.speed) * min(1.0, length)
            if self.swimming:
                speed *= 0.5                 # nada mais devagar
            # na água só anda onde é água; em terra, onde é andável e livre
            if self.swimming:
                free = world.swimmable
            else:
                def free(r):
                    return not world.blocked(r)
            # Move um eixo por vez: assim ele "desliza" encostado nos objetos
            nx = self.x + x * speed * dt
            if free(self.feet_rect(nx, self.y)):
                self.x = nx
            ny = self.y + y * speed * dt
            if free(self.feet_rect(self.x, ny)):
                self.y = ny
            # direção "dominante" (ignora componentes pequenos)
            self.dir = dir_from_vector(round(x * 1.4), round(y * 1.4))
            if abs(x) > 0.2:
                self.facing = "right" if x > 0 else "left"
            self.state = "run" if run else "walk"
        elif self.state in ("walk", "run") and not self.pinned:
            self.state = "idle"
        world.clamp(self)

        name = self.anim_name()
        sheet = self.sheets.get(name)
        prev = sheet.frame_at(self.animator.time) if sheet and self.animator.name == name else -1
        self.animator.play(name)
        self.animator.update(dt)
        if sheet and sheet.hit_frame is not None and prev < sheet.hit_frame <= sheet.frame_at(self.animator.time):
            self.hit_now = True

        # Ações de uma vez só (loop=False) seguem para a próxima ao terminar
        # (padrão idle; ex.: lie_down -> sleep)
        # ("hold" = fica parado no último quadro até alguém mudar o estado)
        if sheet and not sheet.loop and self.animator.time >= sheet.duration and sheet.next_state != "hold":
            self.state = sheet.next_state if sheet.next_state in self.sheets else "idle"

    def current_frame(self):
        """(sheet, frame) a desenhar, ou None se não houver sprite."""
        sheet = self.sheets.get(self.anim_name())
        if sheet:
            return sheet, sheet.frame_at(self.animator.time)
        if self.state == "idle" and "walk" in self.sheets:
            return self.sheets["walk"], 0  # sem 'idle': 1º quadro do 'walk'
        return None

    def draw(self, surface: pygame.Surface, viewer=None, tint: float = 1.0):
        """`tint` < 1 escurece (ex.: debaixo da árvore)."""
        if not self.swimming:
            surface.blit(self._shadow, self._shadow.get_rect(center=(round(self.x), round(self.y))))
        cur = self.current_frame()
        if cur:
            sheet, frame = cur
            lift = sheet.lift_at(self.animator.time) if sheet.name == self.animator.name else 0
            sheet.draw(surface, frame, self.dir, self.x, self.y, self.facing, lift + self.seat_lift, tint)
            if sheet.effect:
                self._draw_effect(surface, sheet)
            if self.swimming and self.world is not None:
                self._draw_water_cover(surface)
        else:
            self._draw_placeholder(surface)

    def _flip_side(self, sheet) -> bool:
        """True se o desenho está espelhado (olhando para o lado oposto da arte)."""
        if not sheet.art_faces:
            return False
        side = "right" if "right" in self.dir else "left" if "left" in self.dir else self.facing
        return side != sheet.art_faces

    def _draw_effect(self, surface, sheet):
        """Brilho do golpe (outra pasta), por cima do corpo, a partir do quadro `start`."""
        fx = sheet.effect
        t = self.animator.time - fx["start"]
        if t < 0:
            return
        i = int(t / fx["frame_duration"])
        if i >= len(fx["frames"]):
            return
        flip = self._flip_side(sheet)
        img = (fx["flipped"] if flip else fx["frames"])[i]
        dx, dy = fx["at"]
        center = (round(self.x + (-dx if flip else dx)), round(self.y + dy - self.seat_lift))
        surface.blit(img, img.get_rect(center=center))

    WATERLINE = 36    # px acima dos pés onde fica a superfície da água (nadando)

    def _draw_water_cover(self, surface):
        """Nadando: cobre o corpo abaixo da linha d'água com a própria água do lago
        (meio transparente), para as pernas parecerem submersas."""
        w = self.world
        ox, oy = w.ground_pos
        top = round(self.y - self.WATERLINE)
        area = pygame.Rect(round(self.x - 60), top, 120, round(self.y + 30) - top)
        src = area.move(-ox, -oy).clip(w.ground.get_rect())
        if not src.w or not src.h:
            return
        patch = w.ground.subsurface(src).copy()
        patch.set_alpha(185)
        surface.blit(patch, (src.x + ox, src.y + oy))

    def draw_light(self, surface, darkness: float):
        """Luz da lanterna (depois do escurecimento): brilho na lanterna e uma poça
        de luz no chão À FRENTE, para onde ele está virado."""
        cur = self.current_frame()
        if not cur or darkness < 0.08:
            return
        sheet, frame = cur
        if not sheet.glow or frame >= len(sheet.glow) or sheet.glow[frame] is None:
            return
        from .props import add_light, radial_glow
        if not hasattr(Character, "_lamp"):
            Character._lamp = radial_glow(46, (255, 236, 170))
            pool = radial_glow(120, (150, 130, 80))
            Character._pool = pygame.transform.smoothscale(pool, (300, 92))
        gx, gy = sheet.glow[frame]
        flip = self._flip_side(sheet)
        ax = sheet.fw - sheet.anchor[0] if flip else sheet.anchor[0]
        if flip:
            gx = sheet.fw - gx
        px = self.x - ax + gx
        py = self.y - sheet.anchor[1] + gy - self.seat_lift
        k = min(1.0, darkness * 1.4)
        add_light(surface, Character._lamp, (px, py), k)
        ahead = 0 if sheet.art_faces is None else (1 if self.facing == "right" else -1)
        add_light(surface, Character._pool, (self.x + ahead * 95, self.y + 4), k * 0.85)

    def draw_speech(self, surface: pygame.Surface):
        """Balão de fala (desenhado por cima de tudo, depois da luz/chuva)."""
        if not self.speech:
            return
        text, left, total = self.speech
        alpha = min(1.0, left / 0.35, (total - left) / 0.15 + 0.2)  # aparece/some suave
        txt = self.font.render(text, True, (38, 40, 52))
        w, h = txt.get_width() + 22, txt.get_height() + 12
        bubble = pygame.Surface((w, h + 10), pygame.SRCALPHA)
        pygame.draw.rect(bubble, (60, 64, 80), (0, 0, w, h), border_radius=10)
        pygame.draw.rect(bubble, (250, 250, 246), (2, 2, w - 4, h - 4), border_radius=9)
        tail = [(w // 2 - 8, h - 3), (w // 2 + 8, h - 3), (w // 2, h + 8)]
        pygame.draw.polygon(bubble, (60, 64, 80), tail)
        pygame.draw.polygon(bubble, (250, 250, 246), [(w // 2 - 5, h - 4), (w // 2 + 5, h - 4), (w // 2, h + 4)])
        bubble.blit(txt, (11, 6))
        bubble.set_alpha(round(255 * max(0.0, alpha)))
        cur = self.current_frame()
        lift = cur[0].lift_at(self.animator.time) if cur and cur[0].name == self.animator.name else 0
        top = 92 if self.state in ("sleep", "lie_down") else 128  # deitado = mais baixo
        x = max(4, min(surface.get_width() - w - 4, round(self.x - w / 2)))
        surface.blit(bubble, (x, round(self.y - top - lift - self.seat_lift - h)))

    def _draw_placeholder(self, surface: pygame.Surface):
        """Boneco temporário (desenhado por código) quando faltam sprites."""
        t = self.animator.time
        if self.state == "walk":
            bob = round(abs(math.sin(t * 14)) * 3)
        else:
            bob = round(math.sin(t * 3) * 0.6)
        x, y = round(self.x), round(self.y) - bob
        up = self.dir.startswith("up")
        lx = -2 if "left" in self.dir else 2 if "right" in self.dir else 0

        pygame.draw.ellipse(surface, (90, 174, 224), (x - 8, y - 14, 16, 14))        # corpo
        if not up:
            pygame.draw.ellipse(surface, (223, 241, 255), (x - 4 + lx, y - 8, 8, 6))  # barriga
        for dx in (-6, -2, 2, 6):                                                     # espuma
            pygame.draw.circle(surface, (255, 255, 255), (x + dx, y - 12), 2)
        if not up:                                                                    # olhos
            for ex in (-5, 2):
                surface.fill((255, 230, 128), (x + ex + lx, y - 18, 3, 3))
                surface.fill((26, 26, 26), (x + ex + 1 + lx, y - 17, 1, 1))
