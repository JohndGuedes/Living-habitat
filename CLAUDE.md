# CLAUDE.md

Living Habitat: jogo **local de desktop** (Python + pygame-ce) em que um personagem vive num minimundo
e anda, come e dorme sozinho. O personagem é o **Knight (Hollow Knight)**. O projeto começou com
Pokémon (Froakie, Charmander), mas o usuário pediu para esquecer isso: não reintroduza Pokémon. O
projeto é feito **por etapas**, e o dono fala português: escreva comentários, logs e mensagens em PT-BR.

**Não é web.** O usuário recusou explicitamente HTML/Canvas: mantenha tudo em Python/pygame.

## Rodar

```powershell
.venv\Scripts\python main.py        # ou clique duas vezes em run.bat (cria a .venv se faltar)
python -m venv .venv; .venv\Scripts\python -m pip install -r requirements.txt   # setup manual
```

Moradores: **Knight** (controlável pelo teclado), **Hornet** e **Grub**. Cada um tem rotina própria
(`brain.py`) e eles se encontram e interagem (`social.py`). O Knight vive sozinho pela **rotina**. Usar o teclado assume o controle e a rotina volta
8 s depois da última tecla. Clicar nele sem arrastar faz ele responder (cutucão).

Teclas: WASD/setas para mover; **Z** para dormir/acordar, **E** para comer, **Espaço** para pular e
**F** para atacar (teclas de teste dos sprites); **T** para alternar a hora (auto/dia/tarde/noite) e
**R** para alternar a chuva (auto/sim/não), para testar o ambiente; **P** para o overlay de debug, que
também mostra as áreas sólidas; Esc para sair.

Janela (popup para deixar num canto do monitor observando):
- **F2**: fixar por cima.
- **F3**: sem borda.
- **F4**: transparência (100/85/70/55%).
- **F11**: tela cheia.
- **Roda do mouse**: tamanho.
- **Arrastar com o botão esquerdo**: mover.

A barra de botões aparece ao passar o mouse.

Não há testes automatizados. Para checar sem abrir janela, use `SDL_VIDEODRIVER=dummy`, crie
`Game(online=False)` (sem rede; ou `online=True` para buscar o clima real), chame `game.step(dt)` ou `game.character.update(dt, teclas, game.world)` e salve
`game.screen` com `pygame.image.save`. `step()` fica separado de `run()` justamente para isso.

## Arquitetura (`habitat/`)

- `config.py`: resolução interna **1280x720** (o personagem e a ilha são arte HD). Também define
  `CHARACTER`, FPS, caminhos, clima/localização e `WORLD_PIXEL` (ampliação dos desenhos provisórios
  dos objetos).
  A janela usa `pygame.SCALED`.
- `sprite_defs.py`: `CHARACTER_SPRITES`. É o único lugar a editar para adicionar ou trocar animações.
  Há dois formatos:
  - **Pasta de frames** (`frames_root`), usado pelo Knight. Cada animação tem `dir` (uma pasta ou uma
    lista de pastas tocadas em sequência), `start`/`end` (com end exclusivo) e `reverse`.
  - **Spritesheet em grade** (`folder` + `file`, `frames`, `rows`): suportado, mas não usado agora.

  Opções comuns:
  - `frame_duration`
  - `loop`: com `False`, a animação toca uma vez e vai para `next` (padrão `idle`)
  - `hop`: altura de um pulo em arco desenhado pelo código, com a sombra no chão
  - `art_faces`: indica uma vista lateral; o lado oposto é espelhado

  No nível do personagem: `scale`, `speed` e `shadow`.
- `assets.py`: `load_sprite_set`. `_load_frame_folders` recorta todas as animações pelo **mesmo
  retângulo** (a união das áreas visíveis), aplica `smoothscale` e põe a âncora (os pés) na base do 1º
  quadro de `idle`. Isso funciona porque os rips têm tamanho de tela e posição constantes. Pasta
  faltando gera aviso, sem erro.
- `spritesheet.py`: `SpriteSheet` (com `cells[direção][quadro]`, `anchor`, `next_state`, `hop`/`lift_at`
  e `flipped`), `Animator` e `dir_from_vector`. Para cima/baixo puros, a vista lateral usa o `facing`
  do personagem.
- `brain.py`: **a rotina**.
  - Necessidades (energia, fome, sede, tédio) com taxas por segundo no topo do arquivo. A energia
    cai bem mais rápido à noite, e a sede sobe mais rápido com calor de 30 °C ou mais.
  - `choose()` decide: dormir (energia baixa, ou à noite abaixo de 0,55), beber, comer, ou um sorteio
    com pesos entre passear, parado, treinar, pular, olhar o céu e ver o lago (o tédio aumenta os pesos
    das coisas divertidas).
  - **Tarefas são geradores** (`t_*`, onde cada `yield` é um quadro), montados com `walk_to` (segue
    `world.find_path` e desiste se ficar preso), `play(anim, hold=)`, `wait` e `face`.
  - Beber: vai a um ponto de `world.shore`, vira para a água, faz `look_down` e depois `eat` duas vezes.
  - Comer: vai ao lado de uma flor ou arbusto pequeno, `eat`, e a planta se agita.
  - Dormir: `toggle_sleep` (lie_down → sleep) com "zZz" periódico. À noite dorme 5–10 min e acorda ao
    amanhecer; de dia tira sonecas de 1–2,5 min.
  - Falas: o dicionário `LINES` (grupos de frases, com `{temp}`/`{city}` vindos do clima real) é
    usado por `say(grupo)`. `context_chat` comenta o momento a cada 25–55 s, e `_events` reage ao
    início da chuva e a relâmpagos.
  - `take_manual()` pausa por `MANUAL_PAUSE`; `poke()` responde ao clique.
  - Subclasses:
    - `HornetBrain`: falas próprias ("Shaw!", "Garama!"...), sem fome; senta, costura, olha em volta,
      treina, pula e toca a agulha como instrumento (`t_needolin`, mais à tarde e à noite).
      `force()` faz ela levantar antes se estiver sentada.
    - `GrubBrain`: sem fome nem sede; `lonely` sobe quando ninguém está perto (até 160 px), e com
      isso ele chora. Também fica feliz e viaja por `burrow_to`.
  - Comum a todos:
    - `available()`/`SOCIAL_OK` dizem se o personagem pode ser chamado para um encontro.
    - `force(nome, gerador)` troca a tarefa.
    - `free_point()` escolhe destinos longe dos outros.
    - `DRINK_ANIMS` define como cada um bebe.
    - `listen_to(musician)`/`t_listen`: quando a Hornet começa a tocar, quem estiver livre às vezes
      vem ouvir, fica virado para ela e aplaude no fim (o Grub fica feliz).
    - `walk_to` corre (`character.running`) quando o caminho passa de `RUN_DIST` e o personagem tem a
      animação `run`. No último passo o vetor é encurtado para não passar do ponto.
- **Banco** (`Brain.t_bench`, `sit_on`/`leave_bench`): Knight e Hornet vão a um assento livre
  (`Bench.free_seat`, com o assento reservado ao sair) e sentam com a animação `bench_sit`, desenhados
  `seat_lift = bench.seat_height - seat_drop` acima. São mais frequentes à tarde e à noite
  (`bench_weight`).
  - Levantar acontece no `finally` da tarefa. Por isso `force`/`take_manual` chamam `task.close()`
    (`_drop_task`).
  - `separate()` ignora quem está sentado.
- **Sombra**: `react_shade(shade)` faz o Knight ou a Hornet ir ver de perto (`t_approach_shade`) e o
  Grub se esconder na terra (`t_hide`).
- `apparition.py`: `Shade`, que não é moradora.
  - Só aparece à noite ou com chuva (`eligible`), a cada `CHECK_EVERY` com `CHANCE`, num ponto longe
    de todos.
  - Surge e some aos poucos (`alpha`), flutua, deriva e olha para quem está perto.
  - Some depressa se alguém chegar a menos de `SCARE_DIST`.
  - `pop_appeared()` avisa o Game para os moradores reagirem.
  - É desenhada DEPOIS da luz, para não escurecer. A tecla **G** a chama.
- `social.py`: `Society`, os encontros.
  - A cada `CHECK_EVERY`, com `CHANCE`, escolhe um par livre de `SCRIPTS` (respeitando `COOLDOWN` por
    par). Grub chorando tem prioridade: `COMFORT`, onde alguém vai consolá-lo.
  - O diretor (`_direct`) manda os dois para pontos lado a lado (`_spots`; o Grub fica parado e o outro
    vai até ele), espera os dois chegarem (`Meeting`) e encena o roteiro: `(quem, fala, ação)`.
  - Cada participante roda `_attend`. Se o jogador assumir o Knight, o encontro é cancelado.
  - `_maybe_bench`: se um está sentado, o outro às vezes vem sentar junto; à tarde ou à noite, às
    vezes vão os dois. Com os dois sentados, roda `BENCH_SCRIPTS` (ou `BENCH_NIGHT_SCRIPTS`), com
    `BENCH_COOLDOWN` entre as conversas.
- `character.py`: `locomotion` vem do sprite_def:
  - `walk`: anda normalmente; com `running` e a animação `run`, corre a `run_speed`.
  - `leap`: com vetor de movimento, toca `takeoff → leap → land` e só avança no ar (não usado agora).
  - `burrow`: não anda; a rotina enterra e faz brotar em outro lugar (Grub).

  `Character` tem `x`/`y` (os **pés**), `dir`, `facing` e `state`. O `state` é o nome
  da animação: idle, walk, run, lie_down, sleep, wake, eat ou jump. Um vetor menor que 1 dá um passo
  mais curto.
  - `update(dt, axis, world)` recebe um vetor de movimento (float), vindo do teclado (`read_axis`) ou
    da rotina.
  - `do_action(nome)`, `toggle_sleep()` e `say(texto)` (balão de fala; `draw_speech` desenha por cima
    da luz e da chuva). Uma animação com `next: "hold"` fica parada no último quadro até alguém mudar o
    estado.
  - `toggle_sleep()` faz lie_down → sleep, e na volta wake → idle.
  - Andar cancela qualquer ação.
- `world.py`: céu em degradê e a **ilha flutuante** como chão: `world/ground/ground.png`, escalada
  para caber na tela e centralizada (`ground_pos`). A colisão com o chão vem de
  `world/ground/walkable.png` (branco = anda), virada `pygame.mask` e esticada sobre a ilha.
  - `walkable(rect)` exige que os pés estejam inteiros na área andável; `blocked(rect)` soma a isso os
    objetos sólidos.
  - `nearest_walkable` corrige o spawn.
  - Navegação (`build_nav`, chamado pelo Game depois de criar o personagem): grade de 16 px
    (`nav`/`nav_cells`), `find_path` (BFS em 8 direções, simplificado em retas com `clear_line`),
    `random_point` e `shore` (pontos andáveis com água do lago ao lado, detectada pela cor da ilha,
    com o lado da água).
  - `draw_debug` desenha o contorno da área andável (tecla P).
  - Há ainda `shade_at` e `draw_lights` para os objetos.
- `scene.py`: layout do mapa (`SCENE`: tipo e `pos` = **base** do objeto, em px de tela), `SPAWN` e
  `SPAWNS`. Hoje tem o banco (`items/town_bench_lit.png`) e o poste logo atrás (`items/cliffs_lamp.png`).
  O cenário está sendo refeito aos poucos. Os objetos provisórios antigos (casa, árvore, fogueira,
  bonecos) continuam em `props.py`, mas só voltam quando o usuário pedir.
- `decor.py`: **plantas animadas** espalhadas pela grama, usando a arte `world/gramas/gramas.png`.
  - Os desenhos são achados com `mask.get_bounding_rects` e agrupados em linhas; `SETS` mapeia
    `tipo -> (linha, início, fim)`.
  - **Os desenhos de uma linha são variações, não quadros de animação.** Tocados em sequência, a
    planta "treme". Por isso cada planta sorteia uma variação (às vezes espelhada), e o balanço é
    feito por cisalhamento: `sway_poses` gera `POSES` inclinações com a base fixa, guardadas em cache.
  - `lean()` combina a brisa (ritmo e fase por planta), o `wind` (chuva = mais forte) e o `rustle`
    (agitação quando o personagem passa andando por dentro).
  - `scatter()` sorteia posições andáveis com espaçamento e deixa o spawn livre.
  - Quantidades, escala, quais tipos são sólidos e a semente ficam em `scene.py` (`DECOR`,
    `DECOR_SCALE`, `DECOR_SOLID`, `DECOR_SEED`).
  - `world.drawables` (props + decor) entra na ordenação por y junto com o personagem.
- `props.py`: `Prop` (base, `footprint` sólido, `draw_ground`/`draw`/`draw_light`, `shade_at`) e os
  tipos:
  - `House`
  - `Tree`: sombra no chão que escurece o personagem; a copa fica transparente quando ele está atrás
  - `Campfire`: chamas animadas, faíscas e brilho aditivo
  - `Dummy`: balança como mola amortecida e pisca ao levar golpe
  - `Bench`: tem `seats` (dx), `occupied`, `seat_pos`, `approach` (onde parar antes de sentar, fora da
    área sólida) e `seat_height`.
  - `Lamp`: `lights` são as lâmpadas, em px da arte original relativos à base; acende com a
    escuridão e tem uma poça de luz no chão.
  - Opções genéricas de prop: `"file"` (arte em qualquer lugar de `assets/sprites/`) e
    `"base_offset"` (px da arte entre a borda de baixo e o ponto que toca o chão).
  - **A arte de cada objeto é provisória**, desenhada por código (o usuário escolheu assim por
    enquanto). `load_prop_frames` usa automaticamente `assets/sprites/world/<tipo>.png` ou a pasta
    `world/<tipo>/` (quadros) se existirem, com a base no centro de baixo da imagem. Ao receber arte,
    ajuste `scale`/`footprint` em `scene.py`.
- `environment.py`: **hora e clima reais**.
  - `WeatherService` roda numa thread daemon. Descobre a localização pelo IP (`ipinfo.io`); se falhar,
    usa `config.LOCATION_FALLBACK` (Manaus). Com `config.LOCATION`, a localização fica fixa.
  - O clima vem da Open-Meteo (sem chave): `weather_code`, precipitação, temperatura, nascer/pôr do
    sol e `utc_offset_seconds`. Atualiza a cada `WEATHER_REFRESH_MIN`; erro de rede só registra aviso
    e tenta de novo.
  - **A hora usada é a do fuso da localização** (UTC + offset da API), não a do relógio do PC. O PC do
    usuário está no horário de Brasília, uma hora à frente de Manaus. O relógio local é só reserva
    quando não há dados.
  - `Environment` gera a luz ambiente (cor multiplicada, interpolada entre noite, amanhecer, dia,
    tarde, entardecer e noite, usando o sunrise/sunset reais), o `darkness` (0..1, usado pelas luzes),
    a chuva (códigos WMO para intensidade, com gotas e respingos), relâmpagos em trovoada e o HUD no
    canto superior direito. Os presets das teclas T/R substituem os dados reais (o HUD mostra
    "manual").
- `window.py`: `PopupWindow`. O jogo desenha sempre em `Game.screen`, uma Surface interna de
  1280x720, e `present()` escala com `smoothscale`, mantendo a proporção (com tarja se precisar),
  para a janela RESIZABLE do tamanho que estiver.
  - Usa a API `pygame.Window` (pygame-ce): `always_on_top`, `borderless`, `opacity`, `position` e
    `size`. Cada mudança passa por `_try`, porque nem todo driver suporta.
  - A barra de botões (fixar, sem borda, transparência, −, +, fechar) é desenhada no espaço da janela.
  - Arrastar usa `mouse.get_pos(desktop=True)`.
  - `handle_event` roda antes dos eventos do jogo (retorna True se consumiu, "quit" para fechar).
  - O estado fica salvo em `window_state.json` (no .gitignore). O padrão é 640x360, fixado por cima.
  - Sem foco, o loop cai para 30 fps.
- `game.py`: eventos e teclas de teste.
  - Cria os moradores (`members`; `self.character` é o Knight, que o teclado controla), as rotinas e a
    `Society`.
  - Clique sem arrasto: `poke()` em quem estiver sob o cursor.
  - `separate()` afasta personagens colados (o Grub não é empurrado). Ordem de desenho: chão → objetos/personagem por y →
  `env.apply_light` → `world.draw_lights(darkness)` (as luzes ficam DEPOIS do escurecimento) →
  chuva → HUD → debug. `resolve_hit()` aplica o golpe do ataque
  (evento `hit_now` do personagem, gerado pelo `hit_frame` da animação) aos bonecos à frente.

## Assets

`assets/sprites/character/the_knight/` tem cerca de 70 pastas de animação, extraídas do jogo. Cada
quadro tem 349x186, a arte olha para a **esquerda** e o índice completo está em `Knight_aaaaa_info.txt`.

Mapeamento atual:

| Ação | Pastas |
|---|---|
| idle | `idle_still` |
| walk | `walk` |
| lie_down | `wake_up_ground` de 5 em diante, invertido |
| sleep | `wake_up_ground` até o quadro 4 (deitado) |
| wake | `wake_up_ground` de 5 em diante |
| eat | `collect_normal` (abaixar e pegar) |
| jump | `jump` + `fall` + `land` |
| attack | `slash_left_longer` (o golpe acerta no índice 7) |
| bench_sit | `sit` (de frente, pernas penduradas; `art_faces: None`) |

Candidatas para depois:
- `sit`, `sit_lean`, `sit_map_*`: sentar no banco
- `focus_v2`: curar
- `look_up` / `look_down`
- `idle_map` / `walk_map`
- `run`, `lantern_*`, `death_anim`, `hungry_knight_side`
- `_ effects`: bling, poeira etc.

Não há vista de frente nem de costas (o jogo é de plataforma).

### Hornet (`character/Hornet/`)

- É uma mistura de frames soltos (prefixo + número) com atlas compactados do jogo (sem ordem e com
  quadros girados).
- Movimentos (idle, walk, run, pulo) vêm de `Hornet main sprites - atlas2 #34870.png`, e o tocar
  (`needolin`) de `Hornet needolin - atlas0 #34857.png`. Os dois são extraídos por
  `tools/extract_atlas.py` (veja abaixo) para `frames/{idle,walk,run,jump_up,crouch,needolin}` com os
  pés no centro da imagem (`"pivot": "center"`).
- O resto usa frames soltos: `"files": prefixo` e `"pick"`.
- `align: "per_anim"`: cada sequência tem um tamanho de tela diferente. `sit`/`sew` (cena da tecelã)
  usam `"scale": 1.3`.
- **Lado da arte** (`art_faces` por animação): `idle`, `walk`, `needolin` e `look` olham para a
  DIREITA; `run`, `jump` e as outras, para a esquerda. Os chifres curvam para trás, então o lado é o
  dos olhos.

| Animação | Origem |
|---|---|
| idle, walk, run | atlas2 #34870 (`frames/idle`, `walk`, `run`) |
| jump | `crouch` → `jump_up` → `crouch` (pulo em arco pelo código, `hop`) |
| needolin | atlas0 #34857 (`frames/needolin`) |
| look | peak_needolin_look |
| eat | hornet_heart_grab_land |
| sit, sew, stand_up | weaver_hornet_* |
| lie_down, sleep, wake | summit_hornet |
| attack | Beast_Slash_Hornet |

- `bench_sit` (sentada no banco) usa `frames/bench_sit`, os quadros 17 e 18 do atlas "Hornet
  sitting", com `scale: 0.75` e `art_faces: None` (pose de frente).
- `tools/extract_atlas.py` extrai quadros de atlas compactados por índice: `EXTRACTS`, com a numeração
  nas faixas `band`. As opções da entrada:
  - `"unrotate"` desvira os quadros guardados deitados, detectados quando a cabeça branca fica à
    direita do vestido.
  - `"pivot"` salva em telas iguais com os pés no centro. `register` alinha cada quadro ao anterior
    pela maior sobreposição; `each` acha os pés de cada quadro.
  - As listas de índices já estão na ordem da animação. A ordem original se perde no atlas; ela foi
    achada por semelhança entre os quadros (a volta mais curta).
  - Gera as pastas da Hornet, `Hornet/frames/bench_sit` e `Shade/frames/idle`.
  - Ficaram de fora do atlas principal, entre outras: a pose de frente com a agulha na horizontal, o
    dash e os ataques. Também ficou de fora a variação do needolin com a cabeça para trás (mistura duas
    sequências).

### Sombra (`character/Shade/frames/idle`)

Os quadros 15, 16, 23, 24, 31 e 51 de `NPCs/atlas0 #10777.png`: a Sombra em pé, flutuando, olhando
para a esquerda. O sprite_def é `"shade"`.

### Grub (`character/Grup/`)

- `tools/slice_grub.py` recorta a folha do Spriters Resource: caixas brancas sobre fundo azul-petróleo,
  com o branco tirado por flood-fill da borda da caixa. Gera `frames/{idle,cry,turn,freed,home_*}`.
- A arte olha para a esquerda; `align: "per_anim"`.
- Uso: `happy` = freed 0–11; `lie_down` = freed 12–19 (se enterra); `sleep` = só a pontinha na terra;
  `wake` = brota.
- Os mesmos `lie_down`/`wake` servem para viajar (`burrow_to`).
- `home_*` não são usados (têm um degradê na base).

### Carregador (`assets._load_frame_folders`)

- Opções por animação: `dir` ou `files`, `start`/`end`, `reverse`, `pick`, e em `per_anim` também
  `foot`, `shift_x`, `scale` e `pivot` (`"center"` = pés no centro de cada imagem).
- `align: "union"` (o Knight) recorta tudo pelo mesmo retângulo.
- As outras pastas em `character/` (`NPCs`, `Tecela`, `charmander`, `froakie`) existem, mas não são usadas.

O usuário fornece a arte. Não gere sprites por código (ele achou feio) e não baixe arte. Os créditos
ficam em `CREDITS.md`. As pastas `character/charmander` e `character/froakie` são sobras da fase Pokémon
e não são usadas.

### Chão (`world/ground/`): `tools/make_ground.py`

- A fonte é `source/island_reference.png` (1672x941), fornecida pelo usuário: uma ilha isométrica com
  lago e barrancos. O xadrez de "transparência" está **desenhado** na imagem; o script o remove por
  flood-fill a partir das bordas (pixels claros e sem cor) e gera `ground.png` com alpha.
- `walkable.png` (418x235, 1 célula = 4 px) marca as células de grama: verde dominante e `g > b + 55`,
  o que exclui a água rasa verde-azulada. Depois o script fecha as falhas (flores e pedras), mantém só
  a maior região e deixa uma margem da borda.
- O usuário pode retocar `walkable.png` à mão. Rodar o script de novo sobrescreve os dois PNGs.
- Hoje os planaltos (degraus da ilha) são tratados como o mesmo nível: não há altura.

## Etapas

1. ✅ Tela + personagem controlado por WASD para testar sprites (com teclas para dormir, comer e pular).
2. ✅ Rotina: necessidades, passear, beber no lago, comer flores, dormir (cochilos de dia, noite
   longa), treinar, pular, olhar o céu e falas contextuais.
3. Comida (`items/`) e necessidades (fome, sono), com balão "zZ" em `ui/` ao dormir.
4. Cenário sendo refeito aos poucos: ✅ chão (ilha com lago), ✅ plantas animadas (gramas, flores,
   arbustos). Os objetos provisórios antigos (casa,
   árvore, fogueira, bonecos) foram tirados da cena.
   Pendente: arte de verdade para eles. Ideias: entrar na casa, sentar perto da fogueira
   (`sit`), um banco.
