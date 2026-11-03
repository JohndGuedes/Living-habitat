"""Layout do habitat: o que existe no mapa e onde.

O cenário está sendo refeito aos poucos: por enquanto só o chão (a ilha).
Para colocar objetos de volta, adicione entradas como:
    {"kind": "tree", "pos": (900, 330)}
Tipos disponíveis em props.py: house, tree, campfire, dummy.

"pos" = BASE do objeto (centro de baixo, onde encosta no chão), em pixels de
tela (1280x720). Opcionais: "footprint": (largura, profundidade) da área
sólida; "scale" da arte (PNG em assets/sprites/world/<tipo>.png);
"shade": (raio_x, raio_y) da sombra da árvore; "lights": janelas acesas.
"""

SCENE = [
    # Banco (Knight e Hornet sentam aqui) e o poste logo atrás dele
    {"kind": "lamp", "pos": (505, 292), "file": "items/cliffs_lamp.png", "scale": 0.6,
     "base_offset": 42, "lights": [(-83, -313), (74, -400)]},
    {"kind": "bench", "pos": (425, 330), "file": "items/town_bench_lit.png", "scale": 0.95,
     "seats": [-38, 38]},
]

# Plantas animadas espalhadas pela grama (decor.py). Tipo -> quantidade.
# Tipos: grama_alta, grama_cheia, grama_pequena, flor_branca, flor_vermelha,
# flor_amarela, flor_azul, arbusto, arbusto_rosa, arbusto_branco, arbusto_liso
DECOR = {
    "grama_alta": 9,
    "grama_cheia": 6,
    "grama_pequena": 14,
    "flor_branca": 3,
    "flor_vermelha": 3,
    "flor_amarela": 3,
    "flor_azul": 3,
    "arbusto": 2,
    "arbusto_rosa": 2,
    "arbusto_branco": 1,
    "arbusto_liso": 2,
}
# Tamanho (fração do desenho original). "*" = padrão.
DECOR_SCALE = {"*": 0.3, "grama_pequena": 0.32, "arbusto": 0.34}
# Quais tipos são sólidos (largura, profundidade da base, em px de tela)
DECOR_SOLID = {"arbusto": (56, 14)}
# Mude a semente para sortear outra distribuição
DECOR_SEED = 7

# Onde o personagem aparece ao abrir o jogo (se cair fora da grama, o jogo
# procura o ponto andável mais perto)
SPAWN = (560, 420)
# Onde cada morador aparece
SPAWNS = {"knight": (560, 420), "hornet": (820, 470), "grub": (420, 520)}
