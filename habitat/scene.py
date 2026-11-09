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
            # Banco (o poste saiu por enquanto: {"kind": "lamp", "file": "items/cliffs_lamp.png", ...})
            {"kind": "bench", "img_pos": (500, 440), "file": "items/town_bench_lit.png", "scale": 1.3,
             "seats": [-38, 38]},
        ],
        "spawn": (760, 640),
        "spawns": {"daughter": (980, 620), "hornet": (1000, 700), "grub": (600, 760)},
        "exits": [],
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
