"""Trilha sonora (assets/music/).

Toca em loop a primeira música da pasta (.opus, .ogg, .mp3, .wav ou .flac), entrando
devagar. Se só houver .weba/.webm (o pygame não abre), converte para .opus numa thread na
primeira vez (webm_opus.py; só troca o contêiner) e começa a tocar quando terminar.

Controles (game.py / window.py): U = mudo, - e + = volume, botão de som na barra da janela
(clique = mudo; roda do mouse em cima = volume). Volume e mudo ficam em window_state.json.

Testes sem som: SDL_AUDIODRIVER=dummy (o mixer funciona, mas não sai nada).
"""
import logging
import threading

import pygame

from .config import ROOT

log = logging.getLogger(__name__)

MUSIC_DIR = ROOT / "assets" / "music"
PLAYABLE = (".opus", ".ogg", ".mp3", ".wav", ".flac")
CONVERTIBLE = (".weba", ".webm")
FADE_IN_MS = 4000
STEP = 0.1                     # quanto cada tecla muda o volume


class Music:
    def __init__(self, state: dict):
        """`state` é o dicionário salvo da janela (window_state.json): guarda volume e mudo."""
        self.state = state
        self.state.setdefault("music_volume", 0.5)
        self.state.setdefault("music_muted", False)
        self.ok = self._init_mixer()
        self.track = None
        self.converting = None         # thread convertendo .weba -> .opus
        self._pending = None           # música pronta para começar (vinda da thread)
        if self.ok:
            self._start()

    # ---------- propriedades ----------
    @property
    def volume(self) -> float:
        return float(self.state["music_volume"])

    @property
    def muted(self) -> bool:
        return bool(self.state["music_muted"])

    def describe(self) -> str:
        """Texto curto para avisos e dicas ("música: 50%", "música: mudo")."""
        if not self.ok:
            return "música: sem som"
        if self.converting:
            return "música: preparando..."
        return "música: mudo" if self.muted else f"música: {round(self.volume * 100)}%"

    # ---------- controles ----------
    def toggle_mute(self):
        self.state["music_muted"] = not self.muted
        self._apply()

    def change(self, delta: float):
        """Muda o volume (e tira do mudo)."""
        self.state["music_volume"] = round(max(0.0, min(1.0, self.volume + delta)), 2)
        self.state["music_muted"] = False
        self._apply()

    def update(self):
        """Chamado a cada quadro: começa a tocar quando a conversão terminar."""
        if self._pending is not None:
            path, self._pending = self._pending, None
            self._play(path)

    # ---------- interno ----------
    def _init_mixer(self) -> bool:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            return True
        except pygame.error as e:
            log.warning("sem som (mixer não iniciou): %s", e)
            return False

    def _apply(self):
        if self.ok:
            pygame.mixer.music.set_volume(0.0 if self.muted else self.volume)

    def _start(self):
        if not MUSIC_DIR.exists():
            return
        files = sorted(p for p in MUSIC_DIR.iterdir() if p.suffix.lower() in PLAYABLE)
        if files:
            self._play(files[0])
            return
        raw = sorted(p for p in MUSIC_DIR.iterdir() if p.suffix.lower() in CONVERTIBLE)
        if raw:
            self.converting = threading.Thread(target=self._convert, args=(raw[0],), daemon=True)
            self.converting.start()
        else:
            log.info("nenhuma música em %s", MUSIC_DIR)

    def _convert(self, src):
        from .webm_opus import convert
        dst = src.with_suffix(".opus")
        tmp = src.with_suffix(".opus.part")
        log.info("convertendo %s para .opus (só na primeira vez)...", src.name)
        try:
            convert(src, tmp)
            tmp.replace(dst)
            self._pending = dst
        except Exception as e:                       # arquivo estranho: segue sem música
            log.warning("não deu para converter %s: %s", src.name, e)
            tmp.unlink(missing_ok=True)
        finally:
            self.converting = None

    def _play(self, path):
        try:
            pygame.mixer.music.load(str(path))       # .opus: reconhecido pela extensão
            self._apply()
            pygame.mixer.music.play(loops=-1, fade_ms=FADE_IN_MS)
            self.track = path
            log.info("tocando %s", path.name)
        except (pygame.error, OSError) as e:
            log.warning("não deu para tocar %s: %s", path.name, e)
