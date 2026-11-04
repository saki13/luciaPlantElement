# Ghidra headless post-script (Jython 2.7 compatible)
# @category PVZ
import os

out = []
def w(s=""):
    out.append(str(s))

prog = currentProgram
fm = prog.getFunctionManager()
mem = prog.getMemory()
listing = prog.getListing()

w("================ PROGRAM OVERVIEW ================")
w("name        : " + prog.getName())
w("language    : " + prog.getLanguageID().toString())
w("compiler    : " + prog.getCompilerSpec().getCompilerSpecID().toString())
w("image base  : " + prog.getImageBase().toString())
w("min address : " + prog.getMinAddress().toString())
w("max address : " + prog.getMaxAddress().toString())

# entry points
w("")
w("================ ENTRY POINTS ================")
for ep in prog.getSymbolTable().getExternalEntryPointIterator():
    w("entry: " + ep.toString())

# memory blocks
w("")
w("================ MEMORY BLOCKS ================")
for b in mem.getBlocks():
    size = b.getSize()
    w("{:<10} start={:<12} end={:<12} size={:>10} ({:>8.1f} KB) r={} w={} x={}".format(
        b.getName(), b.getStart().toString(), b.getEnd().toString(),
        size, size / 1024.0, b.isRead(), b.isWrite(), b.isExecute()))

# functions
w("")
w("================ FUNCTIONS ================")
total = 0
named = 0
named_samples = []
for f in fm.getFunctions(True):
    total += 1
    nm = f.getName()
    if not (nm.startswith("FUN_") or nm.startswith("sub_") or nm.startswith("thunk_")):
        named += 1
        if len(named_samples) < 30:
            named_samples.append(nm + " @ " + f.getEntryPoint().toString())
w("total functions : %d" % total)
w("named functions : %d" % named)
w("--- sample named functions ---")
for s in named_samples:
    w("  " + s)

# strings
w("")
w("================ STRINGS ================")
str_count = 0
interesting = []
kw = ["zombie", "plant", "level", "sun", "pea", "card", "wave", "coin", "save",
      "pak", "reanim", "particle", "lawn", "tower", "shoot", "http", ".dll", ".exe"]
dataIter = listing.getDefinedData(True)
for d in dataIter:
    try:
        if d.hasStringValue():
            val = d.getValue()
            if val is None:
                continue
            sv = val.toString()
            str_count += 1
            low = sv.lower()
            if len(interesting) < 60 and any(k in low for k in kw) and len(sv) >= 4:
                interesting.append(d.getAddress().toString() + "  " + sv[:90])
    except Exception:
        pass
w("defined strings : %d" % str_count)
w("--- interesting strings (keyword filtered) ---")
for s in interesting:
    w("  " + s.encode("ascii", "replace"))

# imports / external symbols
w("")
w("================ EXTERNAL LIBRARIES / IMPORTS ================")
ext = {}
for sym in prog.getSymbolTable().getExternalSymbols():
    lib = sym.getParentNamespace()
    libname = lib.getName() if lib is not None else "?"
    ext.setdefault(libname, []).append(sym.getName())
for lib in sorted(ext.keys()):
    names = sorted(set(ext[lib]))
    w("%-14s %d functions" % (lib, len(names)))
    w("   " + ", ".join(names[:25]).encode("ascii", "replace"))

# disassembly of primary entry
w("")
w("================ ENTRY DISASSEMBLY (first 20 insns) ================")
eps = list(prog.getSymbolTable().getExternalEntryPointIterator())
if eps:
    addr = eps[0]
    inst = listing.getInstructionAt(addr)
    n = 0
    while inst is not None and n < 20:
        w("  " + inst.getAddress().toString() + "  " + inst.toString())
        inst = inst.getNext()
        n += 1

result = "\n".join(out)
print(result)
resfile = os.path.join("D:\\lucia\\rea\\project\\pvz\\logs", "overview.txt")
fh = open(resfile, "w")
fh.write(result)
fh.close()
print("OVERVIEW_WRITTEN: " + resfile)
