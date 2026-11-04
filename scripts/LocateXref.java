// Locate core functions by cross-referencing key strings.
// Headless: auto-compiled; class name must match file name.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.data.*;
import ghidra.program.model.data.AbstractStringDataType;

import java.io.*;
import java.util.*;

public class LocateXref extends GhidraScript {

    static final String OUT = "D:\\lucia\\rea\\project\\pvz\\logs\\xref-map.txt";

    // lower-case keyword groups
    static final String[] KEYWORDS = {
        "wave", "spawn", "picker", "zombie point", "preboard", "distribution",
        "sun", "coin", "money", "cost",
        "bullet", "projectile", "pea", "damage", "attack", "shoot", "muzzle", "fire"
    };

    boolean matches(String s) {
        String low = s.toLowerCase(Locale.ROOT);
        for (String k : KEYWORDS) {
            if (low.contains(k)) return true;
        }
        return false;
    }

    @Override
    public void run() throws Exception {
        PrintWriter w = new PrintWriter(new OutputStreamWriter(
                new FileOutputStream(OUT), "UTF-8"));

        Listing listing = currentProgram.getListing();
        FunctionManager fm = currentProgram.getFunctionManager();
        ReferenceManager rm = currentProgram.getReferenceManager();

        DataIterator it = listing.getDefinedData(true);
        int count = 0;
        while (it.hasNext()) {
            Data d = it.next();
            if (d == null || !(d.getDataType() instanceof AbstractStringDataType)) continue;
            String val = d.getValue() == null ? "" : d.getValue().toString();
            if (val.length() < 3 || val.length() > 160) continue;
            if (!matches(val)) continue;

            Address saddr = d.getMinAddress();
            // unique referencing functions
            LinkedHashSet<String> funcs = new LinkedHashSet<>();
            for (Reference r : rm.getReferencesTo(saddr)) {
                Address from = r.getFromAddress();
                Function f = fm.getFunctionContaining(from);
                if (f != null) {
                    funcs.add(f.getEntryPoint().toString() + "  " + f.getName());
                }
            }
            if (funcs.isEmpty()) continue;

            w.println("STRING @ " + saddr + " : " + val);
            int n = 0;
            for (String f : funcs) {
                w.println("    <- " + f);
                if (++n >= 6) break;
            }
            w.println();
            count++;
        }
        w.println("total matched strings with xrefs: " + count);
        w.close();
        println("xref map written: " + OUT + " (strings=" + count + ")");
    }
}
