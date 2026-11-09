"""Definição dos sprites de cada personagem.

Dois formatos de animação:

1) Pasta de frames ("frames_root" no personagem) — um PNG por quadro, todos
   com o mesmo tamanho de tela (rips do jogo). Cada animação:
     "dir":    pasta (ou lista de pastas, tocadas em sequência)
     "start"/"end": recorte dos quadros (índices; end exclusivo)
     "reverse": True = toca de trás para frente
   O personagem é recortado/alinhado sozinho (veja assets._load_frame_folders).

2) Spritesheet em grade ("folder" + "file", "frames", "rows") — colunas =
   quadros, linhas = direções (8 = ordem PMD, 4 = down/left/right/up, 1 = todas).

Opções de qualquer animação:
  frame_duration  segundos por quadro
  loop            False = toca uma vez e vai para "next" (padrão "idle")
  next            animação seguinte quando loop=False
  hop             altura (px) de um pulo em arco durante a animação
  art_faces       vista lateral: lado para onde a arte olha; o outro é espelhado
                  (pode ficar no personagem, valendo para todas)

Animações que o jogo usa: idle, walk; sleep (com lie_down/wake opcionais),
eat, jump.
Opções do personagem: "scale", "speed" (px/s), "shadow" (largura, altura).
"""

CHARACTER_SPRITES = {
    "knight": {
        # Rips do Hollow Knight em assets/sprites/character/the_knight/<animação>/
        # (quadros de 349x186, arte olhando para a ESQUERDA).
        "frames_root": "character/the_knight",
        "scale": 0.75,
        "art_faces": "left",
        "speed": 180,
        "shadow": (46, 10),
        "seat_drop": 16,           # quanto as pernas ficam abaixo do assento (px de tela)
        "animations": {
            # --- parado / andando ---
            "idle":     {"dir": "idle_still", "frame_duration": 0.12},
            "walk":     {"dir": "walk", "frame_duration": 0.09},
            # andando de costas (para o fundo) e de frente (descendo, para a câmera)
            "walk_up":   {"dir": "into_door", "start": 2, "frame_duration": 0.1, "art_faces": None},
            "walk_down": {"dir": "tram_leave", "frame_duration": 0.1, "art_faces": None},
            # cansado (energia baixa): idle de pouca vida
            "tired":    {"dir": "idle_low_health", "frame_duration": 0.13},
            # à noite: com a lanterna ("glow" = acha a luz em cada quadro)
            "lantern_idle": {"dir": "lantern_idle", "frame_duration": 0.12, "glow": True},
            "lantern_walk": {"dir": "lantern_run", "frame_duration": 0.09, "glow": True},
            # andando lendo o mapa
            "walk_map":      {"dir": "walk_map", "frame_duration": 0.1},
            "walk_map_turn": {"dir": "walk_map_turn", "frame_duration": 0.15},
            # --- ações ---
            # Deitar = levantar do chão ao contrário; dormir = quadros deitado
            "lie_down": {"dir": "wake_up_ground", "start": 5, "reverse": True,
                         "frame_duration": 0.06, "loop": False, "next": "sleep"},
            "sleep":    {"dir": "wake_up_ground", "end": 5, "frame_duration": 0.5},
            "wake":     {"dir": "wake_up_ground", "start": 5,
                         "frame_duration": 0.07, "loop": False},
            # Comer/beber = se abaixar para pegar algo (collect)
            "eat":      {"dir": "collect_normal", "frame_duration": 0.08, "loop": False},
            # sentir o vento (cast)
            "cast":     {"dir": "cast", "frame_duration": 0.1, "loop": False},
            # pulo normal e pulo duplo (pulo + double_jump_v2 + queda + pouso)
            "jump":     {"dir": ["jump", "fall", "land"], "frame_duration": 0.05,
                         "loop": False, "hop": 70},
            "double_jump": {"dir": ["jump", "double_jump_v2", "fall", "land"], "frame_duration": 0.05,
                            "loop": False, "hop": 125},
            # Olhar para cima / para baixo e ficar assim ("hold") até a rotina mudar
            "look_up":   {"dir": "look_up", "frame_duration": 0.08, "loop": False, "next": "hold"},
            "look_down": {"dir": "look_down", "frame_duration": 0.08, "loop": False, "next": "hold"},
            # --- banco (de frente; a rotina levanta o desenho até o assento) ---
            # sit: quadros 0-1 = sentando; 2-4 = descendo do banco
            "sit_down":    {"dir": "sit", "end": 2, "frame_duration": 0.15, "loop": False,
                            "next": "bench_sit", "art_faces": None},
            "bench_sit":   {"dir": "sit", "pick": [1], "frame_duration": 1.0, "art_faces": None},
            "bench_leave": {"dir": "sit", "start": 2, "frame_duration": 0.1, "loop": False,
                            "art_faces": None},
            # lendo o mapa sentado (olha -> escreve)
            "map_look":  {"dir": "sit_map_look", "frame_duration": 0.18, "art_faces": None},
            "map_write": {"dir": "sit_map_write", "frame_duration": 0.12, "art_faces": None},
            # --- golpes ---
            # Golpe de ferrão; o 8º quadro (índice 7) é quando a lâmina acerta
            "attack":   {"dir": "slash_left_longer", "frame_duration": 0.045,
                         "loop": False, "hit_frame": 7},
            # Ataque 1: golpe carregado + brilho (_ effects/charge_slash_effect)
            "attack1":  {"dir": "charge_slash", "frame_duration": 0.06, "loop": False, "hit_frame": 3,
                         "effect": {"dir": "_ effects/charge_slash_effect", "start": 3, "scale": 0.8,
                                    "frame_duration": 0.05, "at": (-140, -40)}},
            # Ataque 2: giro (ciclone) + anel (_ effects/cyclone_slash_effect)
            "attack2":  {"dir": "cyclone_slash", "frame_duration": 0.06, "loop": False, "hit_frame": 3,
                         "effect": {"dir": "_ effects/cyclone_slash_effect", "start": 2,
                                    "frame_duration": 0.06, "at": (0, -38)}},
            # Ataque especial: carrega e solta (o brilho já vem nos quadros)
            "special":  {"dir": "nail_slash", "frame_duration": 0.06, "loop": False, "hit_frame": 13},
            # --- água (lago) ---
            # water_enter tem tela 225x336: "offset" encaixa no lugar dos outros
            "swim_enter": {"dir": "water_enter_to_idle", "offset": (61, -73), "frame_duration": 0.07,
                           "loop": False},
            "swim_idle":  {"dir": "water_surface_idle", "frame_duration": 0.12},
            "swim":       {"dir": "water_surface_swim", "frame_duration": 0.1},
        },
    },
    "hornet": {
        # Frames soltos em assets/sprites/character/Hornet/ (prefixo + número) e
        # pastas frames/* tiradas dos atlas por tools/extract_atlas.py:
        #   "Hornet main sprites - atlas2" -> idle, walk, run, jump_up, crouch
        #   "Hornet needolin - atlas0"     -> needolin (tocando a agulha)
        # Essas pastas são salvas com os pés no centro da imagem ("pivot": "center").
        "frames_root": "character/Hornet",
        "align": "per_anim",
        "scale": 0.6,
        "art_faces": "left",
        "speed": 150,              # andando
        "run_speed": 330,          # correndo (trajetos longos)
        "shadow": (40, 9),
        "seat_drop": 22,
        "animations": {
            # (idle, walk e needolin olham para a DIREITA na arte; run/jump para a esquerda)
            "idle":      {"dir": "frames/idle", "pivot": "center", "frame_duration": 0.09,
                          "art_faces": "right"},
            "walk":      {"dir": "frames/walk", "pivot": "center", "frame_duration": 0.085,
                          "art_faces": "right"},
            "run":       {"dir": "frames/run", "pivot": "center", "frame_duration": 0.045},
            # pulo: agacha -> sobe (arco desenhado pelo código) -> agacha ao pousar
            # (lista = crouch 0-7, jump_up 8-18, crouch 19-26)
            "jump":      {"dir": ["frames/crouch", "frames/jump_up", "frames/crouch"],
                          "pivot": "center", "loop": False, "frame_duration": 0.05, "hop": 75,
                          "pick": [3, 5, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 24, 22, 20]},
            # tocando a agulha como instrumento
            "needolin":  {"dir": "frames/needolin", "pivot": "center", "frame_duration": 0.1,
                          "art_faces": "right"},
            "look":      {"files": "peak_needolin_look", "frame_duration": 0.11, "loop": False,
                          "art_faces": "right"},
            # sentar e costurar
            # (desenhadas menores na origem: "scale" compensa)
            "sit":       {"files": "weaver_hornet_idle", "frame_duration": 0.16, "scale": 1.3},
            "sew":       {"files": "weaver_hornet_sew", "frame_duration": 0.12, "scale": 1.3},
            "stand_up":  {"files": "weaver_hornet_sew_ending", "start": 4, "frame_duration": 0.07,
                          "loop": False},
            # dormir (deita no chão)
            "lie_down":  {"files": "summit_hornet", "pick": [1, 3, 5, 7, 8, 9, 10],
                          "frame_duration": 0.12, "loop": False, "next": "sleep"},
            "sleep":     {"files": "summit_hornet", "pick": [10, 11, 12, 11], "frame_duration": 0.5},
            "wake":      {"files": "summit_hornet", "pick": [10, 9, 8, 7, 5, 3, 1],
                          "frame_duration": 0.1, "loop": False},
            # sentada no banco (quadros tirados do atlas por tools/extract_atlas.py)
            "bench_sit": {"dir": "frames/bench_sit", "pick": [0, 1], "frame_duration": 0.9, "scale": 0.75,
                          "art_faces": None},
            # abaixar (beber/comer) e golpe
            "eat":       {"files": "hornet_heart_grab_land", "pick": [12, 10, 8, 6, 4, 4, 4, 6, 8, 10, 12],
                          "frame_duration": 0.07, "loop": False},
            "attack":    {"files": "Beast_Slash_Hornet", "pick": [0, 1, 2, 3, 3],
                          "frame_duration": 0.07, "loop": False, "hit_frame": 1},
        },
    },
    "shade": {
        # A Sombra (atlas0 #10777 em NPCs, quadros tirados por tools/extract_atlas.py).
        # Não é morador: aparece de vez em quando à noite ou na chuva (apparition.py).
        "frames_root": "character/Shade/frames",
        "align": "per_anim",
        "scale": 0.68,
        "art_faces": "left",
        "animations": {
            "idle": {"dir": "idle", "pick": [0, 1, 2, 3, 4, 5, 4, 3, 2, 1], "frame_duration": 0.13},
        },
    },
    "grub": {
        # Recortado por tools/slice_grub.py. Não anda: viaja se enterrando e
        # brotando em outro lugar (locomotion "burrow"); dorme enterrado.
        "frames_root": "character/Grup/frames",
        "align": "per_anim",
        "scale": 0.5,
        "art_faces": "left",
        "speed": 0,
        "locomotion": "burrow",
        "shadow": (34, 8),
        "animations": {
            "idle":     {"dir": "idle", "frame_duration": 0.11},
            "cry":      {"dir": "cry", "frame_duration": 0.12},
            "happy":    {"dir": "freed", "end": 12, "frame_duration": 0.08, "loop": False},
            # enterrar / debaixo da terra / brotar (também usados para dormir)
            "lie_down": {"dir": "freed", "start": 12, "frame_duration": 0.09, "loop": False, "next": "sleep"},
            "sleep":    {"dir": "freed", "pick": [19, 18], "frame_duration": 0.8},
            "wake":     {"dir": "freed", "start": 12, "reverse": True, "frame_duration": 0.08, "loop": False},
        },
    },
}

# A Filha de Hallownest é uma skin do Knight: mesmas animações e mesmas pastas, com os
# quadros gerados por tools/make_skin.py em daughter_of_hollownest/frames/.
CHARACTER_SPRITES["daughter"] = {
    **CHARACTER_SPRITES["knight"],
    "frames_root": "character/daughter_of_hollownest/frames",
    "speed": 165,              # um pouco mais calma que o Knight
}
