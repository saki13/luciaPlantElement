// Ghidra headless post-script (Java)
// @category PVZ
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressIterator;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.*;

import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

public class ExtractOverview extends GhidraScript {

    static String ascii(String s) {
        if (s == null) return "";
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            sb.append(c >= 32 && c < 127 ? c : '?');
        }
        return sb.toString();
    }

    @Override
    public void run() throws Exception {
        StringBuilder o = new StringBuilder();
        FunctionManager fm = currentProgram.getFunctionManager();
        Listing listing = currentProgram.getListing();
        SymbolTable st = currentProgram.getSymbolTable();

        o.append("================ PROGRAM OVERVIEW ================\n");
        o.append("name        : ").append(currentProgram.getName()).append('\n');
        o.append("language    : ").append(currentProgram.getLanguageID()).append('\n');
        o.append("compiler    : ").append(currentProgram.getCompilerSpec().getCompilerSpecID()).append('\n');
        o.append("image base  : ").append(currentProgram.getImageBase()).append('\n');
        o.append("min address : ").append(currentProgram.getMinAddress()).append('\n');
        o.append("max address : ").append(currentProgram.getMaxAddress()).append('\n');

        o.append("\n================ ENTRY POINTS ================\n");
        List<Address> entries = new ArrayList<>();
        AddressIterator epi = st.getExternalEntryPointIterator();
        while (epi.hasNext()) {
            Address a = epi.next();
            entries.add(a);
            o.append("entry: ").append(a).append('\n');
        }

        o.append("\n================ MEMORY BLOCKS ================\n");
        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            long size = b.getSize();
            o.append(String.format("%-10s start=%-12s end=%-12s size=%10d (%8.1f KB) r=%s w=%s x=%s%n",
                    b.getName(), b.getStart(), b.getEnd(), size, size / 1024.0,
                    b.isRead(), b.isWrite(), b.isExecute()));
        }

        o.append("\n================ FUNCTIONS ================\n");
        int total = 0, named = 0;
        List<String> namedSamples = new ArrayList<>();
        FunctionIterator fi = fm.getFunctions(true);
        while (fi.hasNext()) {
            Function f = fi.next();
            total++;
            String nm = f.getName();
            if (!(nm.startsWith("FUN_") || nm.startsWith("sub_") || nm.startsWith("thunk_"))) {
                named++;
                if (namedSamples.size() < 30) {
                    namedSamples.add(nm + " @ " + f.getEntryPoint());
                }
            }
        }
        o.append("total functions : ").append(total).append('\n');
        o.append("named functions : ").append(named).append('\n');
        o.append("--- sample named functions ---\n");
        for (String s : namedSamples) o.append("  ").append(ascii(s)).append('\n');

        o.append("\n================ STRINGS ================\n");
        int strCount = 0;
        List<String> interesting = new ArrayList<>();
        String[] kw = {"zombie", "plant", "level", "sun", "pea", "card", "wave", "coin",
                "save", "pak", "reanim", "particle", "lawn", "tower", "shoot", "http", ".dll", ".exe"};
        DataIterator di = listing.getDefinedData(true);
        while (di.hasNext()) {
            Data d = di.next();
            try {
                if (d.hasStringValue() && d.getValue() != null) {
                    String sv = d.getValue().toString();
                    strCount++;
                    String low = sv.toLowerCase();
                    boolean hit = false;
                    for (String k : kw) { if (low.contains(k)) { hit = true; break; } }
                    if (hit && sv.length() >= 4 && interesting.size() < 60) {
                        String cut = sv.length() > 90 ? sv.substring(0, 90) : sv;
                        interesting.add(d.getAddress() + "  " + cut);
                    }
                }
            } catch (Exception ignore) {}
        }
        o.append("defined strings : ").append(strCount).append('\n');
        o.append("--- interesting strings (keyword filtered) ---\n");
        for (String s : interesting) o.append("  ").append(ascii(s)).append('\n');

        o.append("\n================ EXTERNAL LIBRARIES / IMPORTS ================\n");
        Map<String, List<String>> ext = new TreeMap<>();
        SymbolIterator esi = st.getExternalSymbols();
        while (esi.hasNext()) {
            Symbol sym = esi.next();
            String lib = sym.getParentNamespace() != null ? sym.getParentNamespace().getName() : "?";
            ext.computeIfAbsent(lib, k -> new ArrayList<>()).add(sym.getName());
        }
        for (Map.Entry<String, List<String>> e : ext.entrySet()) {
            List<String> uniq = new ArrayList<>(new java.util.TreeSet<>(e.getValue()));
            o.append(String.format("%-14s %d functions%n", e.getKey(), uniq.size()));
            String joined = String.join(", ", uniq.subList(0, Math.min(25, uniq.size())));
            o.append("   ").append(ascii(joined)).append('\n');
        }

        o.append("\n================ ENTRY DISASSEMBLY (first 20 insns) ================\n");
        if (!entries.isEmpty()) {
            Instruction ins = listing.getInstructionAt(entries.get(0));
            int n = 0;
            while (ins != null && n < 20) {
                o.append("  ").append(ins.getAddress()).append("  ").append(ascii(ins.toString())).append('\n');
                ins = ins.getNext();
                n++;
            }
        }

        String result = o.toString();
        println(result);
        String resPath = "D:\\lucia\\rea\\project\\pvz\\logs\\overview.txt";
        try (PrintWriter pw = new PrintWriter(Files.newBufferedWriter(Paths.get(resPath), StandardCharsets.UTF_8))) {
            pw.print(result);
        }
        println("OVERVIEW_WRITTEN: " + resPath);
    }
}
