"""
PopCap PAK unpacker for Plants vs Zombies (main.pak).
- whole file is XOR-obfuscated with key 0xF7
- header: magic 0xBAC04AC0, version 0
- entries until flag 0x80 (FILEFLAGS_END):
    flag(1) nameLen(1) name(N) size(4) time(8)
- file data is stored sequentially right after the index (no per-entry offset),
  so each file's offset is accumulated from the end of the index.
"""
import os
import struct

PAK_PATH = r"D:\apps\pvz\Plants vs Zombies GotY_chs\main.pak"
OUT_DIR = r"D:\lucia\rea\project\pvz\unpacked"
LIST_FILE = r"D:\lucia\rea\project\pvz\logs\pak-filelist.txt"

with open(PAK_PATH, "rb") as f:
    raw = f.read()

# 1. decrypt in place (whole file)
data = bytearray(b ^ 0xF7 for b in raw)

# 2. header
magic, version = struct.unpack_from("<II", data, 0)
assert magic == 0xBAC04AC0, "bad magic: 0x%08X" % magic
assert version == 0, "unexpected version: %d" % version

# 3. parse entries
pos = 8
entries = []
while True:
    flag = data[pos]
    pos += 1
    if flag == 0x80:  # FILEFLAGS_END
        break
    name_len = data[pos]
    pos += 1
    name = bytes(data[pos:pos + name_len]).decode("utf-8", "replace")
    pos += name_len
    size, = struct.unpack_from("<I", data, pos)
    pos += 4
    ftime, = struct.unpack_from("<q", data, pos)
    pos += 8
    entries.append((name.replace("\\", "/"), size, ftime))

# 4. data region starts right after the index; offsets accumulate
data_start = pos
running = data_start
records = []
for name, size, ftime in entries:
    records.append((name, running, size))
    running += size

assert running <= len(data), "data exceeds file size"

# 5. write listing
os.makedirs(os.path.dirname(LIST_FILE), exist_ok=True)
ext_stats = {}
with open(LIST_FILE, "w", encoding="utf-8") as lf:
    lf.write("magic=0x%08X version=%d files=%d index_end=%d data_start=%d total_size=%d\n"
             % (magic, version, len(entries), pos, data_start, len(data)))
    lf.write("=" * 90 + "\n")
    for name, off, size in records:
        lf.write("%-50s off=%-9d size=%9d\n" % (name, off, size))
        ext = os.path.splitext(name)[1].lower() or "(noext)"
        ext_stats[ext] = ext_stats.get(ext, 0) + 1

# 6. extract every file
os.makedirs(OUT_DIR, exist_ok=True)
for name, off, size in records:
    target = os.path.join(OUT_DIR, name.replace("/", os.sep))
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "wb") as out:
        out.write(bytes(data[off:off + size]))

print("files extracted :", len(records))
print("data region     :", data_start, "->", running, "file size", len(data))
print("extension counts:")
for ext, c in sorted(ext_stats.items(), key=lambda kv: -kv[1]):
    print("  %-10s %d" % (ext, c))
print("listing written :", LIST_FILE)
print("output dir      :", OUT_DIR)
