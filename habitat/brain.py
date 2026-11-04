"""A rotina do personagem: necessidades + tarefas + falas.

NECESSIDADES (0 = ok, 1 = urgente; energia é o contrário: 1 = cheio)
  energia  cai com o tempo (bem mais rápido à noite) -> dorme
  sede     sobe com o tempo (mais rápido no calor)    -> vai à beira do lago beber
  fome     sobe com o tempo                            -> vai até uma flor/arbusto comer
  tédio    sobe parado, desce fazendo coisas           -> passeia, treina, pula, fala

TAREFAS são geradores Python: cada `yield` = espera um quadro. Assim uma tarefa
se escreve como uma receita ("anda até lá, vira, abaixa, espera 2 s...").

FALAS: balões curtos ligados ao contexto (hora, chuva, calor, necessidades).
Edite as listas em LINES à vontade.

O jogador pode assumir o controle (teclado) a qualquer momento: a rotina pausa
e volta sozinha alguns segundos depois.
"""
import math
import random

# --------------------------------------------------------------------------
# Falas (escolhidas ao acaso dentro de cada grupo). {temp} e {city} são
# trocados pelo clima real.
LINES = {
    "greet":      ["oi!", "olá!", "oi oi", "ah, é você!", "hm?", "e aí?", "oi :)"],
    "bored":      ["tédio...", "hmm...", "...", "que tédio", "*assobia*", "lá lá lá", "nada pra fazer",
                   "cadê todo mundo?", "hmm, e agora?"],
    "wander":     ["vou dar uma volta", "explorar!", "pra lá!", "hmm, por ali", "passeando~"],
    "idle":       ["...", "hm.", "*olha em volta*", "que lugar bonito", "silêncio bom"],
    "sleepy":     ["sono...", "*boceja*", "tô cansado", "hora de dormir", "olhos pesados..."],
    "sleeping":   ["zZz", "zzz...", "Zz", "zZ...", "*ronca*"],
    "wake_day":   ["bom dia!", "que noite boa", "*espreguiça*", "dormi bem!"],
    "wake_nap":   ["que soneca boa", "hm... dormi?", "*espreguiça*", "descansado!"],
    "wake_night": ["hm... ainda é noite", "*boceja*", "sede..."],
    "thirsty":    ["sede...", "água!", "vou no lago", "garganta seca"],
    "drink":      ["ahh, água fresca", "glub glub", "que delícia", "refrescante!"],
    "hungry":     ["fome...", "barriga roncando", "hmm, florzinha...", "que fome"],
    "eat":        ["nhac!", "nham nham", "docinho", "hmm, gostoso"],
    "train":      ["hora de treinar!", "hyah!", "tá!", "mais um!", "foco!"],
    "jump":       ["ê!", "upa!", "hop!", "yay!"],
    "look_up":    ["hmm?", "o que é aquilo?", "nuvens...", "que céu"],
    "stars":      ["olha as estrelas", "que noite bonita", "lua..."],
    "pond":       ["olha o lago", "peixinhos?", "que água clara"],
    "rain_start": ["chuva!", "tá chovendo...", "eita, molhou", "lá vem água"],
    "rain":       ["que chuvarada", "plic plic", "brr", "molhadinho", "chuva boa"],
    "thunder":    ["relâmpago!", "eek!", "que susto!", "trovão!"],
    "hot":        ["que calor!", "{temp}°C... ufa", "{city} tá quente", "derretendo..."],
    "night":      ["tá escuro...", "noite calma", "grilos..."],
    "evening":    ["fim de tarde...", "que pôr do sol", "o dia tá acabando"],
    "morning":    ["dia lindo!", "que sol bom", "bom dia, mundo"],
    "bench":      ["que banco bom", "descansar um pouco...", "ahh", "daqui dá pra ver tudo", "*balança as pernas*"],
    "bench_night": ["que noite bonita", "o poste é quentinho", "estrelas..."],
    "shade_see":  ["...!", "hm?!", "quem tá aí?", "uma sombra..."],
    "shade_ask":  ["quem é você?", "oi...?", "...", "você é como eu?"],
    "shade_gone": ["sumiu...", "hm...", "estranho..."],
    "listen":     ["que música bonita", "*escuta*", "ela tá tocando!", "shhh..."],
    "listen_end": ["*bate palminhas*", "bis!", "gostei muito", "que lindo..."],
    "wind":       ["que vento bom", "*sente o vento*", "ahh...", "o vento tá forte"],
    "map":        ["deixa eu ver o mapa", "hmm, onde eu tô?", "*anota no mapa*", "marcando aqui..."],
    "map_walk":   ["vamos ver o mapa...", "por aqui, acho", "hmm, mapa..."],
    "special":    ["agora!", "HYAH!", "golpe especial!"],
    "swim":       ["vou nadar!", "água!", "tibum!", "que calor, vou pro lago"],
    "swimming":   ["que água boa", "*nada*", "glub", "fresquinho"],
    "swim_out":   ["chega de nadar", "*sacode*", "molhadinho"],
    "travel":     ["vou pra outra ilha", "explorar lá!", "o que tem do outro lado?", "partiu"],
    "arrive":     ["cheguei!", "hmm, aqui...", "olha só", "que lugar"],
    "cave_sleep": ["hora de ir pra caverna", "minha caverna...", "dormir no quentinho"],
    "shelter":    ["chuva! pra caverna!", "vou me abrigar", "aqui não molha"],
    "sheltered":  ["sequinho aqui", "*ouve a chuva*", "plic plic lá fora"],
    "rain_over":  ["parou de chover!", "vamos lá fora", "o céu abriu"],
}

# Animações de quem está sentado no banco
SEATED = ("sit_down", "bench_sit", "map_look", "map_write", "bench_leave")

# Taxas por segundo (tempo real)
ENERGY_DRAIN_DAY = 1 / 1500     # ~25 min acordado de dia até cansar
ENERGY_DRAIN_NIGHT = 1 / 240    # à noite cansa bem mais rápido
ENERGY_GAIN_SLEEP = 1 / 120
HUNGER_RATE = 1 / 700          # come mais ou menos a cada 10 min
THIRST_RATE = 1 / 560          # bebe mais ou menos a cada 8 min (mais no calor)
BORED_RATE = 1 / 90

SLEEP_THRESHOLD = 0.15          # energia abaixo disso = vai dormir
NIGHT_SLEEP_THRESHOLD = 0.55    # à noite dorme mais cedo
NEED_THRESHOLD = 0.75           # fome/sede acima disso = vai resolver
MANUAL_PAUSE = 8.0              # segundos sem tecla até a rotina voltar
RUN_DIST = 380                  # caminho mais longo que isso = corre (se tiver "run")


class Brain:
    """Rotina base (é a do Knight). Hornet e Grub herdam e mudam o que precisam."""
    LINES = LINES
    HAS_HUNGER = True
    HAS_THIRST = True
    # como beber: [(animação, segurar_segundos ou None = até acabar)]
    DRINK_ANIMS = [("look_down", 1.2), ("eat", None), ("eat", None)]
    # tarefas em que dá para ser chamado para interagir com outro personagem
    SOCIAL_OK = ("passear", "parado", "olhar o céu", "ver o lago", "pular", "treinar")

    def __init__(self, character, world, env, seed=None):
        character.brain = self
        self.c = character
        self.world = world
        self.env = env
        self.rng = random.Random(seed)
        self.energy = self.rng.uniform(0.6, 1.0)
        self.hunger = self.rng.uniform(0.0, 0.4)
        self.thirst = self.rng.uniform(0.0, 0.4)
        self.boredom = 0.3
        self.task = None
        self.task_name = "-"
        self.axis = (0.0, 0.0)
        self.dt = 0.0
        self.manual = 0.0          # >0 = jogador no controle
        self.chat_timer = self.rng.uniform(8, 16)
        self.was_raining = False
        self.last_flash = 0.0
        self.recent = []           # últimas falas (evita repetir)
        self.others = ()           # outros personagens (o Game preenche)
        self.worlds = {world.name: world} if hasattr(world, "name") else {}   # todas as áreas (Game)

    # ---------- falas ----------
    def say(self, group: str, chance: float = 1.0):
        if self.rng.random() > chance:
            return
        if group not in self.LINES:
            return
        options = [l for l in self.LINES[group] if l not in self.recent] or self.LINES[group]
        text = self.rng.choice(options)
        d = self.env.data or {}
        text = text.replace("{temp}", f"{d.get('temp', 30):.0f}").replace("{city}", d.get("city", "aqui"))
        self.recent = (self.recent + [text])[-6:]
        self.c.say(text)

    def context_chat(self):
        """Comentário espontâneo sobre o momento."""
        env, d = self.env, self.env.data or {}
        groups = ["idle", "bored" if self.boredom > 0.5 else "idle"]
        if env.rain > 0.3:
            groups += ["rain"] * 3
        if d.get("temp") is not None and d["temp"] >= 30 and env.phase in ("Dia", "Tarde"):
            groups += ["hot"] * 2
        if env.phase == "Noite":
            groups += ["night", "stars"]
        elif env.phase in ("Entardecer", "Tarde"):
            groups.append("evening")
        elif env.phase in ("Amanhecer", "Dia"):
            groups.append("morning")
        if self.HAS_THIRST and self.thirst > 0.55:
            groups.append("thirsty")
        if self.HAS_HUNGER and self.hunger > 0.55:
            groups.append("hungry")
        if self.energy < 0.3:
            groups.append("sleepy")
        self.say(self.rng.choice(groups))

    # ---------- controle externo ----------
    def take_manual(self):
        """Jogador apertou algo: pausa a rotina por um tempo."""
        if self.manual <= 0 and self.task is not None:
            self._drop_task()
            self.task_name = "manual"
        self.manual = MANUAL_PAUSE
        self.axis = (0.0, 0.0)

    def _drop_task(self):
        if self.task is not None:
            self.task.close()   # roda os "finally" da tarefa (ex.: levantar do banco)
        self.task = None

    def force(self, name, gen):
        """Troca a tarefa atual (usado pelas interações entre personagens)."""
        self._drop_task()
        if self.c.state in ("look_up", "look_down"):
            self.c.state = "idle"
        self.task, self.task_name = gen, name

    def available(self) -> bool:
        """Livre para uma interação? (acordado, sem urgência, fazendo algo à toa)"""
        return (self.manual <= 0 and self.task_name in self.SOCIAL_OK
                and self.c.state not in ("sleep", "lie_down", "wake")
                and self.energy > 0.25 and self.thirst < 0.7 and self.hunger < 0.7)

    def poke(self):
        """Clicaram no personagem."""
        if self.c.state in ("sleep", "lie_down"):
            self.c.say(self.rng.choice(["zZz...", "hm... 5 minutinhos", "*ronca*"]))
            return
        self.say("greet")
        if self.manual <= 0 and self.rng.random() < 0.4:
            self.task, self.task_name = self.t_jump(silent=True), "pulo"

    # ---------- por quadro ----------
    def update(self, dt: float) -> tuple[float, float]:
        """Atualiza necessidades e a tarefa atual. Retorna o vetor de movimento."""
        self.dt = dt
        self._needs(dt)
        self._events()
        # à noite anda/fica com a lanterna; cansado = idle de pouca vida
        self.c.lantern = getattr(self.env, "darkness", 0) > 0.45
        self.c.tired = self.energy < 0.3
        if self.manual > 0:
            self.manual -= dt
            return (0.0, 0.0)
        self.axis = (0.0, 0.0)
        if self.task is None:
            self.task_name, self.task = self.choose()
        try:
            next(self.task)
        except StopIteration:
            self.task = None
        # conversa espontânea quando não está dormindo
        if self.c.state not in ("sleep", "lie_down") and not self.c.speech:
            self.chat_timer -= dt
            if self.chat_timer <= 0:
                self.chat_timer = self.rng.uniform(25, 55)
                self.context_chat()
        return self.axis

    def _needs(self, dt):
        asleep = self.c.state in ("sleep", "lie_down")
        night = self.env.phase == "Noite"
        hot = (self.env.data or {}).get("temp", 28) >= 30
        if asleep:
            self.energy = min(1.0, self.energy + ENERGY_GAIN_SLEEP * dt)
        else:
            self.energy = max(0.0, self.energy - (ENERGY_DRAIN_NIGHT if night else ENERGY_DRAIN_DAY) * dt)
        k = 0.3 if asleep else 1.0
        if self.HAS_HUNGER:
            self.hunger = min(1.0, self.hunger + HUNGER_RATE * dt * k)
        if self.HAS_THIRST:
            self.thirst = min(1.0, self.thirst + THIRST_RATE * dt * k * (1.4 if hot else 1.0))
        if self.c.state == "idle" and not asleep:
            self.boredom = min(1.0, self.boredom + BORED_RATE * dt)

    def _events(self):
        """Reage ao clima: começou a chover, relâmpago."""
        raining = self.env.rain > 0.3
        awake = self.c.state not in ("sleep", "lie_down")
        if raining and not self.was_raining and awake:
            self.say("rain_start")
        self.was_raining = raining
        if self.env.flash > self.last_flash + 0.2 and awake:
            self.say("thunder", 0.6)
        self.last_flash = self.env.flash

    # ---------- decisão ----------
    def choose(self):
        night = self.env.phase == "Noite"
        if self.energy < SLEEP_THRESHOLD or (night and self.energy < NIGHT_SLEEP_THRESHOLD):
            return "dormir", self.t_sleep(night)
        if self.env.rain > 0.3 and self.find_cave() and self.rng.random() < 0.7:
            return "abrigo", self.t_shelter()
        if self.thirst > NEED_THRESHOLD and self.world.shore:
            return "beber", self.t_drink()
        if self.hunger > NEED_THRESHOLD and self._food():
            return "comer", self.t_eat()
        options = [
            ("passear", self.t_wander, 40 + 30 * self.boredom),
            ("parado", self.t_idle, 25),
            ("treinar", self.t_train, 6 + 10 * self.boredom),
            ("pular", self.t_jump, 4 + 6 * self.boredom),
            ("olhar o céu", self.t_look_up, 6 + (8 if night else 0)),
            ("ver o lago", self.t_visit_pond, 3 if self.world.shore else 0),
            ("banco", self.t_bench, self.bench_weight()),
            ("sentir o vento", self.t_wind, self.wind_weight()),
            ("nadar", self.t_swim, self.swim_weight()),
            ("outra ilha", self.t_go_other, 2 if len(self.worlds) > 1 else 0),
        ]
        if self.thirst > 0.45 and self.world.shore:
            options.append(("beber", self.t_drink, 20))
        if self.hunger > 0.45 and self._food():
            options.append(("comer", self.t_eat, 20))
        names, fns, weights = zip(*options)
        i = self.rng.choices(range(len(fns)), weights=weights)[0]
        return names[i], fns[i]()

    def _food(self):
        return ([d for d in self.world.decor if d.kind.startswith(("flor", "arbusto_"))]
                + list(getattr(self.world, "food_spots", [])))

    # ---------- blocos de tarefa ----------
    def wait(self, secs):
        t = 0.0
        while t < secs:
            yield
            t += self.dt

    def walk_to(self, target, tolerance=None, run=True):
        """Anda (ou salta) até `target` seguindo um caminho. Desiste se ficar preso."""
        if self.c.locomotion == "burrow":
            yield from self.burrow_to(target)
            return
        if tolerance is None:
            tolerance = 22.0 if self.c.locomotion == "leap" else 6.0
        path = self.world.find_path((self.c.x, self.c.y), target)
        # caminho longo: corre (se tiver a animação "run")
        dist, px, py = 0.0, self.c.x, self.c.y
        for wx, wy in path:
            dist, px, py = dist + math.hypot(wx - px, wy - py), wx, wy
        self.c.running = run and dist > RUN_DIST
        try:
            yield from self._follow(path, tolerance)
        finally:
            self.c.running = False
            self.axis = (0.0, 0.0)
        while self.c.state in ("takeoff", "leap", "land"):  # termina o salto
            yield

    def _follow(self, path, tolerance):
        for wx, wy in path:
            stuck, last = 0.0, (self.c.x, self.c.y)
            while math.hypot(wx - self.c.x, wy - self.c.y) > tolerance:
                dx, dy = wx - self.c.x, wy - self.c.y
                d = math.hypot(dx, dy)
                # último passo mais curto: chega no ponto em vez de passar dele
                spd = self.c.run_speed if self.c.running and "run" in self.c.sheets else self.c.speed
                k = min(1.0, d / max(1e-6, spd * self.dt)) / d
                self.axis = (dx * k, dy * k)
                yield
                moved = math.hypot(self.c.x - last[0], self.c.y - last[1])
                last = (self.c.x, self.c.y)
                # (no salto ele fica parado enquanto agacha/aterrissa: só conta no ar)
                if self.c.state in ("walk", "run", "leap"):
                    stuck = stuck + self.dt if moved < self.c.speed * self.dt * 0.25 else 0.0
                if stuck > 0.8:
                    return

    def burrow_to(self, target):
        """Viaja por baixo da terra: enterra, some, brota no destino."""
        self.c.do_action("lie_down")
        yield
        while self.c.state == "lie_down":
            yield
        yield from self.wait(self.rng.uniform(0.8, 1.6))
        self.c.x, self.c.y = target
        self.c.do_action("wake")
        yield
        while self.c.state == "wake":
            yield

    def face(self, side):
        self.c.facing = side
        self.c.dir = side

    def play(self, anim, hold=None):
        """Toca uma animação até acabar (ou segura `hold` segundos)."""
        self.c.do_action(anim)
        if hold is not None:
            yield from self.wait(hold)
            if self.c.state == anim:
                self.c.state = "idle"
            return
        yield
        while self.c.state == anim:
            yield

    def free_point(self, radius):
        """Ponto andável por perto que não esteja em cima de outro personagem."""
        for _ in range(12):
            p = self.world.random_point(self.rng, near=(self.c.x, self.c.y), radius=radius)
            if all(math.hypot(o.x - p[0], o.y - p[1]) > 90 for o in getattr(self, "others", ())):
                return p
        return p

    # ---------- banco ----------
    def sit_on(self, bench, i):
        bench.occupied[i] = self.c
        self.c.x, self.c.y = bench.seat_pos(i)
        self.c.seated_on = (bench, i)
        self.c.seat_lift = bench.seat_height - self.c.seat_drop
        if "sit_down" in self.c.sheets:
            self.c.do_action("sit_down")     # senta (-> bench_sit)
        else:
            self.c.state = "bench_sit"

    def leave_bench(self):
        if not self.c.seated_on:
            return
        bench, i = self.c.seated_on
        if bench.occupied.get(i) is self.c:
            del bench.occupied[i]
        self.c.seated_on = None
        self.c.seat_lift = 0.0
        self.c.x, self.c.y = bench.approach(i)
        if self.c.state in SEATED:
            self.c.state = "idle"

    def bench_weight(self):
        if not self.world.benches or "bench_sit" not in self.c.sheets:
            return 0
        if all(b.free_seat(self.c) is None for b in self.world.benches):
            return 0
        evening = self.env.phase in ("Tarde", "Entardecer", "Noite")
        return 3 + (7 if evening else 0)

    def t_bench(self, stay=None):
        """Vai até o banco, senta um tempo, levanta."""
        bench = next((b for b in self.world.benches if b.free_seat(self.c) is not None), None)
        if bench is None:
            return
        i = bench.free_seat(self.c)
        bench.occupied[i] = self.c          # reserva o assento
        try:
            yield from self.walk_to(bench.approach(i))
            ax, ay = bench.approach(i)
            if math.hypot(ax - self.c.x, ay - self.c.y) > 30:
                return
            self.sit_on(bench, i)
            night = self.env.phase == "Noite"
            self.say("bench_night" if night else "bench", 0.6)
            stay = stay or self.rng.uniform(25, 45) * (1.3 if night else 1.0)
            # às vezes pega o mapa: olha, anota, olha de novo
            map_at = self.rng.uniform(5, 12) if "map_look" in self.c.sheets and self.rng.random() < 0.5 else None
            t = 0.0
            while t < stay and self.c.seated_on:
                if map_at is not None and t >= map_at and self.c.state == "bench_sit":
                    map_at = None
                    self.say("map", 0.7)
                    yield from self.play("map_look", hold=self.rng.uniform(3, 5))
                    if "map_write" in self.c.sheets:
                        yield from self.play("map_write", hold=self.rng.uniform(4, 7))
                    yield from self.play("map_look", hold=self.rng.uniform(2, 3))
                    self.c.state = "bench_sit"
                    t += 12
                yield
                t += self.dt
            self.boredom = max(0.0, self.boredom - 0.3)
            if self.c.seated_on and "bench_leave" in self.c.sheets:
                yield from self.play("bench_leave")     # desce do banco
        finally:
            if bench.occupied.get(i) is self.c and not self.c.seated_on:
                del bench.occupied[i]       # desistiu antes de sentar
            self.leave_bench()

    # ---------- a Sombra ----------
    def react_shade(self, shade):
        """A Sombra apareceu: reação do personagem (pode ignorar se ocupado)."""
        if self.c.state in ("sleep", "lie_down") or self.manual > 0:
            return
        self.say("shade_see")
        if self.available() and self.rng.random() < 0.5:
            self.force("ver a sombra", self.t_approach_shade(shade))

    def t_approach_shade(self, shade):
        yield from self.wait(1.0)
        side = 1 if self.c.x < shade.x else -1
        target = self.world.nearest_walkable(shade.x - side * 185, shade.y, self.c.feet_rect)
        yield from self.walk_to(target)
        self.face("right" if shade.x > self.c.x else "left")
        if shade.visible:
            self.say("shade_ask")
        yield from self.wait(3)
        if not shade.visible:
            self.say("shade_gone", 0.8)
        yield from self.wait(2)

    def listen_to(self, musician):
        """Alguém começou a tocar: às vezes vem ouvir (se estiver livre)."""
        if self.available() and self.rng.random() < 0.55:
            self.force("ouvir", self.t_listen(musician))

    def t_listen(self, musician):
        """Chega perto de quem está tocando, escuta e aplaude no fim."""
        yield from self.wait(self.rng.uniform(0.5, 2.0))
        side = 1 if self.c.x > musician.x else -1
        spot = self.world.nearest_walkable(musician.x + side * self.rng.uniform(120, 170),
                                           musician.y + self.rng.uniform(-25, 25), self.c.feet_rect)
        if math.hypot(spot[0] - self.c.x, spot[1] - self.c.y) > 60:
            yield from self.walk_to(spot)
        self.face("left" if musician.x < self.c.x else "right")
        self.say("listen", 0.7)
        t, next_line = 0.0, self.rng.uniform(8, 14)
        while musician.state == "needolin" and t < 60:
            next_line -= self.dt
            if next_line <= 0:
                next_line = self.rng.uniform(10, 18)
                if "happy" in self.c.sheets and self.rng.random() < 0.5:
                    yield from self.play("happy")     # o Grub se alegra
                else:
                    self.say("listen", 0.4)
            yield
            t += self.dt
        self.say("listen_end", 0.8)
        self.boredom = max(0.0, self.boredom - 0.3)
        if "happy" in self.c.sheets:
            yield from self.play("happy")
        yield from self.wait(2)

    # ---------- tarefas ----------
    def t_wander(self):
        target = self.free_point(420)
        if "walk_map" in self.c.sheets and self.rng.random() < 0.2:
            self.say("map_walk", 0.6)             # anda lendo o mapa (devagar, sem correr)
            self.c.walk_variant = "walk_map"
            try:
                yield from self.walk_to(target, run=False)
            finally:
                self.c.walk_variant = None
        else:
            self.say("wander", 0.25)
            yield from self.walk_to(target)
        self.boredom = max(0.0, self.boredom - 0.15)
        yield from self.wait(self.rng.uniform(0.8, 3.0))

    def t_idle(self):
        yield from self.wait(self.rng.uniform(2, 5))
        if self.rng.random() < 0.5:  # olha para o outro lado
            self.face("left" if self.c.facing == "right" else "right")
            yield from self.wait(self.rng.uniform(1.5, 4))

    def t_look_up(self):
        night = self.env.phase == "Noite"
        self.say("stars" if night else "look_up", 0.7)
        yield from self.play("look_up", hold=self.rng.uniform(2.5, 5))
        self.boredom = max(0.0, self.boredom - 0.1)
        yield from self.wait(1)

    def t_train(self):
        self.say("train", 0.8)
        yield from self.wait(0.6)
        moves = [(a, w) for a, w in (("attack", 4), ("attack1", 2), ("attack2", 2)) if a in self.c.sheets]
        for _ in range(self.rng.randint(2, 5)):
            if self.rng.random() < 0.4:
                self.face("left" if self.c.facing == "right" else "right")
            anim = self.rng.choices([a for a, _ in moves], weights=[w for _, w in moves])[0]
            yield from self.play(anim)
            yield from self.wait(self.rng.uniform(0.15, 0.6))
        if "special" in self.c.sheets and self.rng.random() < 0.3:   # golpe especial no fim
            yield from self.wait(0.4)
            self.say("special")
            yield from self.play("special")
        self.boredom = max(0.0, self.boredom - 0.4)
        self.energy = max(0.0, self.energy - 0.015)
        yield from self.wait(1.5)

    def t_jump(self, silent=False):
        if not silent:
            self.say("jump", 0.6)
        for _ in range(self.rng.randint(1, 3)):
            double = "double_jump" in self.c.sheets and self.rng.random() < 0.35
            yield from self.play("double_jump" if double else "jump")
            yield from self.wait(0.15)
        self.boredom = max(0.0, self.boredom - 0.25)
        yield from self.wait(1)

    # ---------- áreas (ilhas) ----------
    def enter_area(self, name):
        """Passa para a área `name` (pela saída de lá para cá, se houver)."""
        if name not in self.worlds:
            return
        old = self.world
        self.leave_bench()
        self._leave_cave_now()
        self.c.swimming = False
        new = self.worlds[name]
        ex = old.exit_to(name)
        x, y = new.to_screen(ex["arrive"]) if ex else new.spawn
        self.c.x, self.c.y = new.nav_point((x, y))
        self.c.area = name
        self.c.world = new
        self.world = new

    def go_area(self, name):
        """Anda até a saída para `name` e passa para lá. Retorna True se chegou."""
        if self.c.area == name:
            return True
        ex = self.world.exit_to(name)
        if ex is None:
            return False
        yield from self.walk_to(ex["at"])
        if math.hypot(ex["at"][0] - self.c.x, ex["at"][1] - self.c.y) > 30:
            return False
        self.enter_area(name)
        yield from self.wait(0.6)
        return True

    def t_go_other(self):
        others = [n for n in self.worlds if n != self.c.area]
        if not others:
            return
        self.say("travel", 0.7)
        arrived = yield from self.go_area(self.rng.choice(others))
        if arrived:
            self.say("arrive", 0.6)
            self.boredom = max(0.0, self.boredom - 0.4)
            yield from self.wait(1.5)

    def find_cave(self):
        """(área, caverna) do abrigo mais à mão (a da área atual primeiro)."""
        names = [self.c.area] + [n for n in self.worlds if n != self.c.area]
        for n in names:
            w = self.worlds.get(n)
            if w is not None and w.caves:
                return n, w.caves[0]
        return None

    def _cave_door(self, cave):
        if cave.door is None:
            cave.door = self.world.nearest_walkable(*cave.door_hint, self.c.feet_rect)
        return cave.door

    def _glide(self, target, face_dir):
        """Anda até `target` ignorando o chão (entrar/sair da caverna)."""
        sx, sy = self.c.x, self.c.y
        d = math.hypot(target[0] - sx, target[1] - sy)
        dur = max(0.3, d / (self.c.speed * 0.6))
        self.c.state, self.c.pinned, self.c.dir = "walk", True, face_dir
        t = 0.0
        try:
            while t < dur:
                k = t / dur
                self.c.x, self.c.y = sx + (target[0] - sx) * k, sy + (target[1] - sy) * k
                self.c.dir = face_dir
                yield
                t += self.dt
        finally:
            self.c.x, self.c.y = target
            self.c.pinned = False
            if self.c.state == "walk":
                self.c.state = "idle"

    def go_into_cave(self, found):
        """Vai até a caverna (viajando se preciso) e entra. Retorna True se entrou."""
        area, cave = found
        if self.c.area != area:
            ok = yield from self.go_area(area)
            if not ok:
                return False
        door = self._cave_door(cave)
        yield from self.walk_to(door)
        if math.hypot(door[0] - self.c.x, door[1] - self.c.y) > 30:
            return False
        self.c.in_cave = True
        cave.occupant = self.c
        yield from self._glide(cave.inside, "up")       # entra de costas (into_door)
        return True

    def leave_cave(self):
        found = self.find_cave()
        if not self.c.in_cave or not found:
            return
        cave = found[1]
        yield from self._glide(self._cave_door(cave), "down")   # sai de frente (tram_leave)
        self._leave_cave_now()

    def _leave_cave_now(self):
        if not self.c.in_cave:
            return
        found = self.find_cave()
        if found:
            cave = found[1]
            if cave.occupant is self.c:
                cave.occupant = None
            if math.hypot(self.c.x - cave.inside[0], self.c.y - cave.inside[1]) < 10:
                self.c.x, self.c.y = self._cave_door(cave)
        self.c.in_cave = False

    def t_shelter(self):
        """Chuva: corre para a caverna e espera passar lá dentro."""
        self.say("shelter", 0.8)
        found = self.find_cave()
        if not found:
            return
        try:
            inside = yield from self.go_into_cave(found)
            if not inside:
                return
            t, next_line = 0.0, self.rng.uniform(15, 30)
            while self.env.rain > 0.3 and t < 240:
                next_line -= self.dt
                if next_line <= 0:
                    next_line = self.rng.uniform(20, 40)
                    self.say("sheltered", 0.5)
                yield
                t += self.dt
            if self.env.rain <= 0.3:
                self.say("rain_over", 0.7)
            yield from self.leave_cave()
        finally:
            if self.c.in_cave and self.c.state not in ("sleep", "lie_down"):
                self._leave_cave_now()

    def wind_weight(self):
        if "cast" not in self.c.sheets:
            return 0
        return 3 + (6 if self.env.rain > 0.3 else 0)

    def t_wind(self):
        """Para, abre a capa e sente o vento (cast)."""
        self.say("wind", 0.7)
        yield from self.play("cast")
        self.boredom = max(0.0, self.boredom - 0.15)
        yield from self.wait(self.rng.uniform(1, 2.5))

    def swim_weight(self):
        if "swim" not in self.c.sheets or not getattr(self.world, "water_cells", None) or not self._swim_spots():
            return 0
        if self.env.phase == "Noite" or self.env.rain > 0.3:
            return 0
        hot = (self.env.data or {}).get("temp", 28) >= 30
        return 2 + (4 if hot else 0)

    def _hop(self, frm, to, anim="jump"):
        """Pula de `frm` até `to` (move junto com o arco do pulo)."""
        self.c.do_action(anim)
        dur = self.c.sheets[anim].duration if anim in self.c.sheets else 0.4
        t = 0.0
        while t < dur:
            k = min(1.0, t / dur)
            self.c.x = frm[0] + (to[0] - frm[0]) * k
            self.c.y = frm[1] + (to[1] - frm[1]) * k
            yield
            t += self.dt
        self.c.x, self.c.y = to

    def _swim_to(self, target):
        """Nada em linha reta até `target` (desiste se travar)."""
        stuck = 0.0
        while math.hypot(target[0] - self.c.x, target[1] - self.c.y) > 8:
            dx, dy = target[0] - self.c.x, target[1] - self.c.y
            d = math.hypot(dx, dy)
            k = min(1.0, d / max(1e-6, self.c.speed * 0.5 * self.dt)) / d
            self.axis = (dx * k, dy * k)
            last = (self.c.x, self.c.y)
            yield
            moved = math.hypot(self.c.x - last[0], self.c.y - last[1])
            stuck = stuck + self.dt if moved < self.c.speed * 0.5 * self.dt * 0.25 else 0.0
            if stuck > 0.8:
                break
        self.axis = (0.0, 0.0)

    def _swim_spots(self):
        """Pontos da margem com água funda ao lado: [(x, y, lado, entrada_na_água)]."""
        cache = self.__dict__.setdefault("_spots_cache", {})
        if self.world.name not in cache:
            out = []
            for x, y, side in self.world.shore:
                sx = 1 if side == "right" else -1
                entry = next(((x + sx * d, y) for d in range(40, 200, 8)
                              if self.world.swimmable(self.c.feet_rect(x + sx * d, y))), None)
                if entry:
                    out.append((x, y, side, entry))
            cache[self.world.name] = out
        return list(cache[self.world.name])

    def t_swim(self):
        """Vai à beira do lago, pula na água, nada um pouco e volta."""
        spots = self._swim_spots()
        if not spots:
            return
        self.say("swim", 0.8)
        spots.sort(key=lambda s: (s[0] - self.c.x) ** 2 + (s[1] - self.c.y) ** 2)
        x, y, side, entry = self.rng.choice(spots[:4])
        yield from self.walk_to((x, y))
        if math.hypot(x - self.c.x, y - self.c.y) > 20:
            return
        self.face(side)
        shore = (self.c.x, self.c.y)
        try:
            yield from self._hop(shore, entry)          # tibum
            self.c.swimming = True
            yield from self.play("swim_enter")
            for _ in range(self.rng.randint(2, 4)):
                p = self.world.water_point(self.rng, near=(self.c.x, self.c.y), radius=220)
                if p and self.world.clear_water((self.c.x, self.c.y), p):
                    yield from self._swim_to(p)
                self.say("swimming", 0.3)
                yield from self.wait(self.rng.uniform(1.5, 4))
            if self.world.clear_water((self.c.x, self.c.y), entry):
                yield from self._swim_to(entry)
            else:
                self.c.x, self.c.y = entry
            self.face("left" if shore[0] < self.c.x else "right")
            self.c.swimming = False
            yield from self._hop((self.c.x, self.c.y), shore)   # sai da água
            self.thirst = max(0.0, self.thirst - 0.3)
            self.boredom = max(0.0, self.boredom - 0.5)
            self.say("swim_out", 0.7)
            yield from self.wait(1.5)
        finally:
            if self.c.swimming:                          # interrompido: volta para a margem
                self.c.swimming = False
                self.c.x, self.c.y = shore
                if self.c.state not in ("sleep", "lie_down"):
                    self.c.state = "idle"

    def _go_shore(self):
        """Vai até um ponto na beira do lago e vira para a água. Retorna True se chegou."""
        spots = sorted(self.world.shore, key=lambda s: (s[0] - self.c.x) ** 2 + (s[1] - self.c.y) ** 2)
        x, y, side = self.rng.choice(spots[:12])
        yield from self.walk_to((x, y))
        if math.hypot(x - self.c.x, y - self.c.y) > 20:
            return False
        self.face(side)
        return True

    def t_drink(self):
        self.say("thirsty", 0.8)
        arrived = yield from self._go_shore()
        if not arrived:
            return
        for anim, hold in self.DRINK_ANIMS:  # abaixa e bebe
            yield from self.play(anim, hold=hold)
        self.thirst = 0.0
        self.say("drink")
        yield from self.wait(2)

    def t_visit_pond(self):
        arrived = yield from self._go_shore()
        if not arrived:
            return
        self.say("pond", 0.8)
        yield from self.play("look_down", hold=self.rng.uniform(3, 6))
        self.boredom = max(0.0, self.boredom - 0.2)

    def t_eat(self):
        self.say("hungry", 0.8)
        foods = sorted(self._food(), key=lambda d: (d.x - self.c.x) ** 2 + (d.y - self.c.y) ** 2)
        plant = self.rng.choice(foods[:5])
        # fica ao lado da planta, virado para ela
        first = self.rng.choice((-1, 1))
        for side in (first, -first):
            spot = (plant.x + side * 34, plant.y + 2)
            if not self.world.blocked(self.c.feet_rect(*spot)):
                break
        yield from self.walk_to(spot)
        if math.hypot(spot[0] - self.c.x, spot[1] - self.c.y) > 20:
            return
        self.face("left" if plant.x < self.c.x else "right")
        plant.rustle = 0.8
        yield from self.play("eat")
        self.hunger = max(0.0, self.hunger - 0.65)
        self.say("eat")
        yield from self.wait(2)

    def t_sleep(self, night):
        self.say("sleepy")
        yield from self.wait(2.0)
        cave = self.find_cave() if night and self.c.locomotion != "burrow" else None
        if cave:                             # à noite dorme na caverna
            self.say("cave_sleep", 0.6)
            inside = yield from self.go_into_cave(cave)
            if not inside:
                cave = None
        if not cave and self.c.locomotion != "burrow":
            # procura um cantinho tranquilo por perto (o Grub só se enterra onde está)
            yield from self.walk_to(self.free_point(160))
        try:
            yield from self._sleep_here(night)
        finally:
            if self.c.in_cave and self.c.state not in ("sleep", "lie_down"):
                self._leave_cave_now()

    def _sleep_here(self, night):
        self.c.toggle_sleep()  # deita -> dorme
        yield
        duration = self.rng.uniform(300, 600) if night else self.rng.uniform(60, 150)
        t, next_z = 0.0, 3.0
        while t < duration:
            if self.c.state not in ("lie_down", "sleep"):
                return  # foi acordado (ex.: jogador)
            if night and self.env.phase in ("Amanhecer", "Dia") and t > 30:
                break   # amanheceu
            next_z -= self.dt
            if next_z <= 0 and self.c.state == "sleep":
                next_z = self.rng.uniform(4, 8)
                self.say("sleeping")
            yield
            t += self.dt
        self.c.toggle_sleep()  # acorda
        while self.c.state == "wake":
            yield
        if self.c.in_cave:
            yield from self.leave_cave()
        phase = self.env.phase
        if night and phase in ("Amanhecer", "Dia"):
            self.say("wake_day")        # dormiu a noite e amanheceu
        elif phase == "Noite":
            self.say("wake_night")      # acordou no meio da noite
        else:
            self.say("wake_nap")        # soneca durante o dia
        self.boredom = 0.2
        yield from self.wait(2)


# ==========================================================================
# HORNET — séria, treina muito, costura sentada, toca a agulha (needolin).
# Fala com as palavras dela do jogo ("Shaw!", "Garama!", "Adino!", "Hegale!").
HORNET_LINES = {
    "greet":      ["Hmph.", "O que foi?", "...", "Adino.", "Sim?"],
    "bored":      ["...", "Hmph.", "Tédio é para os fracos.", "Hm."],
    "wander":     ["Hegale!", "Por ali.", "Edino!", "Hm."],
    "idle":       ["...", "Hm.", "Silêncio.", "Fique atento."],
    "sleepy":     ["Descansar... só um pouco.", "Hm... cansada.", "Até os fortes descansam."],
    "sleeping":   ["...", "zz...", "hm..."],
    "wake_day":   ["Amanheceu.", "De pé.", "Hm. Bom."],
    "wake_nap":   ["Já basta.", "De volta ao trabalho.", "Hm."],
    "wake_night": ["Ainda é noite.", "...", "Hm."],
    "thirsty":    ["Água.", "Hm, sede.", "Uma pausa."],
    "drink":      ["...", "Hm. Fresca.", "Melhor."],
    "train":      ["Shaw!", "Garama!", "Adino!", "Hegale!", "Edino!"],
    "train_end":  ["Nada mal.", "Hm. Bom.", "Mais afiada."],
    "look":       ["Hm?", "...", "Algo se move.", "Fique atento."],
    "sew":        ["costurando...", "esta seda...", "linha e agulha.", "Hm. Quase."],
    "sit":        ["Uma pausa.", "...", "Que lugar quieto."],
    "rain_start": ["Chuva.", "Hm. Molhada.", "Tsc."],
    "rain":       ["Chuva incômoda.", "...", "Hm."],
    "thunder":    ["Tsc!", "Hm!", "Shaw!"],
    "hot":        ["Calor demais.", "{temp} graus. Hm.", "{city}... quente."],
    "night":      ["A noite é minha.", "Silêncio.", "Hm. Escuro."],
    "evening":    ["O sol se vai.", "Hm. Tarde."],
    "morning":    ["Bom dia, se é que existe.", "Hm. Dia."],
    "stars":      ["Estrelas.", "Hm."],
    "bench":      ["Um banco. Hm.", "Descanso breve.", "Bom lugar.", "..."],
    "bench_night": ["A luz é boa aqui.", "Noite calma.", "..."],
    "shade_see":  ["Uma sombra...", "Vazio.", "Tsc. Aquilo de novo.", "Fique longe."],
    "shade_ask":  ["Saia daqui.", "O que você quer?", "Hm..."],
    "shade_gone": ["Foi embora.", "Hm. Melhor assim."],
    "needolin":   ["Ouça.", "Uma canção antiga.", "...", "*toca a agulha*"],
    "needolin_night": ["Para a noite.", "Uma canção de casa.", "..."],
    "needolin_end": ["Hm.", "Basta por hoje.", "..."],
}


class HornetBrain(Brain):
    LINES = HORNET_LINES
    HAS_HUNGER = False
    DRINK_ANIMS = [("eat", None), ("eat", None)]   # agacha e bebe
    SOCIAL_OK = Brain.SOCIAL_OK + ("olhar em volta", "sentar")

    def choose(self):
        night = self.env.phase == "Noite"
        if self.energy < SLEEP_THRESHOLD or (night and self.energy < NIGHT_SLEEP_THRESHOLD):
            return "dormir", self.t_sleep(night)
        if self.thirst > NEED_THRESHOLD and self.world.shore:
            return "beber", self.t_drink()
        options = [
            ("passear", self.t_wander, 30 + 20 * self.boredom),
            ("olhar em volta", self.t_look, 18),
            ("sentar", self.t_sit, 12),
            ("costurar", self.t_sew, 14),
            ("treinar", self.t_train, 14 + 10 * self.boredom),
            ("parado", self.t_idle, 12),
            ("banco", self.t_bench, self.bench_weight()),
            ("pular", self.t_jump, 3 + 5 * self.boredom),
            ("tocar", self.t_needolin, self.needolin_weight()),
        ]
        if self.thirst > 0.45 and self.world.shore:
            options.append(("beber", self.t_drink, 18))
        names, fns, weights = zip(*options)
        i = self.rng.choices(range(len(fns)), weights=weights)[0]
        return names[i], fns[i]()

    def force(self, name, gen):
        # se estava sentada/costurando, levanta antes de ir
        if self.c.state in ("sit", "sew"):
            gen = self._stand_then(gen)
        super().force(name, gen)

    def _stand_then(self, gen):
        yield from self.play("stand_up")
        yield from gen

    def needolin_weight(self):
        if "needolin" not in self.c.sheets:
            return 0
        return 4 + (6 if self.env.phase in ("Tarde", "Entardecer", "Noite") else 0)

    def t_needolin(self):
        """Toca a agulha como um instrumento. Quem estiver livre vem ouvir."""
        night = self.env.phase == "Noite"
        yield from self.walk_to(self.free_point(260))
        self.say("needolin_night" if night and self.rng.random() < 0.5 else "needolin", 0.6)
        self.c.do_action("needolin")
        for o in getattr(self, "others", ()):
            if o is not self.c and o.brain:
                o.brain.listen_to(self.c)
        try:
            t, until = 0.0, self.rng.uniform(25, 45)
            while t < until and self.c.state == "needolin":
                yield
                t += self.dt
        finally:
            if self.c.state == "needolin":
                self.c.state = "idle"
        self.say("needolin_end", 0.6)
        self.boredom = max(0.0, self.boredom - 0.5)
        yield from self.wait(1.5)

    def t_look(self):
        self.say("look", 0.5)
        yield from self.play("look")
        self.boredom = max(0.0, self.boredom - 0.1)
        yield from self.wait(self.rng.uniform(1, 3))

    def t_sit(self):
        self.say("sit", 0.5)
        yield from self.play("sit", hold=self.rng.uniform(10, 25))
        yield from self.play("stand_up")
        self.boredom = max(0.0, self.boredom - 0.2)

    def t_sew(self):
        # vai a um canto calmo, senta e costura
        yield from self.walk_to(self.free_point(250))
        self.say("sew", 0.8)
        yield from self.play("sew", hold=self.rng.uniform(15, 35))
        if self.rng.random() < 0.5:
            self.say("sew")
        yield from self.play("stand_up")
        self.boredom = max(0.0, self.boredom - 0.4)

    def t_train(self):
        self.say("train", 0.9)
        yield from self.wait(0.4)
        for _ in range(self.rng.randint(2, 4)):
            if self.rng.random() < 0.4:
                self.face("left" if self.c.facing == "right" else "right")
            yield from self.play("attack")
            if self.rng.random() < 0.3:
                self.say("train")
            yield from self.wait(self.rng.uniform(0.25, 0.7))
        self.say("train_end", 0.5)
        self.boredom = max(0.0, self.boredom - 0.4)
        self.energy = max(0.0, self.energy - 0.015)
        yield from self.wait(1.5)


# ==========================================================================
# GRUB — fofo, carente. Não anda: se enterra e brota em outro lugar.
GRUB_LINES = {
    "greet":      ["oi!!", "eba!", "hihi", "amigo!", "*grub grub*"],
    "bored":      ["sozinho...", "alguém aí?", "*suspiro*", "brincar?"],
    "idle":       ["*grub*", "hihi", "*mexe*", "...", "*grub grub*"],
    "happy":      ["eba!", "yay!", "hihi!", "que bom!", "uiii"],
    "cry":        ["buáá", "*snif*", "sozinho...", "buá..."],
    "travel":     ["*cava cava*", "fui!", "hihi, sumi"],
    "arrive":     ["cheguei!", "tcharam!", "*pop*"],
    "sleepy":     ["soninho...", "*boceja*", "vou pra toca"],
    "sleeping":   ["zz", "*ronc*", "zZ"],
    "wake_day":   ["bom diaaa!", "*pop*", "acordei!"],
    "wake_nap":   ["*pop*", "oi de novo!", "acordei!"],
    "wake_night": ["tá escuro...", "*pop*"],
    "rain_start": ["chuva!", "molhou!", "hihi, chuva"],
    "rain":       ["plic plic", "*treme*"],
    "thunder":    ["buáá!", "medo!", "*treme*"],
    "hot":        ["calor...", "*derrete*"],
    "night":      ["escurinho...", "medo do escuro"],
    "evening":    ["o céu tá laranja!"],
    "morning":    ["dia!", "sol!"],
    "stars":      ["estrelinhas!"],
    "shade_see":  ["medo!!", "buáá!", "fantasma!", "*treme*"],
    "listen":     ["música!", "lalala!", "hihi, que bonito", "*balança*"],
    "listen_end": ["de novo!", "eba!!", "mais!"],
}


class GrubBrain(Brain):
    LINES = GRUB_LINES
    HAS_HUNGER = False
    HAS_THIRST = False
    SOCIAL_OK = ("parado", "feliz", "chorar", "passear")

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.lonely = 0.0   # sobe quando ninguém chega perto; alto = chora
        self.others = ()    # outros personagens (o Game preenche)

    def available(self):
        return self.manual <= 0 and self.task_name in self.SOCIAL_OK and self.c.state in ("idle", "cry", "happy")

    def update(self, dt):
        near = any(o is not self.c and math.hypot(o.x - self.c.x, o.y - self.c.y) < 160 for o in self.others)
        self.lonely = max(0.0, self.lonely - dt / 20) if near else min(1.0, self.lonely + dt / 240)
        return super().update(dt)

    def choose(self):
        night = self.env.phase == "Noite"
        if self.energy < SLEEP_THRESHOLD or (night and self.energy < NIGHT_SLEEP_THRESHOLD):
            return "dormir", self.t_sleep(night)
        options = [
            ("parado", self.t_idle, 45),
            ("feliz", self.t_happy, 5),
            ("passear", self.t_travel, 6),
            ("chorar", self.t_cry, 25 * self.lonely),
        ]
        names, fns, weights = zip(*options)
        i = self.rng.choices(range(len(fns)), weights=weights)[0]
        return names[i], fns[i]()

    def t_idle(self):
        yield from self.wait(self.rng.uniform(6, 14))
        if self.rng.random() < 0.4:
            self.face("left" if self.c.facing == "right" else "right")
            self.say("idle", 0.2)

    def t_happy(self):
        self.say("happy", 0.5)
        for _ in range(self.rng.randint(1, 2)):
            yield from self.play("happy")
        yield from self.wait(1)

    def t_cry(self):
        self.say("cry")
        yield from self.play("cry", hold=self.rng.uniform(5, 10))
        yield from self.wait(1)

    def react_shade(self, shade):
        if self.c.state in ("sleep", "lie_down") or self.manual > 0:
            return
        self.say("shade_see")
        if math.hypot(shade.x - self.c.x, shade.y - self.c.y) < 500:
            self.force("esconder", self.t_hide())

    def t_hide(self):
        """Se enterra de medo e só sai depois de um tempo."""
        yield from self.play("lie_down")
        t, until = 0.0, self.rng.uniform(12, 20)
        while t < until:
            yield
            t += self.dt
        self.c.do_action("wake")
        yield
        while self.c.state == "wake":
            yield
        self.say("arrive", 0.5)

    def t_travel(self):
        self.say("travel", 0.4)
        target = self.free_point(320)
        yield from self.burrow_to(target)
        self.say("arrive", 0.3)
        yield from self.wait(1)
