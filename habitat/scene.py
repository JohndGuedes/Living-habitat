"""Layout do habitat: as áreas (ilhas), o que existe em cada uma e como se liga.

Cada área usa a pasta assets/sprites/world/areas/<nome>/ gerada por
tools/make_areas.py (ground.png, walkable.png, water.png, meta.json, cave.png).

Posições ("img_pos", "spawn", "at", "arrive") em px da imagem ground.png da área
(o jogo converte para a tela). Objetos ("props"): "kind" (props.py), "img_pos" =
BASE do objeto (centro de baixo, onde encosta no chão) e opções do tipo
("file", "scale" relativa à ilha, "seats", "lights"...).

"seasons": {estação: {...}} troca chaves da área naquela estação (ex.: outro "folder" = outro
mapa no Natal, com seus "props", "spawn", "jumps").
"jumps": [(a, b)] pares de pontos ligados por um pulo (ex.: por cima da cachoeira).
"effects": efeitos animados por cima do chão (effects.py), ex.: {"kind": "waterfall", ...}.
"exits": por onde o personagem passa para outra área: chega em "at" e aparece
na outra área em "arrive".
"top_room": espaço (px da imagem) reservado acima da ilha (a caverna passa do topo).
"""

AREAS = {
    "lago": {
        "folder": "world/areas/lago",
        "props": [
            # Banco (o poste saiu por enquanto: {"kind": "lamp", "file": "items/cliffs_lamp.png", ...})
            {"kind": "bench", "img_pos": (488, 268), "file": "items/town_bench_lit.png", "scale": 0.5,
             "seats": [-24, 24], "approach_dy": 22},
        ],
        "spawn": (465, 392),
        "spawns": {"daughter": (600, 380), "hornet": (612, 429), "grub": (367, 465), "hollow": (540, 415)},
        "exits": [
            {"to": "casa", "at": (456, 148), "return_at": (472, 172), "arrive": (740, 445), "label": "Entrar na casa"},
        ],
        "fairies": {"swarms": 3, "size": (3, 6), "scale": 0.3},   # fadinhas (fairies.py)
        # plantas pintadas no chão balançando de leve (effects.PlantSway): (x0, y0, x1, y1), y1 = base
        "effects": [
            {"kind": "sway", "plants": [
                (555, 155, 615, 205), (705, 215, 800, 265), (195, 312, 255, 362), (290, 378, 340, 425),
                (635, 405, 710, 455), (630, 328, 672, 366), (745, 305, 812, 362), (825, 288, 880, 340),
                (700, 345, 735, 386), (348, 160, 382, 200), (270, 52, 305, 82), (378, 462, 428, 500),
                (350, 452, 390, 493), (448, 450, 495, 486), (195, 198, 235, 240), (912, 152, 955, 186),
                (372, 362, 412, 398),
            ]},
        ],
        # Em outras estações a área troca de mapa (e tudo que depende dele)
        "seasons": {
            "natal": {
                "folder": "world/areas/natal",      # ground-natal.jpg: dois níveis, cachoeira
                "props": [
                    {"kind": "bench", "img_pos": (700, 783), "file": "items/town_bench_lit.png", "scale": 1.0,
                     "seats": [-24, 24], "approach_dy": 22},
                    {"kind": "snowman", "img_pos": (830, 880), "file": "world/library/natal/boneco_neve_knight.png",
                     "scale": 0.9, "name": "boneco_neve_knight"},
                    {"kind": "snowman", "img_pos": (1520, 890), "file": "world/library/natal/boneco_neve_hornet.png",
                     "scale": 0.9, "name": "boneco_neve_hornet"},
                    {"kind": "campfire", "img_pos": (1225, 1230), "file": "world/library/natal/fogueira.png",
                     "scale": 0.85, "name": "fogueira"},
                    {"kind": "grub_natal", "img_pos": (980, 1180), "file": "world/library/natal/grub_natal.png",
                     "scale": 0.85, "name": "grub_natal"},
                ],
                "spawn": (1167, 867),
                "spawns": {"daughter": (1417, 933), "hornet": (1300, 1000), "grub": (900, 1000), "hollow": (1060, 960)},
                "exits": [
                    {"to": "casa", "at": (640, 438), "return_at": (690, 470), "arrive": (740, 445), "label": "Entrar na casa"},
                ],
                # pulos: os personagens pulam de um ponto para o outro (por cima da cachoeira)
                "jumps": [((1975, 292), (2308, 375))],
                # luzes (lighting.py), em px da imagem: luz quente + fios de pisca-pisca do desenho
                "lighting": {
                    "warm": [
                        # porta: luz de dentro da casa, saindo pela abertura e se espalhando no chão
                        # (a parede da porta é diagonal: soleira na direção "edge", luz para a frente dela)
                        {"kind": "opening", "rect": (590, 330, 42, 92), "edge": (1.0, -0.45),
                         "spill": (1.0, 0.5, 150, 2.0), "radius": 70, "color": (255, 150, 70), "flicker": 0.06},
                        # janela
                        {"kind": "opening", "rect": (442, 340, 24, 40), "edge": (1.0, 0.3),
                         "spill": (-0.3, 1.0, 40, 1.8), "radius": 40, "color": (255, 170, 85), "flicker": 0.08},
                        {"pos": (277, 290), "radius": 80, "color": (255, 170, 80), "flicker": 0.2},    # lanterna
                        {"pos": (238, 345), "radius": 80, "color": (255, 170, 80), "flicker": 0.2},    # lanterna
                        {"pos": (686, 98), "radius": 65, "color": (220, 190, 110), "flicker": 0.05},   # estrela
                    ],
                    "strings": [
                        [(395, 325), (440, 335), (490, 345), (540, 335), (575, 320)],      # casa
                        [(668, 140), (700, 150), (662, 178), (712, 190), (655, 213), (722, 222)],  # árvore
                        [(268, 335), (270, 375), (300, 400), (330, 410), (365, 412)],     # pedra grande
                        [(265, 480), (300, 500), (340, 505), (375, 495)],
                        [(215, 575), (255, 600), (300, 605), (345, 595), (385, 575)],     # pedras de baixo
                        [(450, 505), (480, 470), (515, 475), (540, 500)],
                        [(1395, 95), (1400, 140), (1415, 175), (1440, 180), (1470, 165), (1495, 145)],  # arco
                        [(2470, 705), (2495, 698), (2520, 690), (2548, 698), (2565, 705)],  # colunas da direita
                        [(2375, 845), (2400, 852), (2425, 842), (2445, 850)],
                        [(273, 953), (295, 975), (318, 975), (328, 952)],                 # coluna de baixo
                    ],
                    "sheen": True,                          # brilho deslizando no gelo
                },
                # a água da cachoeira correndo (effects.py): cascata de cima -> riacho -> queda
                "effects": [
                    {"kind": "waterfall", "rect": (2208, 165, 72, 170), "dir": (0, 1), "speed": 150,
                     "splash": (2214, 2272, 330)},
                    {"kind": "waterfall", "rect": (2050, 318, 195, 72), "dir": (-0.85, 0.5), "speed": 70},
                    {"kind": "waterfall", "rect": (2060, 378, 128, 290), "dir": (0, 1), "speed": 180,
                     "splash": (2040, 2200, 668), "mist": True},
                    # plantas pintadas no chão balançando de leve: (x0, y0, x1, y1), y1 = base
                    {"kind": "sway", "plants": [
                        (545, 858, 655, 955), (655, 905, 750, 972),          # samambaias + capim (esq.)
                        (770, 1055, 895, 1132), (985, 995, 1085, 1050),
                        (955, 1248, 1045, 1308), (1048, 1245, 1112, 1335),
                        (652, 1238, 728, 1288), (122, 1018, 202, 1068),
                        (538, 558, 612, 645),                                # perto da escada da casa
                        (1532, 718, 1648, 802), (1708, 902, 1808, 983),      # perto do lago
                        (1892, 942, 1962, 1033), (1982, 897, 2112, 998),
                        (2248, 803, 2345, 900),
                        (1718, 1102, 1852, 1215), (1848, 1122, 1912, 1198), (2088, 1137, 2152, 1203),
                        (2572, 1088, 2638, 1155),
                        (1308, 132, 1382, 212), (1092, 244, 1188, 298),      # platô de cima
                        (1838, 254, 1958, 327), (1762, 104, 1822, 172), (1508, 436, 1598, 538),
                    ]},
                ],
            },
        },
    },
    "casa": {
        "folder": "world/areas/casa",
        "indoor": True,
        "props": [
            {"kind": "bed", "img_pos": (510, 405), "file": "world/library/casa/cama_azul.png",
             "scale": 0.54, "name": "cama_azul", "approach_rel": 0.20},
            {"kind": "bed", "img_pos": (290, 560), "file": "world/library/casa/cama_vermelha.png",
             "scale": 0.54, "name": "cama_vermelha", "approach_rel": 0.20},
        ],
        "spawn": (535, 515),
        "spawns": {"daughter": (605, 535), "hornet": (620, 500), "grub": (450, 540), "hollow": (480, 490)},
        "exits": [
            {"to": "lago", "at": (815, 412), "return_at": (740, 445), "arrive": "door", "label": "Sair da casa"},
        ],
        "lighting": {
            "warm": [
                {"pos": (290, 345), "radius": 150, "color": (255, 145, 65), "flicker": 0.14},
                {"pos": (716, 195), "radius": 115, "color": (255, 180, 90), "flicker": 0.08},
                {"pos": (428, 175), "radius": 85, "color": (165, 195, 235), "flicker": 0.03},
            ],
        },
    },
}
START_AREA = "lago"

# Plantas animadas (decor.py, arte world/gramas/gramas.png) por área: tipo -> quantidade.
# As ilhas novas já têm plantas desenhadas e a arte das gramas é bem mais clara,
# então começam sem (dá para ligar aqui por área).
DECOR = {}
# Tamanho (fração do desenho original). "*" = padrão.
DECOR_SCALE = {"*": 0.3, "grama_pequena": 0.32, "arbusto": 0.34}
# Quais tipos são sólidos (largura, profundidade da base, em px de tela)
DECOR_SOLID = {"arbusto": (56, 14)}
# Mude a semente para sortear outra distribuição
DECOR_SEED = 7
