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
            "idle":     {"dir": "idle_still", "frame_duration": 0.12},
            "walk":     {"dir": "walk", "frame_duration": 0.09},
            # Deitar = levantar do chão ao contrário; dormir = quadros deitado
            "lie_down": {"dir": "wake_up_ground", "start": 5, "reverse": True,
                         "frame_duration": 0.06, "loop": False, "next": "sleep"},
            "sleep":    {"dir": "wake_up_ground", "end": 5, "frame_duration": 0.5},
            "wake":     {"dir": "wake_up_ground", "start": 5,
                         "frame_duration": 0.07, "loop": False},
            # Comer = se abaixar para pegar algo (collect)
            "eat":      {"dir": "collect_normal", "frame_duration": 0.08, "loop": False},
            "jump":     {"dir": ["jump", "fall", "land"], "frame_duration": 0.05,
                         "loop": False, "hop": 70},
            # Sentado no banco, de frente (a rotina levanta o desenho até o assento)
            "bench_sit": {"dir": "sit", "pick": [0, 1, 2, 3, 4, 3, 2, 1], "frame_duration": 0.22,
                          "art_faces": None},
            # Olhar para cima / para baixo e ficar assim ("hold") até a rotina mudar
            "look_up":   {"dir": "look_up", "frame_duration": 0.08, "loop": False, "next": "hold"},
            "look_down": {"dir": "look_down", "frame_duration": 0.08, "loop": False, "next": "hold"},
            # Golpe de ferrão; o 8º quadro (índice 7) é quando a lâmina acerta
            "attack":   {"dir": "slash_left_longer", "frame_duration": 0.045,
                         "loop": False, "hit_frame": 7},
        },
    },
    "hornet": {
        # Frames soltos em assets/sprites/character/Hornet/ (prefixo + número) e
        # quadros "no ar" tirados do atlas por tools/extract_hornet.py.
        # Não há animação de andar: ela se move SALTANDO (locomotion "leap").
        "frames_root": "character/Hornet",
        "align": "per_anim",
        "scale": 0.6,
        "art_faces": "left",
        "speed": 340,              # velocidade durante o salto
        "locomotion": "leap",
        "shadow": (40, 9),
        "seat_drop": 22,
        "animations": {
            # (estas duas olham para a DIREITA na arte; as outras para a esquerda)
            "idle":      {"files": "peak_needolin_look", "pick": [0], "frame_duration": 1.0,
                          "art_faces": "right"},
            "look":      {"files": "peak_needolin_look", "frame_duration": 0.11, "loop": False,
                          "art_faces": "right"},
            # salto: agacha -> no ar (arco) -> aterrissa
            "takeoff":   {"files": "hornet_heart_grab_land", "pick": [13, 11, 9, 7],
                          "frame_duration": 0.035, "loop": False, "next": "leap"},
            "leap":      {"dir": "frames/air", "pick": [0, 0, 1, 1, 1], "frame_duration": 0.07,
                          "loop": False, "next": "land", "hop": 55},
            "land":      {"files": "hornet_heart_grab_land", "pick": [4, 6, 8, 10, 12, 13],
                          "frame_duration": 0.045, "loop": False},
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
