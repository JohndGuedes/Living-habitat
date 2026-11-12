"""Converte música .weba/.webm (áudio Opus) para .opus, que o pygame toca.

O jogo já faz isso sozinho na primeira vez (habitat/audio.py); este script é para fazer
antes, à mão. Só troca o contêiner, sem recodificar (habitat/webm_opus.py).

    .venv\Scripts\python tools\convert_music.py                 (todas as .weba de assets/music)
    .venv\Scripts\python tools\convert_music.py arquivo.weba    (só esse; salva .opus ao lado)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from habitat.webm_opus import convert  # noqa: E402

MUSIC = ROOT / "assets" / "music"


def main():
    files = [Path(a) for a in sys.argv[1:]] or sorted(MUSIC.glob("*.weba")) + sorted(MUSIC.glob("*.webm"))
    if not files:
        print("nenhuma .weba/.webm em", MUSIC)
    for src in files:
        n, minutes = convert(src, src.with_suffix(".opus"))
        print(f"{src.name} -> {src.with_suffix('.opus').name}: {n} pacotes, {minutes:.1f} min")


if __name__ == "__main__":
    main()
