"""Layout do habitat: as áreas (ilhas), o que existe em cada uma e como se liga.

Cada área usa a pasta assets/sprites/world/areas/<nome>/ gerada por
tools/make_areas.py (ground.png, walkable.png, water.png, meta.json, cave.png).

Posições ("img_pos", "spawn", "at", "arrive") em px da imagem ground.png da área
(o jogo converte para a tela). Objetos ("props"): "kind" (props.py), "img_pos" =
BASE do objeto (centro de baixo, onde encosta no chão) e opções do tipo
("file", "scale" relativa à ilha, "seats", "lights"...).

"exits": por onde o personagem passa para outra área: chega em "at" e aparece
na outra área em "arrive".
"top_room": espaço (px da imagem) reservado acima da ilha (a caverna passa do topo).
"""

AREAS = {
    "lago": {
        "folder": "world/areas/lago",
        "props": [
            # Banco e o poste logo atrás dele
            {"kind": "lamp", "img_pos": (610, 545), "file": "items/cliffs_lamp.png", "scale": 0.82,
             "base_offset": 42, "lights": [(-83, -313), (74, -400)]},
            {"kind": "bench", "img_pos": (500, 590), "file": "items/town_bench_lit.png", "scale": 1.3,
             "seats": [-38, 38]},
        ],
        "spawn": (760, 640),
        "spawns": {"hornet": (1000, 700), "grub": (600, 760)},
        # trilha de pedra no fundo -> ilha da caverna
        "exits": [{"to": "caverna", "at": (600, 80), "arrive": (240, 400)}],
    },
    "caverna": {
        "folder": "world/areas/caverna",
        "top_room": 150,
        "props": [
            # a caverna encaixada no fundo da ilha (abrigo: dorme aqui à noite e foge da chuva)
            {"kind": "cave", "img_pos": (735, 128), "file": "world/areas/caverna/cave.png", "scale": 1.0},
        ],
        "spawn": (700, 400),
        "spawns": {},
        # lado esquerdo -> ilha do lago
        "exits": [{"to": "lago", "at": (180, 385), "arrive": (640, 140)}],
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
