"""Configurações globais do jogo."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT / "assets"
SPRITES_DIR = ASSETS_DIR / "sprites"

TITLE = "Living Habitat"

# Resolução INTERNA (pixels de jogo). A janela amplia isso por um fator
# inteiro (pygame.SCALED). O personagem é arte HD desenhada nessa resolução.
WIDTH = 1280
HEIGHT = 720

# Ampliação dos desenhos provisórios dos objetos (props.py), em pixel art.
WORLD_PIXEL = 2
FPS = 60

# Quem mora no habitat (chave de CHARACTER_SPRITES em sprite_defs.py)
CHARACTER = "knight"
# Moradores na cena (o 1º é CHARACTER, controlado pelo teclado; Tab troca quem é controlado).
# Opções: "knight", "daughter", "hollow", "hornet", "grub"
RESIDENTS = ("knight", "daughter")
# Tamanho dos personagens em relação à ilha (multiplica a "scale" de cada sprite_def, e
# também velocidade, sombra, altura do balão e distâncias). 0.6 = cabem na porta da casinha.
CHARACTER_SCALE = 0.6

# Estação do cenário: None = automático pelo mês (novembro e dezembro = "natal": ilha com
# neve, casinha enfeitada e lago congelado); ou fixe "natal" / "normal". Tecla V alterna.
SEASON = None
NATAL_MONTHS = (11, 12)
# A Sombra (aparição à noite/na chuva). Desligada enquanto trabalhamos só no Knight.
SHADE_ENABLED = False

# --- Clima e hora de verdade (environment.py) ---
# None = descobre a cidade pelo IP da internet. Para fixar: (lat, lon, "Nome").
LOCATION = None
# Usado se não der para descobrir pelo IP (sem internet etc.)
LOCATION_FALLBACK = (-3.119, -60.0217, "Manaus")
# De quantos em quantos minutos atualizar o clima
WEATHER_REFRESH_MIN = 10

# Começa com o overlay de debug ligado? (alternar com a tecla P)
DEBUG = False
