# Sprites

```
assets/sprites/
├── character/
│   └── the_knight/   ← frames do Knight: uma pasta por animação (idle_still/, walk/, ...)
├── world/            ← arte dos objetos do cenário (veja abaixo)
├── items/            ← comida, brinquedos
└── ui/               ← ícones, balões (zZz, coração, fome)
```

## Knight (`character/the_knight/`)

Frames extraídos do jogo: **um PNG por quadro**, todos com 349x186 e o Knight sempre na mesma
posição. A arte olha para a esquerda, e o jogo espelha para a direita. A lista completa dos
sprites está em `Knight_aaaaa_info.txt`.

O jogo lê as pastas direto (não há spritesheet gerado). Para usar outra animação, adicione em
`habitat/sprite_defs.py`:

```python
"nome": {"dir": "pasta", "frame_duration": 0.1},
# opcionais: "start"/"end" (recorte), "reverse", "loop": False, "next", "hop"
```

Se uma pasta não existir, o jogo avisa no terminal e usa a animação parada no lugar.

## Chão (`world/ground/`)

- `source/island_reference.png`: a imagem original da ilha.
- `ground.png`: a ilha com fundo transparente, gerada por `tools/make_ground.py`.
- `walkable.png`: onde dá para andar (branco = anda, preto = não). É gerado pelo mesmo script e
  **pode ser retocado à mão**: pinte de preto onde não quer que ele ande, de branco onde quer.

## Plantas (`world/gramas/gramas.png`)

É uma folha com 7 linhas: grama alta, grama cheia e grama pequena; flores brancas e vermelhas; flores
amarelas e azuis; arbustos grandes; arbustos pequenos (rosa, branco e liso). Os desenhos de cada linha
são **variações** da mesma planta. O jogo sorteia uma variação para cada planta e faz o balanço ao vento
por código. Quantas plantas de cada tipo aparecem, e o tamanho delas, se ajusta em `habitat/scene.py`
(`DECOR`, `DECOR_SCALE`). Mude `DECOR_SEED` para sortear outra distribuição.

## Objetos do cenário (`world/`)

No momento nenhum objeto está no mapa (`habitat/scene.py` está vazio). Os tipos que já existem no código
são casa, árvore, fogueira e boneco de treino, com desenho provisório. Para usar arte de verdade,
coloque:

| Objeto | Imagem única | ou pasta com quadros (animação) |
|---|---|---|
| casa | `world/house.png` | `world/house/` |
| árvore | `world/tree.png` | `world/tree/` |
| fogueira | `world/campfire.png` | `world/campfire/` (ex.: chamas animadas) |
| boneco de treino | `world/dummy.png` | — (o balanço é feito por código) |

A **base** do objeto (onde ele toca o chão) é o centro da borda de baixo da imagem. Tamanho, área
sólida e posição se ajustam em `habitat/scene.py` (`scale`, `footprint`, `pos`).
