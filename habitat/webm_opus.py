"""Converte áudio .weba/.webm (Opus) para .opus (Opus em Ogg), que o pygame toca.

O pygame não abre o contêiner WebM, mas toca Opus dentro de Ogg. Aqui só se troca o
contêiner (remux): os pacotes Opus do WebM são copiados para páginas Ogg, sem recodificar
(sem perder qualidade e sem precisar de ffmpeg). Usado por audio.py (automático) e por
tools/convert_music.py.
"""
import struct
from pathlib import Path

# elementos EBML (Matroska/WebM) que interessam
SEGMENT, CLUSTER, BLOCKGROUP = 0x18538067, 0x1F43B675, 0xA0
TRACKS, TRACKENTRY, TRACKNUMBER, CODECID, CODECPRIVATE = 0x1654AE6B, 0xAE, 0xD7, 0x86, 0x63A2
SIMPLEBLOCK, BLOCK = 0xA3, 0xA1
MASTERS = {SEGMENT, CLUSTER, BLOCKGROUP, TRACKS, TRACKENTRY}


def _vint(data, pos, keep_marker):
    first = data[pos]
    length = 1
    mask = 0x80
    while length <= 8 and not first & mask:
        mask >>= 1
        length += 1
    value = first if keep_marker else first & (mask - 1)
    unknown = (first & (mask - 1)) == mask - 1
    for i in range(1, length):
        value = (value << 8) | data[pos + i]
        unknown = unknown and data[pos + i] == 0xFF
    return value, pos + length, unknown


def read_webm(data):
    """-> (OpusHead, [pacotes]) da trilha Opus."""
    head, packets = None, []
    tracks = {}                        # número -> codec
    entry = {}
    stack = [(0, len(data))]           # (início, fim) dos elementos mestres abertos

    pos = 0
    end = len(data)
    while pos < end:
        while stack and pos >= stack[-1][1]:
            stack.pop()
            if entry.get("num") is not None and "codec" in entry:
                tracks[entry["num"]] = entry["codec"]
                if entry["codec"] == "A_OPUS" and entry.get("private"):
                    head = entry["private"]
        eid, pos, _ = _vint(data, pos, True)
        size, pos, unknown = _vint(data, pos, False)
        stop = end if unknown else pos + size
        if eid in MASTERS:
            if eid == TRACKENTRY:
                entry = {}
            stack.append((pos, stop))
            continue                   # entra no elemento
        body = data[pos:stop]
        if eid == TRACKNUMBER:
            entry["num"] = int.from_bytes(body, "big")
        elif eid == CODECID:
            entry["codec"] = bytes(body).decode("ascii", "replace").rstrip("\0")
        elif eid == CODECPRIVATE:
            entry["private"] = bytes(body)
        elif eid in (SIMPLEBLOCK, BLOCK):
            track, p, _ = _vint(body, 0, False)
            flags = body[p + 2]
            if flags & 0x06:
                raise SystemExit("blocos com 'lacing' não suportados")
            if tracks.get(track, "A_OPUS") == "A_OPUS":
                packets.append(bytes(body[p + 3:]))
        pos = stop
    if entry.get("codec") == "A_OPUS" and entry.get("private") and head is None:
        head = entry["private"]
    if not head or not head.startswith(b"OpusHead"):
        raise SystemExit("não achei a trilha Opus (OpusHead) no arquivo")
    return head, packets


def opus_samples(packet):
    """Duração do pacote em amostras a 48 kHz (pelo byte TOC)."""
    if not packet:
        return 0
    toc = packet[0]
    config = toc >> 3
    if config < 12:
        frame = (480, 960, 1920, 2880)[config % 4]
    elif config < 16:
        frame = (480, 960)[config % 2]
    else:
        frame = (120, 240, 480, 960)[config % 4]
    code = toc & 3
    count = 1 if code == 0 else 2 if code in (1, 2) else (packet[1] & 0x3F if len(packet) > 1 else 0)
    return frame * count


def _crc_table():
    table = []
    for i in range(256):
        r = i << 24
        for _ in range(8):
            r = ((r << 1) ^ 0x04C11DB7) if r & 0x80000000 else (r << 1)
        table.append(r & 0xFFFFFFFF)
    return table


CRC = _crc_table()


def _crc(data):
    c = 0
    for b in data:
        c = ((c << 8) & 0xFFFFFFFF) ^ CRC[((c >> 24) ^ b) & 0xFF]
    return c


class OggWriter:
    SERIAL = 0x4C48_6162       # "LHab"

    def __init__(self, f):
        self.f, self.seq = f, 0

    def page(self, packets, granule, flags=0):
        lacing, body = [], b""
        for p in packets:
            n = len(p)
            lacing += [255] * (n // 255) + [n % 255]
            body += p
        hdr = struct.pack("<4sBBqIIIB", b"OggS", 0, flags, granule, self.SERIAL, self.seq, 0, len(lacing))
        hdr += bytes(lacing)
        crc = _crc(hdr + body)
        hdr = hdr[:22] + struct.pack("<I", crc) + hdr[26:]
        self.f.write(hdr + body)
        self.seq += 1


def convert(src, dst):
    data = memoryview(src.read_bytes())
    head, packets = read_webm(data)
    with open(dst, "wb") as f:
        w = OggWriter(f)
        w.page([head], 0, flags=0x02)                                  # início do fluxo
        vendor = b"Living Habitat"
        w.page([b"OpusTags" + struct.pack("<I", len(vendor)) + vendor + struct.pack("<I", 0)], 0)
        granule = 0
        group, segs = [], 0
        for i, p in enumerate(packets):
            need = len(p) // 255 + 1
            if group and (segs + need > 255 or sum(map(len, group)) > 8000):
                w.page(group, granule)
                group, segs = [], 0
            group.append(p)
            segs += need
            granule += opus_samples(p)
        w.page(group, granule, flags=0x04)                             # fim do fluxo
    minutes = granule / 48000 / 60
    return len(packets), minutes
