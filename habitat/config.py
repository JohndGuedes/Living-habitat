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

# --- Clima e hora de verdade (environment.py) ---
# None = descobre a cidade pelo IP da internet. Para fixar: (lat, lon, "Nome").
LOCATION = None
# Usado se não der para descobrir pelo IP (sem internet etc.)
LOCATION_FALLBACK = (-3.119, -60.0217, "Manaus")
# De quantos em quantos minutos atualizar o clima
WEATHER_REFRESH_MIN = 10

# Começa com o overlay de debug ligado? (alternar com a tecla P)
DEBUG = False
