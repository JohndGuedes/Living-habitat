"""Ações de contexto do personagem controlado (tecla E).

Perto de algo com que dá para interagir, aparece em cima da cabeça "[E] ação"; apertar E
começa a ação. Cada ação vira uma tarefa da rotina (brain.t_player), e no fim o jogador
continua no controle (a rotina volta depois de MANUAL_PAUSE sem teclas).

  fruta no chão          Pegar fruta     abaixa, pega e come (fome −0,6)
  árvore de frutas       Bater na árvore golpe: a árvore balança e derruba uma fruta
  boneco de treino       Treinar         sequência de golpes (o boneco vai quebrando; F também bate)
  banco (assento livre)  Sentar          senta; sentado: "Levantar" (E de novo ou andar)
  beira do lago (água)   Nadar           pula na água; nadando anda com WASD
  nadando, perto da beira Sair da água   pula de volta para a margem
  ponta de um pulo       Pular           pula a cachoeira (Espaço também faz)
"""
import math

import pygame

from .config import CHARACTER_SCALE

REACH = 42          # px de tela: distância para a ação aparecer


def find_action(game, ch):
    """(rótulo, nome da tarefa, gerador-fábrica) da ação disponível para `ch`, ou None."""
    w, b = game.worlds[ch.area], ch.brain
    if ch.seated_on:
        return "Levantar", "stand", None
    if ch.sleeping_in:
        return "Levantar da cama", "wake_bed", None
    if ch.swimming:
        spot = _nearest(b._swim_spots(), (ch.x, ch.y), key=lambda s: s[3], limit=REACH + 20)
        if spot:
            return "Sair da água", "sair da água", lambda: b.t_exit_water(spot)
        return None
    fruits = [f for f in getattr(w, "fruits", []) if f.landed and not f.eaten and f.claimed in (None, ch)]
    f = _nearest(fruits, (ch.x, ch.y), key=lambda f: (f.x, f.y), limit=REACH)
    if f:
        return "Pegar fruta", "comer", lambda: b.t_pick_fruit(f)
    for tree in getattr(w, "fruit_trees", []):
        half = tree.frames[0].get_width() * 0.45
        if abs(ch.x - tree.x) < half and abs(ch.y - tree.y) < 28 * max(1.0, CHARACTER_SCALE / 0.6):
            if tree.fruits > 0:
                return "Bater na árvore", "comer", lambda: b.t_hit_tree(tree)
            return "Árvore sem frutas", None, None
    for dm in getattr(w, "dummies", []):
        half = dm.frames[0].get_width() * 0.45
        if abs(ch.x - dm.x) < half and abs(ch.y - dm.y) < 30:
            if dm.destroyed:
                return "Boneco quebrado", None, None
            return "Treinar", "treinar", lambda dm=dm: b.t_train_dummy(dm, walk=False)
    for sm in getattr(w, "snowmen", []):
        half = 24 + sm.frames[0].get_width() * 0.45
        if abs(ch.x - sm.x) < half and abs(ch.y - sm.y) < 34:
            if sm.destroyed:
                return "Montar boneco", "boneco de neve", lambda sm=sm: b.t_build_snowman(sm, walk=False)
            return "Quebrar boneco", "boneco de neve", lambda sm=sm: b.t_break_snowman(sm, walk=False)
    for cf in getattr(w, "campfires", []):
        half = 26 + cf.frames[0].get_width() * 0.45
        if abs(ch.x - cf.x) < half and abs(ch.y - cf.y) < 36:
            if cf.lit:
                return "Apagar fogueira", "fogueira", lambda cf=cf: b.t_toggle_campfire(cf, walk=False)
            return "Acender fogueira", "fogueira", lambda cf=cf: b.t_toggle_campfire(cf, walk=False)
    for gn in getattr(w, "grubs_natal", []):
        half = 24 + gn.frames[0].get_width() * 0.45
        if abs(ch.x - gn.x) < half and abs(ch.y - gn.y) < 34:
            if gn.state == "jar":
                return "Libertar Grub", "grub de natal", lambda gn=gn: b.t_free_grub_natal(gn, walk=False)
            if gn.state == "free":
                return "Brincar com o Grub", "grub de natal", lambda gn=gn: b.t_play_grub_natal(gn, walk=False)
            if gn.state == "snow":
                return "Chamar o Grub", "grub de natal", lambda gn=gn: b.t_play_grub_natal(gn, walk=False)
    for bed in getattr(w, "beds", []):
        if bed.is_free(ch) and math.dist(bed.approach(), (ch.x, ch.y)) < REACH + 18:
            return "Dormir na cama", "dormir", lambda bed=bed: b.t_sleep_in_bed(bed, walk=True)
    for bench in getattr(w, "benches", []):
        i = bench.free_seat(ch)
        if i is not None and math.dist(bench.approach(i), (ch.x, ch.y)) < REACH + 10:
            return "Sentar", "banco", lambda: b.t_sit_here(bench, i)
    for ex in getattr(w, "exits", []):
        if math.dist(ex["at"], (ch.x, ch.y)) < REACH + 18:
            label = ex.get("label") or ("Entrar na casa" if ex["to"] == "casa" else "Sair da casa")
            return label, "viajar", lambda to=ex["to"]: b.go_area(to)
    for jump in getattr(w, "jumps", []):
        if min(math.dist(p, (ch.x, ch.y)) for p in jump) < REACH:
            return "Pular", "pular a cachoeira", lambda: b.t_leap_falls(jump, start_near=True)
    if not getattr(w, "frozen", False) and "swim" in ch.sheets:
        spot = _nearest(b._swim_spots(), (ch.x, ch.y), key=lambda s: (s[0], s[1]), limit=REACH + 10)
        if spot:
            return "Nadar", "nadar", lambda: b.t_enter_water(spot)
    return None


def _nearest(items, pos, key, limit):
    best, best_d = None, limit
    for it in items:
        d = math.dist(key(it), pos)
        if d < best_d:
            best, best_d = it, d
    return best


def do_action(game, ch):
    """E apertado: começa a ação disponível. Retorna True se havia uma."""
    act = find_action(game, ch)
    if not act:
        return False
    label, name, make = act
    b = ch.brain
    if name == "stand":
        b.stand_request = True                  # a tarefa de sentar levanta sozinha
        b.manual = 0
        return True
    if name == "wake_bed":
        ch.toggle_sleep()
        b.leave_bed()
        b.manual = 0
        return True
    if make is None:
        return True                             # só informativo ("Árvore sem frutas")
    b.force(name, b.t_player(make()))
    b.manual = 0
    return True


class Prompt:
    """Balãozinho "[E] ação" em cima da cabeça do personagem controlado."""

    def __init__(self):
        self.font = pygame.font.Font(None, 24)
        self.key_font = pygame.font.Font(None, 22)
        self._cache = {}

    def draw(self, surface, ch, label, enabled=True):
        key = (label, enabled)
        img = self._cache.get(key)
        if img is None:
            txt = self.font.render(label, True, (40, 42, 55) if enabled else (110, 110, 120))
            k = self.key_font.render("E", True, (255, 255, 255))
            kw = k.get_width() + 10
            w, h = kw + txt.get_width() + 18, max(txt.get_height(), k.get_height()) + 10
            img = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(img, (250, 250, 246, 235), (0, 0, w, h), border_radius=8)
            pygame.draw.rect(img, (70, 74, 92), (0, 0, w, h), 2, border_radius=8)
            pygame.draw.rect(img, (70, 74, 92) if enabled else (150, 150, 160), (5, 5, kw, h - 10), border_radius=5)
            img.blit(k, k.get_rect(center=(5 + kw / 2, h / 2)))
            img.blit(txt, (kw + 12, (h - txt.get_height()) / 2))
            self._cache[key] = img
        top = 128 * CHARACTER_SCALE + (34 if ch.speech else 6) + ch.seat_lift
        x = max(4, min(surface.get_width() - img.get_width() - 4, round(ch.x - img.get_width() / 2)))
        surface.blit(img, (x, round(ch.y - top - img.get_height())))
