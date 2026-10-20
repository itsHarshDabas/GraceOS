"""Drive a VMware console over local VNC.
vnc.py PORT shot FILE.png | type 'text' (Enter appended) | keys ctrl+alt+f2 [...]"""
import socket, struct, sys, time, zlib

SHIFTED = '~!@#$%^&*()_+{}|:"<>?'
NAMED = {"ctrl": 0xFFE3, "alt": 0xFFE9, "shift": 0xFFE1, "super": 0xFFEB, "ret": 0xFF0D,
         "esc": 0xFF1B, "tab": 0xFF09, "space": 0x20, "up": 0xFF52, "down": 0xFF54}
NAMED.update({f"f{i}": 0xFFBE + i - 1 for i in range(1, 13)})


def recvn(s, n):
    b = b""
    while len(b) < n:
        c = s.recv(n - len(b))
        if not c:
            raise EOFError
        b += c
    return b


s = socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=30)
recvn(s, 12)
s.sendall(b"RFB 003.008\n")
types = recvn(s, recvn(s, 1)[0])
assert 1 in types, f"server wants auth: {list(types)}"
s.sendall(b"\x01")
assert recvn(s, 4) == b"\0\0\0\0"
s.sendall(b"\x01")
w, h = struct.unpack(">HH", recvn(s, 4))
recvn(s, 16)
recvn(s, struct.unpack(">I", recvn(s, 4))[0])


def key(sym, down):
    s.sendall(struct.pack(">BBxxI", 4, down, sym))


cmd = sys.argv[2]
if cmd == "shot":
    # 32bpp little-endian BGRX, raw encoding only
    s.sendall(struct.pack(">BxxxBBBBHHHBBBxxx", 0, 32, 24, 0, 1, 255, 255, 255, 16, 8, 0))
    s.sendall(struct.pack(">BxHi", 2, 1, 0))
    s.sendall(struct.pack(">BBHHHH", 3, 0, 0, 0, w, h))
    px = bytearray(w * h * 4)
    while True:
        t = recvn(s, 1)[0]
        if t != 0:  # skip bell / cut text etc.
            if t == 2:
                continue
            if t == 3:
                recvn(s, 3); recvn(s, struct.unpack(">I", recvn(s, 4))[0]); continue
            if t == 1:
                recvn(s, 1); n = struct.unpack(">H", recvn(s, 2))[0]; recvn(s, 6 * n); continue
        recvn(s, 1)
        n = struct.unpack(">H", recvn(s, 2))[0]
        for _ in range(n):
            x, y, rw, rh, enc = struct.unpack(">HHHHi", recvn(s, 12))
            if enc != 0:
                continue  # pseudo-encodings (desktop size, cursor) carry no pixels here
            data = recvn(s, rw * rh * 4)
            for r in range(rh):
                o = ((y + r) * w + x) * 4
                px[o:o + rw * 4] = data[r * rw * 4:(r + 1) * rw * 4]
        break
    # BGRX -> RGB
    rows = []
    for i in range(h):
        row = px[i * w * 4:(i + 1) * w * 4]
        rgb = bytearray(w * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = row[0::4], row[1::4], row[2::4]
        rows.append(b"\0" + bytes(rgb))
    def chunk(tag, d):
        return struct.pack(">I", len(d)) + tag + d + struct.pack(">I", zlib.crc32(tag + d))
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) \
        + chunk(b"IDAT", zlib.compress(b"".join(rows), 6)) + chunk(b"IEND", b"")
    open(sys.argv[3], "wb").write(png)
    print(f"saved {w}x{h}")
elif cmd == "type":
    for c in sys.argv[3] + "\n":
        sym = 0xFF0D if c == "\n" else ord(c)
        sh = c in SHIFTED or c.isupper()
        if sh: key(0xFFE1, 1)
        key(sym, 1); key(sym, 0)
        if sh: key(0xFFE1, 0)
        time.sleep(0.04)
    print("typed")
elif cmd == "click":  # click X Y [left|right]
    x, y = int(sys.argv[3]), int(sys.argv[4])
    mask = 4 if sys.argv[5:] == ["right"] else 1
    for m in (0, mask, 0):
        s.sendall(struct.pack(">BBHH", 5, m, x, y))
        time.sleep(0.15)
    print("clicked")
elif cmd == "keys":
    for combo in sys.argv[3:]:
        syms = [NAMED.get(k, ord(k[0])) for k in combo.split("+")]
        for k in syms: key(k, 1)
        time.sleep(0.05)
        for k in reversed(syms): key(k, 0)
        time.sleep(0.3)
    print("sent")
s.close()
