"""Janela, loop principal e overlay de debug."""
import logging

import pygame

from .apparition import Shade
from .brain import Brain, GrubBrain, HornetBrain
from .character import Character, read_axis
from .config import CHARACTER, DEBUG, FPS, HEIGHT, TITLE, WIDTH
from .environment import Environment
from .scene import SPAWN, SPAWNS
from .social import Society
from .sprite_defs import CHARACTER_SPRITES
from .window import PopupWindow
from .world import World


class Game:
    def __init__(self, online: bool = True):
        logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
        pygame.init()
        # Janela popup (fixar por cima, sem borda, tamanho livre...). O jogo desenha
        # sempre em `self.screen` (WIDTHxHEIGHT) e a janela escala para o tamanho dela.
        self.window = PopupWindow((WIDTH, HEIGHT), TITLE)
        self.screen = pygame.Surface((WIDTH, HEIGHT)).convert()
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 26)
        self.debug = DEBUG
        self.running = True

        self.world = World(WIDTH, HEIGHT)
        self.env = Environment(WIDTH, HEIGHT, online=online)
        # Moradores: o Knight (que o teclado controla) + Hornet + Grub.
        # Cada um tem sua rotina (brain.py) e eles se encontram (social.py).
        brains = {"knight": Brain, "hornet": HornetBrain, "grub": GrubBrain}
        self.members = {}
        for key in (CHARACTER, "hornet", "grub"):
            sd = CHARACTER_SPRITES[key]
            ch = Character(key.capitalize(), *SPAWNS.get(key, SPAWN), sprite_def=sd, speed=sd.get("speed", 55))
            ch.x, ch.y = self.world.nearest_walkable(ch.x, ch.y, ch.feet_rect)
            self.members[key] = ch
        self.character = self.members[CHARACTER]          # o controlado pelo teclado
        self.characters = list(self.members.values())
        self.world.build_nav(self.character.feet_rect)
        for key, ch in self.members.items():
            brains.get(key, Brain)(ch, self.world, self.env)
            ch.brain.others = [o for o in self.characters if o is not ch]
        self.brain = self.character.brain
        self.society = Society(self.members, self.world)
        # A Sombra: aparece de vez em quando à noite ou na chuva (tecla G chama)
        self.shade = Shade(self.world, self.env, self.characters)

    def handle_events(self):
        for event in pygame.event.get():
            handled = self.window.handle_event(event)
            if handled == "quit":
                self.running = False
            if handled:
                continue
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_p:
                    self.debug = not self.debug
                # Teclas de teste das animações
                elif event.key == pygame.K_z:
                    self.brain.take_manual()
                    self.character.toggle_sleep()
                elif event.key == pygame.K_e:
                    self.brain.take_manual()
                    self.character.do_action("eat")
                elif event.key == pygame.K_SPACE:
                    self.brain.take_manual()
                    self.character.do_action("jump")
                elif event.key == pygame.K_f:
                    self.brain.take_manual()
                    self.character.do_action("attack")
                # Testar ambiente: T = hora (auto/dia/tarde/noite), R = chuva (auto/sim/não)
                elif event.key == pygame.K_t:
                    self.env.cycle_time()
                elif event.key == pygame.K_r:
                    self.env.cycle_rain()
                elif event.key == pygame.K_g:
                    self.shade.appear()             # chama a Sombra (teste)

    def step(self, dt: float):
        """Um quadro de lógica + desenho (separado do loop para facilitar testes)."""
        self.handle_events()
        c = self.character
        keys_axis = read_axis(pygame.key.get_pressed())
        if keys_axis != (0, 0):
            self.brain.take_manual()        # jogador no controle por alguns segundos
        click = self.window.pop_click()
        if click:                           # clicou em alguém? (o mais à frente)
            for ch in sorted(self.characters, key=lambda o: -o.y):
                if pygame.Rect(ch.x - 40, ch.y - 120, 80, 125).collidepoint(click):
                    ch.brain.poke()
                    break
        self.society.update(dt)
        for ch in self.characters:
            axis = ch.brain.update(dt)
            if ch is c and keys_axis != (0, 0):
                axis = keys_axis
            ch.update(dt, axis, self.world)
        self.separate(dt)
        self.world.update(dt, wind=1 + 1.5 * self.env.rain, actors=self.characters)
        self.env.update(dt)
        self.shade.update(dt)
        if self.shade.pop_appeared():             # os moradores reagem
            for ch in self.characters:
                ch.brain.react_shade(self.shade)
        if c.hit_now:
            self.resolve_hit()

        self.world.draw(self.screen)
        # Profundidade: quem está mais embaixo na tela (y maior) fica na frente
        for obj in sorted(self.world.drawables + self.characters, key=lambda o: o.y):
            if obj in self.characters:
                obj.draw(self.screen, tint=self.world.shade_at(obj.x, obj.y))
            else:
                obj.draw(self.screen, viewer=c)
        self.env.apply_light(self.screen)                      # noite / tarde / céu nublado
        self.world.draw_lights(self.screen, self.env.darkness)  # fogueira, janelas, poste
        self.shade.draw(self.screen)                           # a Sombra (não escurece)
        self.env.draw_weather(self.screen)                     # chuva e relâmpagos
        for ch in self.characters:
            ch.draw_speech(self.screen)                        # balões de fala
        self.env.draw_hud(self.screen)
        if self.debug:
            self.draw_debug()
        self.window.present(self.screen)

    def separate(self, dt, min_dist=46):
        """Personagens muito colados se afastam devagar (um não some atrás do outro)."""
        chars = [c for c in self.characters if c.state not in ("sleep", "lie_down") and not c.seated_on]
        for i, a in enumerate(chars):
            for b in chars[i + 1:]:
                dx, dy = b.x - a.x, (b.y - a.y) * 2      # profundidade conta mais
                d = (dx * dx + dy * dy) ** 0.5
                if d >= min_dist:
                    continue
                if d < 0.01:
                    dx, d = 1.0, 1.0
                push = (min_dist - d) * dt * 2.5
                for who, sign in ((a, -1), (b, 1)):
                    if who.locomotion == "burrow":
                        continue                      # o Grub não é empurrado
                    nx = who.x + sign * dx / d * push
                    if not self.world.blocked(who.feet_rect(nx, who.y)):
                        who.x = nx

    def resolve_hit(self):
        """Golpe do ferrão: acerta bonecos à frente do personagem, perto e na mesma "faixa"."""
        c = self.character
        side = 1 if c.facing == "right" else -1
        for p in self.world.props:
            if hasattr(p, "hit") and 0 < (p.x - c.x) * side < 130 and abs(p.y - c.y) < 50:
                p.hit(c.facing)

    def draw_debug(self):
        p = self.character
        lines = [
            f"fps {self.clock.get_fps():.0f}",
            f"pos {p.x:.0f},{p.y:.0f}  dir {p.dir}",
            f"state {p.state}  facing {p.facing}",
            f"rotina: {self.brain.task_name}" + (f" (manual {self.brain.manual:.0f}s)" if self.brain.manual > 0 else ""),
            f"energia {self.brain.energy:.2f}  fome {self.brain.hunger:.2f}  "
            f"sede {self.brain.thirst:.2f}  tédio {self.brain.boredom:.2f}",
        ]
        cur = p.current_frame()
        if cur:
            sheet, frame = cur
            w, h = sheet.image_size
            lines.append(f"{sheet.name} {w}x{h}  quadro {sheet.fw}x{sheet.fh}")
            lines.append(f"frame {frame + 1}/{sheet.frames}  row {sheet.row_for(p.dir)}")
        else:
            lines.append("placeholder (sem sprite)")
        for key, ch in self.members.items():
            if ch is not p:
                lines.append(f"{key}: {ch.brain.task_name} ({ch.state})  E{ch.brain.energy:.2f}")
        lines.append(f"encontro: {self.society.current or '-'}  |  sombra: "
                     + (f"em cena ({self.shade.left:.0f}s)" if self.shade.visible
                        else f"próxima tentativa {self.shade.timer:.0f}s" + ("" if self.shade.eligible()
                                                                           else " (só noite/chuva)")))
        lines.append("Z dormir  E comer  Espaco pular  F atacar")
        lines.append("T hora (auto/dia/tarde/noite)  R chuva (auto/sim/nao)  G chamar a Sombra")

        # área andável (azul), áreas sólidas (vermelho) e pés do personagem (amarelo)
        self.world.draw_debug(self.screen)
        for prop in self.world.props:
            if prop.solid:
                pygame.draw.rect(self.screen, (255, 60, 60), prop.solid, 1)
        pygame.draw.rect(self.screen, (255, 230, 60), p.feet_rect(), 1)

        rendered = [self.font.render(line, True, (184, 255, 207)) for line in lines]
        box_w = max(r.get_width() for r in rendered) + 10
        box_h = sum(r.get_height() for r in rendered) + 8
        bg = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 160))
        self.screen.blit(bg, (6, 6))
        y = 9
        for r in rendered:
            self.screen.blit(r, (10, y))
            y += r.get_height()

    def run(self):
        while self.running:
            # Sem foco (só observando), roda a 30 fps para gastar menos
            fps = FPS if pygame.key.get_focused() else 30
            dt = min(self.clock.tick(fps) / 1000, 0.1)  # evita saltos grandes
            self.step(dt)
        self.window.save()
        pygame.quit()
