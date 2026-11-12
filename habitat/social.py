"""Interações entre personagens (Knight, Hornet, Grub).

De tempos em tempos a "sociedade" procura dois personagens livres (acordados,
sem necessidade urgente, fazendo algo à toa) e começa um ENCONTRO:

  1. os dois vão até pontos lado a lado, virados um para o outro
     (o Grub fica onde está: os outros vão até ele);
  2. um roteiro é encenado: falas alternadas e ações (golpe, pulo, festa...);
  3. cada um volta à própria rotina.

Roteiros ficam em SCRIPTS: (quem, fala, ação). "a" e "b" são os dois
participantes na ordem da chave do par. Ações = nomes de animação.
Edite / acrescente à vontade.
"""
import math
import random

from .config import CHARACTER_SCALE

# par -> lista de roteiros. Cada passo: (quem, texto ou None, ação ou None)
SCRIPTS = {
    ("knight", "hornet"): [
        [("b", "Pequeno fantasma.", None), ("a", "...", None), ("b", "Ainda de pé? Ótimo.", None),
         ("a", "oi!", "jump")],
        [("a", "oi!", None), ("b", "Hmph. Não me atrapalhe.", None), ("a", "...", None),
         ("b", "Tá bom. Oi.", None)],
        [("b", "Vamos ver se melhorou.", None), ("a", "!", None),
         ("b", "Shaw!", "attack"), ("a", "hyah!", "attack"), ("b", "Garama!", "attack"),
         ("a", "tá!", "attack"), ("b", "Nada mal.", None), ("a", "*ofegante*", None)],
        [("b", "Viu algo estranho por aí?", None), ("a", "hm-hm", None), ("b", "Fique atento.", None)],
        [("a", "*acena*", None), ("b", "...Adino.", None)],
        [("b", "Treino. Agora.", None), ("a", "!", None), ("a", "hyah!", "attack"),
         ("b", "Edino!", "attack"), ("a", "tá!", "attack"), ("b", "Shaw!", "attack"),
         ("b", "Hm. Bom.", None)],
    ],
    ("knight", "grub"): [
        [("b", "amigo!!", "happy"), ("a", "oi, grubinho!", None), ("b", "eba!", "happy")],
        [("a", "oi!", None), ("b", "*grub grub*", None), ("a", "*faz carinho*", None), ("b", "hihi!", "happy")],
        [("b", "brinca comigo?", None), ("a", "upa!", "jump"), ("b", "uiii!", "happy"), ("a", "hop!", "jump")],
        [("a", "tá tudo bem?", None), ("b", "agora tá!", "happy")],
    ],
    ("hornet", "grub"): [
        [("b", "oi, moça!", None), ("a", "...Pequeno.", None), ("b", "hihi", "happy")],
        [("b", "você é alta!", None), ("a", "Hmph.", None), ("b", "eba!", "happy")],
        [("b", "o que você tá fazendo?", None), ("a", "Vigiando.", None), ("b", "posso vigiar junto?", None),
         ("a", "...Pode.", None), ("b", "eba!", "happy")],
        [("b", "me ensina a lutar?", None), ("a", "Garama!", "attack"), ("b", "uiii!", "happy"),
         ("a", "Primeiro, cresça.", None)],
    ],
}

SCRIPTS.update({
    ("knight", "daughter"): [
        [("b", "olá, pequeno andarilho.", None), ("a", "oi!", None), ("b", "já comeu hoje?", None),
         ("a", "hm-hm", None), ("b", "que bom.", None)],
        [("a", "*acena*", None), ("b", "*acena de volta*", None), ("a", "upa!", "jump"), ("b", "hihi", "jump")],
        [("b", "você conhece Hallownest?", None), ("a", "...", None), ("b", "eu também não reconheço mais.", None)],
        [("a", "olha!", "cast"), ("b", "que bonito.", "cast"), ("a", "hihi", None)],
        [("b", "treina comigo?", None), ("a", "!", None), ("a", "hyah!", "attack1"), ("b", "hah!", "attack2"),
         ("a", "tá!", "attack"), ("b", "nada mal.", None)],
        [("a", "*mostra o mapa*", None), ("b", "ah, este lago eu já anotei.", None), ("a", "...", None),
         ("b", "podemos comparar depois.", None)],
        [("b", "colhi uma flor para você.", "eat"), ("a", "!!", "jump"), ("b", "de nada.", None)],
    ],
    ("hornet", "daughter"): [
        [("a", "Hm. Você de novo.", None), ("b", "olá, irmã.", None), ("a", "...Não me chame assim.", None),
         ("b", "como quiser.", None)],
        [("b", "ainda vigiando?", None), ("a", "Sempre.", None), ("b", "descanse um pouco.", None), ("a", "Hmph.", None)],
    ],
    ("daughter", "grub"): [
        [("a", "olá, pequenino.", None), ("b", "moça bonita!", "happy"), ("a", "hihi", None)],
        [("b", "você tem coroa?", None), ("a", "tinha...", None), ("b", "eu faço uma!", "happy")],
    ],
    ("knight", "hollow"): [
        [("a", "oi, irmãozão!", "jump"), ("b", "...", None), ("b", "*inclina a cabeça*", None),
         ("a", "hihi!", "jump")],
        [("a", "*olha para cima*", "look_up"), ("b", "...", None), ("a", "você é muito alto!", None),
         ("b", "*afaga a cabeça dele*", None)],
        [("b", "...", None), ("a", "vamos passear?", None), ("b", "*acena que sim*", None),
         ("a", "eba!", "jump")],
    ],
    ("daughter", "hollow"): [
        [("a", "irmão...", None), ("b", "...", None), ("a", "que bom que você está em paz aqui.", None),
         ("b", "*inclina a cabeça*", None)],
        [("a", "a neve fica bonita no seu manto.", None), ("b", "...", None), ("a", "hihi.", None)],
    ],
    ("hornet", "hollow"): [
        [("a", "Você está livre agora.", None), ("b", "...", None), ("a", "Descanse, irmão.", None),
         ("b", "*inclina a cabeça*", None)],
    ],
    ("hollow", "grub"): [
        [("b", "grandão!!", "happy"), ("a", "...", None), ("b", "oi, amigo alto!", "happy"),
         ("a", "*inclina a cabeça*", None)],
    ],
})

# Conversas no banco (a = Knight, b = Hornet), quando os dois estão sentados
BENCH_SCRIPTS = [
    [("b", "...", None), ("a", "...", None), ("b", "Bonito, daqui.", None), ("a", "hm-hm", None)],
    [("a", "*balança as pernas*", None), ("b", "Pare com isso.", None), ("a", "...", None),
     ("b", "...Tá. Pode continuar.", None)],
    [("b", "Já viajou muito, pequeno fantasma?", None), ("a", "*acena que sim*", None),
     ("b", "Hm. Eu também.", None)],
    [("a", "olha a luz do poste", None), ("b", "Lembra casa.", None), ("a", "...", None)],
    [("b", "Silêncio bom.", None), ("a", "...", None), ("b", "Hm.", None)],
    [("a", "*encosta*", None), ("b", "...", None), ("b", "Só dessa vez.", None)],
]
BENCH_NIGHT_SCRIPTS = [
    [("a", "olha as estrelas", None), ("b", "...São bonitas.", None), ("a", "hm-hm", None)],
    [("b", "A noite aqui é calma.", None), ("a", "*boceja*", None), ("b", "Durma, se quiser.", None)],
]
# Conversas no banco com a Filha (a = Knight, b = Filha)
BENCH_DAUGHTER_SCRIPTS = [
    [("b", "...", None), ("a", "...", None), ("b", "é bom não estar sozinha.", None), ("a", "hm-hm", None)],
    [("a", "*balança as pernas*", None), ("b", "hihi", None), ("b", "*balança também*", None)],
    [("b", "de onde você veio?", None), ("a", "*aponta para longe*", None), ("b", "longe... eu também.", None)],
    [("a", "*mostra o mapa*", None), ("b", "que traço bonito.", None), ("a", "!", None)],
]
BENCH_DAUGHTER_NIGHT = [
    [("a", "olha as estrelas", None), ("b", "em casa não dava para ver.", None), ("a", "...", None)],
    [("b", "sua lanterna é bonita.", None), ("a", "*mostra*", None), ("b", "obrigada por ficar.", None)],
]
BENCH_COOLDOWN = 360     # segundos entre conversas de banco

# Quando o Grub está chorando há um tempo, alguém vai consolá-lo
COMFORT = {
    "knight": [("a", "ei, não chora", None), ("b", "*snif*", None), ("a", "*abraço*", None),
               ("b", "obrigado!", "happy")],
    "hornet": [("a", "Não chore.", None), ("b", "*snif*... tá", None), ("a", "Hm.", None),
               ("b", "hihi", "happy")],
    "daughter": [("a", "shh, estou aqui.", None), ("b", "*snif*", None), ("a", "*acaricia*", None),
                 ("b", "hihi!", "happy")],
    "hollow": [("a", "...", None), ("b", "*snif*", None), ("a", "*fica ao lado em silêncio*", None),
               ("b", "obrigado, grandão!", "happy")],
}

CHECK_EVERY = (25, 45)   # segundos entre tentativas de encontro
CHANCE = 0.4             # chance de um encontro acontecer em cada tentativa
COOLDOWN = 240           # segundos mínimos até o mesmo par se encontrar de novo
COMFORT_COOLDOWN = 90    # idem para consolar o Grub


class Meeting:
    def __init__(self):
        self.arrived = set()
        self.done = False


class Society:
    def __init__(self, members: dict, world, seed=None):
        """members: {"knight": Character, "hornet": Character, "grub": Character}"""
        self.m = members
        self.world = world
        self.rng = random.Random(seed)
        self.timer = self.rng.uniform(*CHECK_EVERY)
        self.director = None      # encontro em andamento (gerador)
        self.dt = 0.0
        self.last_met = {}        # par -> tempo
        self.t = 0.0
        self.current = None       # descrição (debug)

    # ---------- por quadro ----------
    def update(self, dt):
        self.dt = dt
        self.t += dt
        if self.director is not None:
            try:
                next(self.director)
            except StopIteration:
                self.director, self.current = None, None
            return
        self.timer -= dt
        if self.timer > 0:
            return
        self.timer = self.rng.uniform(*CHECK_EVERY)
        self._maybe_start()

    def _maybe_start(self):
        free = {k: c for k, c in self.m.items() if c.brain and c.brain.available()}
        grub = self.m.get("grub")
        # prioridade: Grub chorando -> alguém consola
        if grub and grub.state == "cry" and grub.brain.manual <= 0                 and self.t - self.last_met.get("consolo", -1e9) > COMFORT_COOLDOWN:
            helpers = [k for k in COMFORT if k in free]
            if helpers:
                k = self.rng.choice(helpers)
                self.last_met["consolo"] = self.t
                self._start((k, "grub"), COMFORT[k])
                return
        if self._maybe_bench(free):
            return
        if self.rng.random() > CHANCE:
            return
        pairs = [p for p in SCRIPTS if p[0] in free and p[1] in free
                 and self.t - self.last_met.get(p, -1e9) > COOLDOWN]
        if pairs:
            pair = self.rng.choice(pairs)
            self._start(pair, self.rng.choice(SCRIPTS[pair]))

    # ---------- banco ----------
    def _maybe_bench(self, free) -> bool:
        """Knight e outra (Hornet ou Filha) no banco: um sentado chama o outro; à
        tarde/noite os dois às vezes vão juntos. Com os dois sentados, conversam."""
        partners = [p for p in ("daughter", "hornet") if p in self.m]
        k = self.m.get("knight")
        if not partners or not k or not self.world.benches:
            return False
        # quem já está sentada tem a preferência
        partners.sort(key=lambda p: not self.m[p].seated_on)
        partner = partners[0] if self.m[partners[0]].seated_on else self.rng.choice(partners)
        h = self.m[partner]
        if self.t - self.last_met.get("banco", -1e9) < BENCH_COOLDOWN:
            return False
        seated = {c for c in (k, h) if c.seated_on}
        evening = k.brain.env.phase in ("Tarde", "Entardecer", "Noite")
        if len(seated) == 1:
            other = h if k in seated else k
            key = "knight" if other is k else partner
            if key in free and self.rng.random() < 0.4:
                other.brain.force("banco", other.brain.t_bench(stay=self.rng.uniform(40, 70)))
                self._bench_scene(k, h)
                return True
        elif not seated and "knight" in free and partner in free and evening and self.rng.random() < 0.2:
            for c in (k, h):
                c.brain.force("banco", c.brain.t_bench(stay=self.rng.uniform(50, 80)))
            self._bench_scene(k, h)
            return True
        return False

    def _bench_scene(self, k, h):
        self.last_met["banco"] = self.t
        self.current = f"banco: knight + {h.name.lower()}"
        night = k.brain.env.phase == "Noite"
        if h is self.m.get("daughter"):
            pool = BENCH_DAUGHTER_SCRIPTS + (BENCH_DAUGHTER_NIGHT * 2 if night else [])
        else:
            pool = BENCH_SCRIPTS + (BENCH_NIGHT_SCRIPTS * 2 if night else [])
        script = self.rng.choice(pool)
        self.director = self._bench_direct(k, h, script)

    def _bench_direct(self, k, h, script):
        t = 0.0
        while not (k.seated_on and h.seated_on):   # espera os dois sentarem
            yield
            t += self.dt
            if t > 30 or "banco" not in (k.brain.task_name, ) or h.brain.task_name != "banco":
                return
        yield from self._wait(1.5)
        for who, text, action in script:
            c = k if who == "a" else h
            if not c.seated_on:
                break                                # alguém levantou
            if text:
                c.say(text)
            yield from self._wait(max(1.2, (c.speech[2] if c.speech else 1.0) * 0.85))

    # ---------- encontro ----------
    def _start(self, pair, script):
        a, b = self.m[pair[0]], self.m[pair[1]]
        self.last_met[pair] = self.t
        self.current = f"{pair[0]} + {pair[1]}"
        self.director = self._direct(a, b, script)

    def _spots(self, a, b):
        """Onde cada um fica: lado a lado, ~110 px de distância, virados um p/ o outro.
        Quem não anda (Grub) fica parado e o outro vem até ele."""
        foot = a.feet_rect
        if b.locomotion == "burrow":
            for side in (1, -1):
                spot = (b.x + side * 95 * CHARACTER_SCALE, b.y)
                if self.world.walkable(foot(*spot)):
                    return spot, (b.x, b.y)
            return self.world.nearest_walkable(b.x + 95, b.y, foot), (b.x, b.y)
        mx, my = (a.x + b.x) / 2, (a.y + b.y) / 2
        for dx in (55 * CHARACTER_SCALE, 70 * CHARACTER_SCALE, 40 * CHARACTER_SCALE):
            sa, sb = (mx - dx, my), (mx + dx, my)
            if self.world.walkable(foot(*sa)) and self.world.walkable(foot(*sb)):
                return (sa, sb) if a.x <= b.x else (sb, sa)
        sa = self.world.nearest_walkable(mx - 55 * CHARACTER_SCALE, my, foot)
        return sa, self.world.nearest_walkable(sa[0] + 110 * CHARACTER_SCALE, sa[1], foot)

    def _direct(self, a, b, script):
        meet = Meeting()
        spot_a, spot_b = self._spots(a, b)
        a.brain.force("encontro", self._attend(a, b, spot_a, meet))
        b.brain.force("encontro", self._attend(b, a, spot_b, meet))
        t = 0.0
        while len(meet.arrived) < 2:             # espera os dois chegarem
            yield
            t += self.dt
            if t > 25 or a.brain.task_name != "encontro" or b.brain.task_name != "encontro":
                meet.done = True                  # desistiu (jogador assumiu, travou...)
                return
        yield from self._wait(0.4)
        for who, text, action in script:
            c = a if who == "a" else b
            if c.brain.task_name != "encontro":   # jogador assumiu no meio
                break
            if action:
                c.do_action(action)
            if text:
                c.say(text)
            yield from self._wait(max(1.0, (c.speech[2] if c.speech else 1.0) * 0.8))
            while c.state not in ("idle", "cry") and c.state in c.sheets and not c.sheets[c.state].loop:
                yield                              # espera a ação terminar
        yield from self._wait(1.0)
        meet.done = True

    def _wait(self, secs):
        t = 0.0
        while t < secs:
            yield
            t += self.dt

    def _attend(self, me, other, spot, meet):
        """Tarefa de cada participante: ir ao ponto, encarar o outro, esperar o roteiro."""
        brain = me.brain
        if math.hypot(spot[0] - me.x, spot[1] - me.y) > 8:
            yield from brain.walk_to(spot)
        meet.arrived.add(me)
        while not meet.done:
            if me.state in ("idle", "cry"):
                brain.face("right" if other.x > me.x else "left")
            yield
        if me.state == "cry":
            me.state = "idle"
        brain.boredom = max(0.0, brain.boredom - 0.5)
        if hasattr(brain, "lonely"):
            brain.lonely = 0.0
        yield from brain.wait(1.0)
