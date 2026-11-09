"""Janela, loop principal e overlay de debug."""
import logging

import pygame

from .apparition import Shade
from .brain import Brain, DaughterBrain, GrubBrain, HornetBrain
from .character import Character, read_axis
from .config import CHARACTER, DEBUG, FPS, HEIGHT, RESIDENTS, SHADE_ENABLED, TITLE, WIDTH
from .environment import Environment
from .scene import AREAS, START_AREA
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

        # Áreas (ilhas) do habitat: cada uma é um World (scene.AREAS). A tela mostra
        # a área onde o Knight está; ele viaja pelas saídas (tecla C = ir para a outra).
        self.worlds = {name: World(WIDTH, HEIGHT, name) for name in AREAS}
        self.env = Environment(WIDTH, HEIGHT, online=online)
        start = self.worlds[START_AREA]
        # Moradores (config.RESIDENTS): o Knight (que o teclado controla) e quem mais
        # estiver na lista. Cada um tem sua rotina (brain.py) e eles se encontram (social.py).
        brains = {"knight": Brain, "hornet": HornetBrain, "grub": GrubBrain, "daughter": DaughterBrain}
        self.members = {}
        for key in dict.fromkeys((CHARACTER,) + tuple(RESIDENTS)):
            sd = CHARACTER_SPRITES[key]
            ch = Character(key.capitalize(), *start.spawns.get(key, start.spawn), sprite_def=sd,
                           speed=sd.get("speed", 55))
            ch.x, ch.y = start.nearest_walkable(ch.x, ch.y, ch.feet_rect)
            ch.area = START_AREA
            self.members[key] = ch
        self.character = self.members[CHARACTER]          # o controlado pelo teclado
        self.characters = list(self.members.values())
        for w in self.worlds.values():
            w.build_nav(self.character.feet_rect)
        for key, ch in self.members.items():
            brains.get(key, Brain)(ch, start, self.env)
            ch.brain.worlds = self.worlds
            ch.brain.others = [o for o in self.characters if o is not ch]
        self.viewing = START_AREA            # área mostrada (muda com escurecimento)
        self.fade = 0.0                      # 1 = tela preta (troca de área)
        self.brain = self.character.brain
        # encontros só com 2 ou mais moradores
        self.society = Society(self.members, start) if len(self.members) > 1 else None
        # A Sombra: aparece de vez em quando à noite ou na chuva (tecla G chama)
        self.shade = Shade(start, self.env, self.characters) if SHADE_ENABLED else None
        # Teste de sprites: N/B percorrem as animações; M liga/desliga a rotina
        self.anim_names = list(self.character.sheets)
        self.anim_index = 0
        self.routine_on = True
        self.flash = None                    # [texto, segundos] mostrado no topo

    @property
    def world(self):
        """A área que está na tela (a do Knight)."""
        return self.worlds[self.viewing]

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
                elif event.key == pygame.K_g and self.shade:
                    self.shade.appear()             # chama a Sombra (teste)
                # Teste de sprites: N = próxima animação, B = anterior, M = rotina on/off
                elif event.key in (pygame.K_n, pygame.K_b) and self.anim_names:
                    step = 1 if event.key == pygame.K_n else -1
                    self.anim_index = (self.anim_index + step) % len(self.anim_names)
                    self.play_test(self.anim_names[self.anim_index])
                elif event.key == pygame.K_TAB:    # troca quem o teclado controla
                    self.switch_control()
                elif event.key == pygame.K_c:      # ir para a outra ilha (teste)
                    self.brain.take_manual()
                    others = [n for n in self.worlds if n != self.character.area]
                    if others:
                        self.brain.enter_area(others[0])
                elif event.key == pygame.K_m:
                    self.routine_on = not self.routine_on
                    if not self.routine_on:
                        self.brain.take_manual()
                    else:
                        self.brain.manual = 0
                    self.show("rotina " + ("LIGADA" if self.routine_on else "DESLIGADA (fica parado)"))

    def switch_control(self):
        """Tab: o teclado e as teclas de teste passam para o próximo morador que tenha
        as animações (o anterior volta para a própria rotina)."""
        ok = [c for c in self.characters if c.locomotion == "walk"]
        if len(ok) < 2:
            return
        self.brain.manual = 0
        self.character.pinned = False
        self.character = ok[(ok.index(self.character) + 1) % len(ok)]
        self.brain = self.character.brain
        self.anim_names = list(self.character.sheets)
        self.anim_index = 0
        self.routine_on = True
        self.show(f"controlando: {self.character.name}")

    def play_test(self, name):
        """Toca uma animação do Knight para conferir o sprite."""
        self.brain.take_manual()
        c = self.character
        c.state = name
        c.pinned = name in ("walk", "run")    # andar/correr no lugar, para ver o ciclo
        c.animator.play(None)
        sheet = c.sheets[name]
        self.show(f"{name}  ({self.anim_index + 1}/{len(self.anim_names)})  {sheet.frames} quadros"
                  + ("" if sheet.loop else "  [toca 1x]"))

    def show(self, text, secs=2.5):
        self.flash = [text, secs]

    def step(self, dt: float):
        """Um quadro de lógica + desenho (separado do loop para facilitar testes)."""
        self.handle_events()
        c = self.character
        keys_axis = read_axis(pygame.key.get_pressed())
        if keys_axis != (0, 0):
            c.pinned = False
        if keys_axis != (0, 0) or not self.routine_on:
            self.brain.take_manual()        # jogador no controle (ou rotina desligada)
        click = self.window.pop_click()
        if click:                           # clicou em alguém? (o mais à frente)
            for ch in sorted(self.characters, key=lambda o: -o.y):
                if pygame.Rect(ch.x - 40, ch.y - 120, 80, 125).collidepoint(click):
                    ch.brain.poke()
                    break
        if self.society:
            self.society.update(dt)
        for ch in self.characters:
            axis = ch.brain.update(dt)
            if ch is c and keys_axis != (0, 0):
                axis = keys_axis
            ch.update(dt, axis, self.worlds[ch.area])
        if keys_axis != (0, 0):              # andando com o teclado até uma saída: viaja
            for e in self.worlds[c.area].exits:
                if abs(c.x - e["at"][0]) < 26 and abs(c.y - e["at"][1]) < 20:
                    self.brain.enter_area(e["to"])
                    break
        # o Knight mudou de área: escurece e mostra a outra
        if c.area != self.viewing:
            self.viewing = c.area
            self.fade = 1.0
        self.fade = max(0.0, self.fade - dt * 2.2)
        here = [ch for ch in self.characters if ch.area == self.viewing]
        self.separate(dt, here)
        self.world.update(dt, wind=1 + 1.5 * self.env.rain, actors=here)
        self.env.update(dt)
        if self.shade:
            self.shade.update(dt)
            if self.shade.pop_appeared():         # os moradores reagem
                for ch in self.characters:
                    ch.brain.react_shade(self.shade)
        if c.hit_now:
            self.resolve_hit()

        self.world.draw(self.screen)
        # Profundidade: quem está mais embaixo na tela (y maior) fica na frente
        for obj in sorted(self.world.drawables + here, key=lambda o: o.y):
            if obj in here:
                tint = self.world.shade_at(obj.x, obj.y)
                if obj.in_cave:
                    tint = min(tint, 0.45)       # lá dentro da caverna: escuro
                obj.draw(self.screen, tint=tint)
            else:
                obj.draw(self.screen, viewer=c)
        self.env.apply_light(self.screen)                      # noite / tarde / céu nublado
        self.world.draw_lights(self.screen, self.env.darkness)  # fogueira, janelas, poste
        for ch in here:
            ch.draw_light(self.screen, self.env.darkness)       # lanterna do Knight
        if self.shade:
            self.shade.draw(self.screen)                       # a Sombra (não escurece)
        self.env.draw_weather(self.screen)                     # chuva e relâmpagos
        for ch in here:
            ch.draw_speech(self.screen)                        # balões de fala
        self.env.draw_hud(self.screen)
        self.draw_flash(dt)
        if self.debug:
            self.draw_debug()
        if self.fade > 0:                     # escurecimento da troca de área
            veil = pygame.Surface(self.screen.get_size())
            veil.set_alpha(round(255 * min(1.0, self.fade)))
            self.screen.blit(veil, (0, 0))
        self.window.present(self.screen)

    def separate(self, dt, chars=None, min_dist=46):
        """Personagens muito colados se afastam devagar (um não some atrás do outro)."""
        chars = [c for c in (chars if chars is not None else self.characters)
                 if c.state not in ("sleep", "lie_down") and not c.seated_on and not c.in_cave]
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
            f"área {p.area}  pos {p.x:.0f},{p.y:.0f}  dir {p.dir}" + ("  (na caverna)" if p.in_cave else ""),
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
        if self.society:
            lines.append(f"encontro: {self.society.current or '-'}")
        if self.shade:
            lines.append("sombra: " + (f"em cena ({self.shade.left:.0f}s)" if self.shade.visible
                                       else f"próxima tentativa {self.shade.timer:.0f}s"
                                       + ("" if self.shade.eligible() else " (só noite/chuva)")))
        lines.append("Z dormir  E comer  Espaco pular  F atacar")
        lines.append("N/B animação seguinte/anterior  M rotina " + ("on" if self.routine_on else "OFF")
                     + ("  C outra ilha" if len(self.worlds) > 1 else "") + "  Tab trocar personagem")
        lines.append("T hora (auto/dia/tarde/noite)  R chuva (auto/sim/nao)"
                     + ("  G chamar a Sombra" if self.shade else ""))

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

    def draw_flash(self, dt):
        """Aviso curto no topo da tela (nome da animação em teste etc.)."""
        if not self.flash:
            return
        self.flash[1] -= dt
        if self.flash[1] <= 0:
            self.flash = None
            return
        txt = self.font.render(self.flash[0], True, (255, 255, 255))
        bg = pygame.Surface((txt.get_width() + 20, txt.get_height() + 10), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 150))
        x = (self.screen.get_width() - bg.get_width()) // 2
        self.screen.blit(bg, (x, 12))
        self.screen.blit(txt, (x + 10, 17))

    def run(self):
        while self.running:
            # Sem foco (só observando), roda a 30 fps para gastar menos
            fps = FPS if pygame.key.get_focused() else 30
            dt = min(self.clock.tick(fps) / 1000, 0.1)  # evita saltos grandes
            self.step(dt)
        self.window.save()
        pygame.quit()
