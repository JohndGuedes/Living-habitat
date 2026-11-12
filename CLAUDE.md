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

**Agora estão em cena o Knight e a Filha de Hallownest** (`config.RESIDENTS = ("knight", "daughter")`,
`SHADE_ENABLED = False`). Para trazer os outros de volta, inclua `"hornet"` e `"grub"` em `RESIDENTS`. Com
um morador só, `Society` fica `None`; sem a Sombra, `shade` fica `None`.

Moradores possíveis: **Knight** (controlável pelo teclado), **Filha de Hallownest** (`"daughter"`), **Hornet** e **Grub**. Cada um tem rotina própria
(`brain.py`) e eles se encontram e interagem (`social.py`). O Knight vive sozinho pela **rotina**. Usar o teclado assume o controle e a rotina volta
8 s depois da última tecla. Clicar nele sem arrastar faz ele responder (cutucão).

Teclas: WASD/setas para mover; **E** para a ação de contexto (veja `actions.py`); **Z** para
dormir/acordar, **Espaço** para pular e
**F** para atacar (teclas de teste dos sprites); **T** para alternar a hora (auto/dia/tarde/noite) e
**R** para alternar a chuva (auto/sim/não), para testar o ambiente; **P** para o overlay de debug, que
também mostra as áreas sólidas; Esc para sair.

Música (`audio.py`): **U** liga/desliga o mudo; **-** e **+** mudam o volume. Na barra da janela há um
botão de som: clicar põe no mudo, e a roda do mouse em cima dele muda o volume.

Teste de sprites (`Game.play_test`):
- **N**/**B**: toca a animação seguinte/anterior do Knight, com o nome no topo (`show`/`draw_flash`).
  Andar e correr ficam no lugar (`Character.pinned`) até uma tecla de movimento.
- **M**: liga e desliga a rotina. Desligada, ele fica parado esperando as teclas.
- **Tab**: troca quem o teclado e as teclas de teste controlam (`Game.switch_control`).
- **V**: estação (automática → natal → normal), via `Game.set_season`, que recria as áreas.
- **O**: editor de cenário (`editor.py`), detalhado abaixo.
- **C**: vai para a outra ilha na hora. Andar com o teclado até uma saída também faz a viagem.

Janela (popup para deixar num canto do monitor observando):
- **F2**: fixar por cima.
- **F3**: sem borda.
- **F4**: transparência (100/85/70/55%).
- **F11**: tela cheia.
- **Roda do mouse**: tamanho (em cima do botão de som: volume da música).
- **Arrastar com o botão esquerdo**: mover.

A barra de botões aparece ao passar o mouse.

Não há testes automatizados. Para checar sem abrir janela, use `SDL_VIDEODRIVER=dummy` (e
`SDL_AUDIODRIVER=dummy`, para a música não tocar de verdade), crie
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
  - Comer (`t_eat`; `_can_eat` diz se há comida): com **árvores de frutas** na área, ou fruta no
    chão, usa `t_eat_fruit`:
    - pega uma fruta caída (`world.fruits`, com `claimed` para dois não irem na mesma);
    - se não houver, vai ao lado do tronco, dá um golpe (`attack`) e chama `tree.hit` (a fruta cai);
    - espera a fruta aterrissar, vai até ela, faz `eat` (abaixar e pegar) e come: fome −0,6.

    Sem árvore, vai ao lado de uma flor ou arbusto pequeno (`_t_eat_plant`), `eat`, e a planta se
    agita.
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
    - `DaughterBrain`: falas próprias (`DAUGHTER_LINES`), calma e nostálgica. Colhe flores
      (`t_flowers`), lembra de casa (`t_remember`), dança (`t_dance`), observa o Knight de longe
      (`t_watch`), senta mais no banco e quase não treina.
    - `HollowBrain`: falas próprias (`HOLLOW_LINES`, silencioso e solene), sem fome nem sede; caminha
      pela ilha, vigia os outros moradores (`t_guard`), olha o céu e o lago, descansa no banco e
      interage com os elementos do cenário.
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
- **Áreas (ilhas)**: hoje só existe a ilha **lago**. A ilha da caverna foi removida a pedido do usuário,
  junto com os arquivos dela; o código de várias áreas, viagem e caverna continua pronto. As áreas ficam
  em `scene.AREAS`. O `Game` cria um `World` por
  área (`game.worlds`), e `game.world` é a que está na tela (`viewing`, a área do Knight).
  - Cada `Character` tem `area`. Só os personagens da área mostrada são desenhados, mas todos são
    atualizados no mundo deles.
  - Viagem: `Brain.go_area`/`enter_area` usa as saídas (`world.exits`: `at` e `arrive`). A troca de
    área tem um escurecimento (`game.fade`).
  - **lago**: ilha com a casinha, o lago e o banco. O poste saiu por enquanto. É onde todos começam
    (`START_AREA`).
  - **Estações** (`world.current_season`, `config.SEASON`/`NATAL_MONTHS`): `scene.AREAS[área]["seasons"]`
    troca chaves da área numa estação. Em novembro e dezembro, "lago" usa outro mapa inteiro, a área
    **natal** (`world/areas/natal/`, de `ground-natal.jpg`):
    - dois níveis (a praça e o platô de cima) ligados por escadas;
    - a casinha com o píer;
    - o lago congelado;
    - a **cachoeira** no alto.
    Sem `seasons`, uma área ainda pode usar `ground_<estação>.png` da mesma pasta.
  - **Pulos** (`world.jumps`, de `"jumps"` em `scene.py`): pares de pontos ligados por um pulo. No Natal, há
    um por cima da cachoeira:
    - `Brain.t_leap_falls` ("pular a cachoeira") anda até a ponta mais perto e faz `_hop` com o
      `double_jump` até a outra; às vezes volta;
    - **Espaço** perto de uma ponta faz o pulo com o personagem controlado;
    - o debug (P) mostra os pulos em rosa.
  - No Natal (área natal ou `ground_natal.png`) Nesse caso `world.frozen` é
    verdadeiro:
    - o andável vem de `walkable_frozen.png` (o gelo vira chão);
    - `water_mask` fica vazia (sem nadar), mas `lake_mask` continua valendo para as margens (beber
      "quebrando o gelo", fala `drink_ice`);
    - `t_skate` ("patinar") anda por pontos do gelo (`world.ice_point`);
    - as falas `xmas` entram no `context_chat`.
  - (removida) **caverna**: ilha com lago menor e a **caverna** no fundo (`props.Cave`, arte `cave.png`).
    Era o abrigo: à noite ele dorme lá dentro (`t_sleep`) e na chuva se abriga (`t_shelter`, 70% das
    escolhas com `env.rain` > 0,3).
  - Para entrar: `go_into_cave` anda até a `door` e desliza (`_glide`) até `inside` de costas
    (`walk_up`); sai de frente (`walk_down`). Dentro, `in_cave` desenha o personagem escurecido.
- `world.py`: um `World(width, height, area)` por ilha. Céu em degradê e a ilha
  (`world/areas/<área>/ground.png`), escalada para caber na tela (`k`, `ground_pos`). `top_room`
  reserva espaço acima, para a caverna.
  - Posições de `scene.py` vêm em px da imagem; `to_screen` converte. `_place` faz o mesmo nos props,
    com `scale` relativa à ilha.
  - Colisão: `walkable.png` (branco = anda) vira `pygame.mask` esticada sobre a ilha.
    `walkable(rect)` exige os pés inteiros na área andável; `blocked(rect)` soma os objetos sólidos.
  - Água: `water.png` (`_load_water`), usada por `swimmable`/`water_cells`/`clear_water` e por
    `shore` (margens).
  - Comida: `food_spots` (`FoodSpot`, das florzinhas brilhantes em `meta.json`), usados por `t_eat`
    junto com as plantas de `decor`.
  - Navegação (`build_nav`, chamado pelo Game depois de criar o personagem): grade de 16 px
    (`nav`/`nav_cells`), `find_path` (BFS em 8 direções, simplificado em retas com `clear_line`),
    `random_point` e `nav_point`. As saídas são ajustadas para a célula andável mais perto.
  - `draw_debug` (tecla P): contorno andável (ciano), lago (azul), saídas (círculo amarelo) e comida
    (pontos verdes).
  - Há ainda `shade_at` e `draw_lights` para os objetos.
- `actions.py`: **ações de contexto** do personagem controlado (tecla **E**).
  - `find_action` acha o que dá para fazer ali. Em ordem de prioridade:
    - sentado: "Levantar";
    - nadando: "Sair da água";
    - fruta no chão: "Pegar fruta";
    - árvore com frutas: "Bater na árvore" ("Árvore sem frutas" só avisa);
    - assento livre: "Sentar";
    - ponta de pulo: "Pular";
    - beira do lago com água: "Nadar".
  - `Prompt` desenha "[E] ação" em cima da cabeça enquanto o jogador está no controle (`manual` > 0,
    rotina desligada ou `brain.player_task`).
  - `do_action` vira uma tarefa `Brain.t_player(...)`: no fim, o controle volta ao jogador (`manual` =
    `MANUAL_PAUSE`). As tarefas são `t_hit_tree`, `t_pick_fruit`, `t_sit_here` (fica sentado até
    `stand_request` ou andar), `t_enter_water`/`t_exit_water` (na água anda-se com WASD; se a rotina
    voltar com ele na água, `t_leave_water` o tira) e `t_leap_falls`.
  - Sem ação por perto, E toca a animação de comer (teste de sprite).
- `editor.py`: `Editor`, o editor de cenário (tecla **O**). Com ele ligado, os personagens ficam
  parados (sem rotina nem encontros) e o editor recebe os eventos antes da janela
  (`window.to_canvas` converte o mouse).
  - Comandos:
    - **L**: abre a biblioteca, com as miniaturas de `assets/sprites/world/library/<conjunto>/*.png`.
      Clicar coloca o item no meio da tela; a roda rola a lista.
    - Arrastar move o objeto; roda ou +/− mudam o tamanho; setas fazem ajuste fino (Shift = 10x).
    - Tab passa para o próximo objeto.
    - Delete remove o objeto selecionado.
    - K alterna sólido/atravessável.
    - Backspace volta o objeto ao valor de `scene.py` (só os que estão lá).
    - Ctrl+S ou Enter salvam; O ou Esc saem.
  - Itens da biblioteca viram `props.Item` (`kind: "item"`, `file`, `name`), com `ITEM_SCALE` inicial.
    São sólidos por padrão: uma faixa na base com metade da largura da arte. Os que têm nome começando
    com "banco" viram `Bench`, com `seats_rel`/`approach_rel` (frações da arte, que acompanham o
    tamanho).
  - Cada mudança altera `world.prop_defs` e recria o objeto (`make_prop`). Ao sair, a navegação é
    refeita, por causa das colisões.
  - **`layout.json`** (na raiz, versionado) é o padrão salvo: a lista COMPLETA de objetos de cada área,
    por estação (`"lago@natal"`, `"lago@normal"`). Assim a decoração de Natal fica só no Natal.
    `world.load_layout` usa a chave da estação; se ela não existir, usa a da área; se nenhuma existir,
    usa `scene.py`.
- `scene.py`: `AREAS`. Para cada área:
  - `folder`;
  - `props` (`img_pos` = **base** do objeto em px da imagem);
  - `spawn`/`spawns`;
  - `exits`;
  - `top_room`.

  Também ficam lá `START_AREA` e `DECOR` por área (hoje vazio: as ilhas novas já têm plantas e
  `gramas.png` é bem mais clara). Os objetos provisórios antigos (casa, árvore, fogueira, bonecos)
  continuam em `props.py`, mas só voltam quando o usuário pedir.
- `effects.py`: efeitos animados do cenário (`"effects"` em `scene.py`, criados por `make_effect`).
  `world.draw` os desenha logo depois do chão, então objetos e personagens passam na frente; à noite
  escurecem junto com a luz. Há dois tipos: `PlantSway` (abaixo) e `Waterfall`, a água da cachoeira
  do mapa de Natal, em três partes:
  - a cascata de cima, com respingos;
  - o riacho na diagonal (`dir`);
  - a queda principal, com respingos e névoa (`mist`).

  Como funciona:
  - a camada de água é a própria arte (pixels claros e azulados do `rect`) deslocada sem parar na
    direção do fluxo, em 4 cópias que se emendam, e misturada por cima (`FLOW_ALPHA`), com as bordas
    esmaecidas;
  - riscos de luz (`STREAKS`) escorrem mais rápido;
  - no `splash` saem gotinhas com gravidade e baforadas de névoa;
  - custa cerca de 1 ms por quadro.

  `PlantSway` (`"kind": "sway"`): as **plantas pintadas no chão** (samambaias, capim de gelo,
  florzinhas) balançam bem de leve.
  - `"plants"`: caixas `(x0, y0, x1, y1)` em px da imagem do chão, marcadas à mão nos dois mapas. O
    `y1` é a base (fica parada). As caixas estão em `scene.py`: o `lago` normal tem 17 e o Natal tem 23.
  - Cada caixa vira um recorte da própria arte, inclinado em `POSES` posições com fração de pixel
    (`decor.soft_sway_poses`: amplia sem suavizar, cisalha e reduz com suavização, então a pose parada
    é idêntica ao chão). Uma margem `PAD` em volta é esmaecida, para não ter emenda.
  - Cada planta tem ritmo próprio (`decor.breeze`); a chuva (`world.wind`) balança mais, e um
    personagem andando por dentro (`world.actors`) agita a planta.
  - Uma planta nova no mapa precisa da caixa dela em `scene.py`.
- `lighting.py`: **iluminação, sombras e reflexos**.
  - **Luzes** (`SceneLights`, de `"lighting"` em `scene.py`, criadas pelo `World` e desenhadas em
    `world.draw_lights`, depois do escurecimento, com luz aditiva). São fortes à noite e fracas de dia:
    - todos os brilhos são **difusos**: `_glow` usa queda gaussiana calculada pequena e ampliada com
      suavização (sem anéis). O usuário não quer luz "circular marcada";
    - `warm`: luz quente com tremulação. Com `pos`/`radius`, é um brilho difuso (lanternas do píer,
      estrela). Com `kind: "opening"` + `rect` + `spill` (dx, dy, comprimento, abertura) + `edge` (direção da base da parede: a ilha é isométrica,
      então a soleira é diagonal e a luz sai perpendicular a ela), é luz vindo
      **de dentro** por uma abertura (`_opening_light`, no Natal a porta e a janela): a abertura
      inteira brilha, há um halo suave em volta e um leque de luz no chão à frente, que esmaece e é
      desfocado (`_blur`);
    - `strings`: fios de pisca-pisca que seguem os desenhados na arte, com uma lâmpada a cada
      `BULB_GAP` px, cores alternadas (`BULB_COLORS`) e piscando cada uma no seu ritmo. Foram marcados
      à mão, porque as lâmpadas da arte são pequenas demais para achar sozinho;
    - `sheen`: uma faixa de brilho deslizando sobre o lago (recortada por `world.lake_surface`).
  - **Sombras do sol**: `Environment.sun()` dá (lado, comprimento, força). Sem sol à noite; mais
    fracas com chuva. `Game.draw_shadows_and_reflections` desenha, no chão, a silhueta de objetos e
    personagens (`Character.pose`, `SpriteSheet.frame_image`) achatada e cisalhada por
    `cast_shadow` (com cache). De manhã a sombra vai para a esquerda e no fim da tarde para a direita,
    e fica comprida perto do nascer e do pôr do sol. Quem pula tem a sombra mais fraca.
  - **Reflexos**: quem está sobre o lago (`world.on_lake`) aparece de cabeça para baixo debaixo dos
    pés (`reflect`), levemente azulado, recortado pela forma do lago. O reflexo se afasta quando o
    personagem pula.
- `fairies.py`: **fadinhas**, personagens de fundo. A arte é `world/fairies/fadinhas.png`: 8 quadros
  batendo as asas, em células com moldura azul. Por dentro a folha já é transparente, com a fadinha
  branca e o halo em alpha; é preciso carregar com `convert_alpha`, porque com `convert` vira um disco
  branco. `_load_frames` recorta as células.
  - Pequenas (`scale` 0,3 em `scene.py`). Grupinhos (`Swarm`) de 3 a 6 fadinhas (`Fairy`), cada uma
    com posição e velocidade próprias, puxada por uma mola até o seu lugar no grupo.
  - Passam a maior parte do tempo paradas: `rest` por `REST` (20–60 s), em 75% das vezes sentadas num
    objeto (`_perches`: copa das árvores, encosto do banco, em cima das lanternas dos itens, cabeça do
    Zote, topo de outros itens), cada uma num cantinho dele, com as asas mais lentas
    (`REST_FRAME_TIME`); senão pairando no ar. Depois voam (`fly`) devagar para outro lugar, por cima de
    tudo (não usam a navegação).
  - Alguém a menos de `SCARE` px faz a fadinha **debandar** (impulso para longe por `SCATTER` s); depois
    ela volta e o grupo se reúne.
  - **Curiosa**: `Fairies.still` conta quanto tempo cada personagem está parado. Depois de
    `CURIOUS_AFTER` s, com um grupo a menos de `CURIOUS_RANGE` px, às vezes uma fadinha vai rodear a
    cabeça dele (`visit`) por 5–10 s; se ele se mexer, ela foge e volta para o grupo.
  - `Fairies` (de `"fairies"` em `scene.py`: `swarms`, `size`, `scale`) é criado pelo `World`.
    `Game` desenha as fadinhas depois de todos os objetos (voam por cima) e antes da luz.
    `world.draw_lights` → `draw_light` acrescenta um brilho azulado, quase nada de dia e mais forte à
    noite (com cache por força).
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
  - `Campfire` (`kind: "campfire"`): **fogueira interativa** recortada de `world/natal/fogueira.png` por
    **`tools/make_campfire.py`** para `world/campfire/` (`unlit_snow`, `extinguished`, `kindling`,
    `fire_0..4`, mais `flame`, `smoke_0..2` e `spark_0..3`), com miniatura `library/natal/fogueira.png` (e
    itens extras `lenha_neve.png` e `espeto_fogueira.png`).
    - Acesa (`lit = True`): anima `fire_0..3` em loop, solta fagulhas (`spark_*`), línguas de fogo (`flame`)
      e fumaça (`smoke_*`), e ilumina o redor com brilho difuso quente que oscila como fogo real.
    - Apagada (`lit = False`): ao apagar (`extinguish`) passa por `fire_4`, solta fumaça e fica em
      `extinguished` (no Natal, depois de um tempo apagada, acumula neve `unlit_snow`); ao acender
      (`light_up`) passa por `kindling` derretendo a neve das pedras.
    - Perto dela, a tecla **E** mostra **"Apagar fogueira"** ou **"Acender fogueira"**
      (`Brain.t_toggle_campfire`), e na rotina (`Brain.t_campfire`) os moradores vão acendê-la e se aquecer.
  - `Dummy`: balança como mola amortecida e pisca ao levar golpe
  - `Bench`: tem `seats` (dx), `occupied`, `seat_pos`, `approach` (onde parar antes de sentar, fora da
    área sólida) e `seat_height`.
  - `ZoteDummy` (`kind: "zote"`): o **boneco de treino** (o Zote). É colocado pelo editor; na
    biblioteca é `boneco_zote`. Usa a arte de `world/zote/`.
    - Cada `hit`:
      - pisca branco;
      - toca `hit_0..4`;
      - solta lascas, madeira e neve com gravidade (quicam no chão);
      - mostra uma faísca no impacto e às vezes um balão de emoção.
    - Tem `MAX_HP` (10) de vida: com 6 ou menos fica rasgado (`damaged`); com 3 ou menos, com a base
      quebrada (`nobase`).
    - Na vida zero, quebra (`_break`): a cabeça voa e fica no chão, o corpo sem cabeça tomba e some,
      sobra a `base`.
    - Depois de `RESPAWN` s, sobe uma fumaça e ele volta inteiro, resmungando.
    - Só o poste é sólido. A rotina treina nele (`t_train` → `t_train_dummy`, 75% das vezes quando
      existe); **E** perto dele: "Treinar"; **F** também bate.
  - `FruitTree` (`kind: "fruit_tree"`): a comida. É colocada pelo editor; na biblioteca é
    `arvore_frutas`, com `scale` inicial 1,2. Usa as poses de `world/fruit_tree/`. Um `hit`:
    - pisca branca (`FLASH`) e treme;
    - toca `hit_0..3` (neve e folhas voando), com partículas de folhas;
    - derruba uma `Fruit`, que cai quicando até um ponto andável perto do tronco e entra em
      `world.fruits` (desenhada por y, com sombrinha; some em 10 min se ninguém pegar).
    Com `fruits` (padrão 4) zerado, mostra `empty` e rebrota em `REGROW` s. Só o tronco é sólido.
    **Árvore de imagem única** (`single`, ex.: `pinheiro_enfeitado`, que não tem poses desenhadas): o
    balanço é feito pelo código com `decor.sway_poses` (a copa inclina com a base parada, numa
    oscilação que vai parando por `SINGLE_TIME`). `make_prop` transforma em árvore de frutas os itens
    cujo nome começa com `FRUIT_TREE_NAMES` (`arvore_frutas`, `pinheiro`), inclusive os já salvos no
    `layout.json`.
    O `World` liga `prop.world`. **F** perto da árvore bate nela (`resolve_hit`); **E** perto de uma
    fruta no chão pega e come.
  - `Lamp`: `lights` são as lâmpadas, em px da arte original relativos à base; acende com a
    escuridão e tem uma poça de luz no chão.
  - **Brisa** (`Breeze`): os itens com nome começando em `PLANT_NAMES` (arbusto, capim, planta,
    folhas) e todas as `FruitTree` (pinheiros e árvore de frutas, parados entre os golpes) balançam bem
    de leve. O topo vai e volta 1–3 px e a base fica parada. As poses vêm de `decor.soft_sway_poses` e
    ficam em cache por arte e escala; a chuva balança mais. A sombra do sol usa `shadow_image()`, a
    imagem sem balanço, para não encher o cache de sombras.
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
    a chuva (códigos WMO para intensidade, com gotas e respingos), relâmpagos em trovoada e o
    **indicador celeste de horário** (`draw_hud`) no topo-centro da tela: um arco sutil onde o Sol (de
    dia, mudando gradativamente de cor e brilho do amanhecer ao pôr do sol) ou a Lua (à noite, com
    estrelinhas e a **fase astronômica real do dia** calculada em `moon_phase`/`_moon_disc`) percorrem
    o ciclo conforme o minuto atual, sem texto de cidade, temperatura ou relógio numérico.
- `window.py`: `PopupWindow`. O jogo desenha sempre em `Game.screen`, uma Surface interna de
  1280x720, e `present()` escala com `smoothscale`, mantendo a proporção (com tarja se precisar),
  para a janela RESIZABLE do tamanho que estiver.
  - Usa a API `pygame.Window` (pygame-ce): `always_on_top`, `borderless`, `opacity`, `position` e
    `size`. Cada mudança passa por `_try`, porque nem todo driver suporta.
  - A barra de botões (fixar, sem borda, transparência, −, +, som, fechar) é desenhada no espaço da
    janela. O botão de som usa `window.music` (o `Game` liga).
  - Arrastar usa `mouse.get_pos(desktop=True)`.
  - `handle_event` roda antes dos eventos do jogo (retorna True se consumiu, "quit" para fechar).
  - O estado fica salvo em `window_state.json` (no .gitignore). O padrão é 640x360, fixado por cima.
  - Sem foco, o loop cai para 30 fps.
- `audio.py`: **trilha sonora** (`Music`).
  - Toca em loop a primeira música de `assets/music/` (.opus, .ogg, .mp3, .wav ou .flac), entrando
    devagar (`FADE_IN_MS`).
  - Volume e mudo ficam em `window_state.json` (`music_volume`, `music_muted`).
  - O pygame não abre .weba/.webm. Se só houver um desses, `audio` converte numa thread
    (`webm_opus.convert`, via `.opus.part`) e começa a tocar quando termina. A conversão só troca o
    contêiner (os pacotes Opus vão do WebM para páginas Ogg), sem recodificar e sem ffmpeg. O
    `tools/convert_music.py` faz o mesmo à mão.
  - A música atual é `hollow-background-music` (65,8 min), fornecida pelo usuário. Os dois arquivos
    (.weba e .opus) têm cerca de 70 MB.
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

Mapeamento atual (o usuário definiu quais pastas são o quê):

| Animação | Pastas | Uso na rotina |
|---|---|---|
| idle | `idle_still` | parado |
| walk | `walk` | andar de lado |
| walk_up / walk_down | `into_door` (do 2 em diante) / `tram_leave` | andando de costas / de frente (`dir` "up"/"down") |
| tired | `idle_low_health` | parado com energia < 0,3 |
| lantern_idle / lantern_walk | `lantern_idle` / `lantern_run` (`"glow": True`) | à noite (`env.darkness` > 0,45) |
| walk_map, walk_map_turn | `walk_map`, `walk_map_turn` | às vezes passeia lendo o mapa |
| lie_down / sleep / wake | `wake_up_ground` | dormir |
| eat | `collect_normal` | comer e beber |
| cast | `cast` | "sentir o vento" (mais na chuva) |
| jump / double_jump | `jump`+`fall`+`land` / `jump`+`double_jump_v2`+`fall`+`land` | pular (35% duplo) |
| look_up / look_down | `look_up` / `look_down` | céu / lago |
| sit_down → bench_sit → bench_leave | `sit` 0–1 sentando, quadro 1 sentado, 2–4 descendo | banco |
| map_look / map_write | `sit_map_look` / `sit_map_write` | lendo o mapa sentado no banco |
| attack | `slash_left_longer` | treinar |
| attack1 | `charge_slash` + efeito `_ effects/charge_slash_effect` | treinar |
| attack2 | `cyclone_slash` + efeito `_ effects/cyclone_slash_effect` | treinar |
| special | `nail_slash` (o brilho já vem nos quadros) | fim do treino, às vezes |
| swim_enter / swim_idle / swim | `water_enter_to_idle` (tela 225x336, `"offset"`) / `water_surface_idle` / `water_surface_swim` | nadar no lago |

As variações (cansado, lanterna, de costas/de frente, mapa, nadar) não mudam o `state`:
`Character.anim_name()` escolhe a animação pelo `state` ("idle"/"walk") e pelas flags `tired`,
`lantern`, `walk_variant` e `swimming`, que a rotina liga.

Detalhes:
- **Efeitos dos golpes**: `"effect"` na animação (`assets._attach_effect`) com `dir`, `start`
  (quadro do corpo), `scale`, `flip` e `at` (centro do efeito em relação aos pés, em px da arte).
  As posições foram ajustadas por captura de tela.
- **Lanterna**: `"glow"` acha a luz em cada quadro (`sheet.glow`). `Character.draw_light` soma um
  brilho nela e uma poça de luz no chão à frente, depois do escurecimento.
- **Nadar**: `World._build_water` faz a máscara do lago pela cor da ilha (`swimmable`,
  `water_cells`, `water_point`, `clear_water`; o contorno aparece no debug com P). `Brain.t_swim`
  escolhe uma margem com água funda ao lado (`_swim_spots`), pula para dentro (`_hop`), nada
  (`_swim_to`) e volta. Na água, `_draw_water_cover` cobre as pernas com os pixels do próprio lago.

Não há vista de frente nem de costas (o jogo é de plataforma).

### Filha de Hallownest (`character/daughter_of_hollownest/`): `tools/make_skin.py`

É uma **skin** do Knight: `Knight.png` tem a disposição exata do atlas original
(`the_knight/Knight_full_0.png`), com a arte trocada. O sprite_def `"daughter"` é o do Knight com outro
`frames_root` (`daughter_of_hollownest/frames/`), então novas animações do Knight valem para ela.
- O script acha cada quadro do Knight no atlas original (8 orientações; procura uma tira de pixels nos
  bytes do atlas e confere as cores), recorta o mesmo lugar da skin e salva com o mesmo nome de pasta.
- O atlas tem desenhos duplicados: prefere a cópia pintada.
- `replace_unpainted`: quadros que o autor da skin deixou quase sem pintar (similaridade > 0,6 com o Knight:
  `walk` 0, `walk_map` 0–1, `slash_left_longer` 1, `sit` 4) repetem o vizinho.
- `fill_gaps`: quadro sem par repete o vizinho (`collect_normal` 12, `double_jump_v2` 1, `death_anim` 5).
- Efeitos semitransparentes sem par (`_ effects`) usam o original do Knight (são brilhos brancos). A pasta
  `_ unnamed` não é gerada.
- Os outros PNGs da pasta (`Hornet`, `Quirrel`, `Hatchling`, `Unn`, `voidSpells`, `wraiths`, `Wings` etc.) são
  de outros personagens ou efeitos da mesma skin e não são usados.

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

### Hollow (`character/hollow/`): `tools/make_hollow.py`

- `tools/make_hollow.py` recorta os 19 quadros de `character/hollow/walk.png` (removendo o fundo cinza
  por flood-fill e frestas entre as pernas) e centraliza cada quadro numa tela uniforme de 120x186 pelo
  eixo da cabeça (`ANCHOR_X = 60`, pés em `ANCHOR_Y = 183`), gerando `frames/{idle,walk,walk_down,walk_up,walk_up_side,walk_left}`.
- `Character.anim_name()` usa `walk_down` (frente), `walk` (lados, espelhado na esquerda), `walk_up_side`
  (diagonais para cima mostrando o manto e o ferrão nas costas) e `walk_up` (costas).

### Carregador (`assets._load_frame_folders`)

- Opções por animação: `dir` ou `files`, `start`/`end`, `reverse`, `pick`, e em `per_anim` também
  `foot`, `shift_x`, `scale` e `pivot` (`"center"` = pés no centro de cada imagem).
- `align: "union"` (o Knight) recorta tudo pelo mesmo retângulo. Uma pasta com tela de outro
  tamanho usa `"offset": (dx, dy)` para se encaixar. Também há `"glow"` e `"effect"` (veja acima).
- As outras pastas em `character/` (`NPCs`, `Tecela`, `charmander`, `froakie`) existem, mas não são usadas.

O usuário fornece a arte. Não gere sprites por código (ele achou feio) e não baixe arte. Os créditos
ficam em `CREDITS.md`. As pastas `character/charmander` e `character/froakie` são sobras da fase Pokémon
e não são usadas.

### Biblioteca de itens (`world/library/<conjunto>/`): `tools/slice_sheet.py`

- O script recorta folhas de itens com fundo liso (`SHEETS`: folha → conjunto). A primeira é
  `world/natal/assets terreno natal.png`, fornecida pelo usuário, que vira `library/natal/`.
- Passos:
  - tira o fundo (a cor do canto) por flood-fill a partir das bordas, com tolerância `EDGE_TOL`,
    e também nos buracos fechados, com `HOLE_TOL`;
  - junta os pedaços que se tocam depois de "engordados" `JOIN/2` px (a lanterna e o poste, os
    presentes, o pisca-pisca);
  - salva cada item recortado justo, com os nomes de `NAMES`.
- Os 19 itens de Natal: postes (com e sem guirlanda, curvo), pilares com lanterna, estátua com lanterna,
  pedras com neve (vários), plantas com neve, presentes, pisca-pisca, guirlandas e `banco_neve`.
- Qualquer PNG colocado à mão numa pasta de `library/` também aparece no editor.
- `world/natal/boneco-zote.png` (fornecida pelo usuário): **`tools/make_zote.py`** recorta as poses e as
  alinha pela base (parado, golpe, `damaged`, `nobase`, `headless`), mais as peças soltas (cabeça,
  base, lascas, neve, faíscas, fumaça, balões). Também gera a miniatura
  `library/natal/boneco_zote.png`.
- **Boneco de neve** (`props.Snowman`, `kind: "snowman"`): dois modelos (`knight` e `hornet`), recortados de
  `world/natal/bonecos-neve.png` por **`tools/make_snowmen.py`** para `world/snowman_knight/` e
  `world/snowman_hornet/`, com miniaturas `library/natal/boneco_neve_knight.png` e
  `library/natal/boneco_neve_hornet.png`.
  - Poses alinhadas pela base: `build_0..2` (etapas de montagem), `idle_0..2` (cachecol/manto ao vento),
    `hit_0..1` (rachado / desmoronando) e `destroyed` (pilha de neve no chão), mais `piece_0..7` (bolas
    de neve, flocos, galhos e cachecol/manto).
  - Bater (`hit`, tecla **F** ou **E** "Quebrar boneco" -> `Brain.t_break_snowman`) tira vida (`MAX_HP = 4`),
    solta neve/galhos, racha na metade da vida (`hit_0`) e desmonta (`hit_1` -> `destroyed`).
  - Desmontado (`stage < 4`), **E** mostra "Montar boneco" (`Brain.t_build_snowman`), onde o personagem se
    abaixa repetidamente (`eat`) chamando `build_step()` para avançar `destroyed -> build_0 -> build_1 ->
    build_2 -> idle_0..2` até ficar pronto de novo. A rotina (`Brain.t_snowman`) também monta os bonecos
    desmontados ou brinca de desmontar e remontar.
- **Grub de Natal** (`props.GrubNatal`, `kind: "grub_natal"`): recortado de `world/natal/group-natal.png` por
  **`tools/make_grub_natal.py`** para `world/grub_natal/` (`jar_0..5`, `hit_0..2`, `shatter_0..2`,
  `free_0..2`, `burrow_0..2`, `broken_jar`, `lid`, `piece_0..6`), com miniatura `library/natal/grub_natal.png`.
  - No pote (`state == "jar"`): **E** "Libertar Grub" (`Brain.t_free_grub_natal`) ou **F** dá 3 golpes que
    racham o pote (`hit_0..2`) até quebrar em cacos (`shatter_0..2`) com a tampa (`lid`) voando.
  - Livre (`state == "free"`): pula de alegria com gorro de Natal (`free_0..2`); **E** "Brincar com o Grub"
    (`Brain.t_play_grub_natal`) faz ele mergulhar na neve (`burrow_0..2`).
  - No montinho de neve (`state == "snow"`): fica só com o gorro e estrelinhas de fora (`burrow_2`); **E**
    "Chamar o Grub" faz ele brotar de novo e reiniciar o ciclo. A rotina (`Brain.t_grub_natal`) também
    interage com ele sozinha.
- `menu.py`: `Menu`, tela de título transparente sobre o habitat vivo ao abrir o jogo (`"title"`) e painel
  central de configurações (`"settings"`, tecla **Esc** ou botão `☰` na barra superior). Permite ajustar
  modo de exibição, tamanho, opacidade, áudio, estação, hora do dia, clima e rotina da IA.
- **Golpes**: `Game.resolve_hit(ch)` vale para qualquer personagem, no quadro do golpe (`hit_now`).
  Acerta o que tem `hit` e está logo à frente (alcance = 26 + 35% da largura do objeto).
- `world/natal/arvores.png` (fornecida pelo usuário) vira `library/natal_2/`: muro e pedras com neve,
  arbustos, capim, montes e o pinheiro enfeitado. Os pedaços com nome `None` em `NAMES` ficam de fora.
  A árvore de frutas e as cerejas são recortadas por **`tools/make_fruit_tree.py`**:
  - as poses `full`, `hit_0..3` e `empty` são alinhadas pela base do tronco (maior sobreposição da
    parte de baixo) numa tela comum;
  - saem também `fruit_0..5` e a miniatura `library/natal_2/arvore_frutas.png`.

  Rode o `make_fruit_tree` depois do `slice_sheet`, porque o `slice_sheet` limpa os PNGs da pasta do
  conjunto.
- **Luzes dos itens**: `library/<conjunto>/lights.json` diz onde ficam as luzes de cada item, em px
  da imagem do item:
  - `"nome": [[x, y]]`: lanternas (no Natal: os postes, os pilares, o poste curvo e a estátua).
    `Item.draw_light` desenha um brilho difuso no vidro e uma pocinha no chão;
  - `"bulbs": {"nome": [[x, y], ...]}`: lâmpadas de pisca-pisca, coloridas e piscando (o
    `pisca_pisca`).

  As luzes acompanham a posição e o tamanho do item. Os brilhos ficam em cache por força
  (`Item._glows`), para não pesar. Um item novo com lanterna precisa da entrada dele nesse arquivo.

### Ilhas (`world/areas/<área>/`): `tools/make_areas.py`

- A ilha atual (`lago`) foi fornecida pelo usuário em duas versões alinhadas pixel a pixel (1024x572,
  estilo Hollow Knight, com uma casinha no canto de cima):
  - `source/ground.png`: a normal, com fundo preto;
  - `source/Natal.jpg` (2752x1536, mesma proporção e posição, em alta resolução): neve, enfeites e lago
    congelado, com fundo azul-escuro e estrelas.
- O script (`AREAS` no topo, em px da imagem) gera, a partir da versão normal:
  - `ground.png` (fundo removido por flood-fill de pixels escuros a partir das bordas);
  - `walkable.png`: grama verde-azulada ou trilha de pedra cinza; fechamento, maior região, margem.
    `block` tira retângulos com cor de grama que não são chão (o telhado musgoso da casinha);
  - `water.png`: o lago a partir de um ponto `lake`, porque as paredes dos barrancos têm cor
    parecida. A água tem bem mais azul que verde. Os buracos pequenos são preenchidos;
  - `walkable_frozen.png`: andável + o lago, ligado à margem (para o Natal);
  - `meta.json`: as florzinhas brilhantes, que viram comida.
- `variants` (`natal`): `ground_natal.png`, na resolução da própria imagem, recortado pelo contorno da ilha
  normal (3 px de folga para a neve, suavizado). O fundo com estrelas não é escuro o bastante para o
  flood-fill. O `World` estica a variante para o mesmo tamanho da normal; as posições continuam em px de
  `ground.png`.
- O suporte a caverna (`erase`, `island_top`, `cave`/`cut_cave`) continua no script, sem uso.
- **Área natal** (`ground-natal.jpg`, 2752x1536). Opções da entrada em `AREAS`:
  - `cell` 8 e `margin` 1: as escadas são estreitas;
  - `bg: "corner"`: o fundo é azul-escuro com estrelas;
  - `ground: "snow"` (`is_snow`): a média clara vira chão, e paredões e rochas escuros não;
  - `lake_test: "ice"`: o gelo é azulado e um pouco mais escuro que a neve;
  - `frozen`;
  - `block`: a cachoeira, branca como a neve;
  - `allow`: a escada da direita, que uma coluna de pedra cortava;
  - `food`: as plantinhas, marcadas à mão, porque a neve é clara demais;
  - `clear_dark`: o halo desenhado em volta da estrela da árvore virava um disco no céu. Nesse círculo,
    só ficam a estrela e o triângulo da árvore; o jogo põe o brilho.

  A praça, o platô, as duas escadas e as duas beiras da cachoeira formam uma região só da navegação
  (conferido).
- `walkable.png`/`water.png` (1 célula = 4 px) podem ser retocados à mão. Rodar o script de novo
  sobrescreve tudo. Com uma pasta como argumento, salva prévias com as áreas pintadas.
- As ilhas antigas (`world/ground`, `island.png`, a ilha da caverna) foram substituídas e removidas;
  estão no histórico do git.
- As posições em `scene.py` são em px de `ground.png` (1024x572). O banco tem `scale` 0,5 relativa à
  ilha, `seats` ±24 e `approach_dy` 22, para o tamanho novo dos personagens.
- **Tamanho dos personagens**: `config.CHARACTER_SCALE` (0,6, para caberem na porta da casinha)
  multiplica:
  - a `scale` dos sprite_defs (em `load_sprite_set`);
  - a velocidade, a sombra, o `seat_drop`, os pés (`feet_rect`) e a altura dos pulos (`hop`);
  - a altura do balão e a `WATERLINE`;
  - as distâncias de corpo: comer ao lado da planta, `separate` e os pontos dos encontros.
- Hoje os planaltos (degraus da ilha) são tratados como o mesmo nível: não há altura.

## Etapas

1. ✅ Tela + personagem controlado por WASD para testar sprites (com teclas para dormir, comer e pular).
2. ✅ Rotina: necessidades, passear, beber no lago, comer flores, dormir (cochilos de dia, noite
   longa), treinar, pular, olhar o céu e falas contextuais.
3. Comida (`items/`) e necessidades (fome, sono), com balão "zZ" em `ui/` ao dormir.
4. Cenário sendo refeito aos poucos: ✅ duas ilhas (lago; caverna com abrigo) com viagem entre elas,
   ✅ plantas animadas (gramas, flores, arbustos; desligadas nas ilhas novas). Os objetos provisórios antigos (casa,
   árvore, fogueira, bonecos) foram tirados da cena.
   Pendente: arte de verdade para eles. Ideias: entrar na casa, sentar perto da fogueira
   (`sit`), um banco.
