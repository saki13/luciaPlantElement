// Decompile a selected set of core functions to C pseudo-code.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;

import java.io.*;
import java.util.*;

public class DecompileFunctions extends GhidraScript {

    static final String OUT = "D:\\lucia\\rea\\project\\pvz\\logs\\decompiled.txt";

    // selected core functions across the three systems
    static final String[] ADDRS = {
        // wave generation
        "0040e690", "0040fd10", "0041e140",
        // projectile / plant attack
        "00480100", "00480d80", "00481ea0",
        // sun economy
        "0043c9b0", "00429a00", "0043b5a0"
    };

    @Override
    public void run() throws Exception {
        PrintWriter w = new PrintWriter(new OutputStreamWriter(
                new FileOutputStream(OUT), "UTF-8"));

        DecompInterface ifc = new DecompInterface();
        ifc.setOptions(new DecompileOptions());
        ifc.toggleCCode(true);
        ifc.toggleSyntaxTree(true);
        ifc.setSimplificationStyle("decompile");
        ifc.openProgram(currentProgram);

        FunctionManager fm = currentProgram.getFunctionManager();

        for (String a : ADDRS) {
            Address addr = toAddr(a);
            Function f = fm.getFunctionAt(addr);
            if (f == null) {
                f = fm.getFunctionContaining(addr);
            }
            w.println("================================================================");
            if (f == null) {
                w.println("NO FUNCTION AT " + a);
                continue;
            }
            w.println("FUNCTION " + f.getName() + " @ " + f.getEntryPoint()
                    + "  size=" + f.getBody().getNumAddresses());
            w.println("signature: " + f.getSignature().getPrototypeString());
            w.println("----------------------------------------------------------------");
            DecompileResults res = ifc.decompileFunction(f, 90, monitor);
            if (res.decompileCompleted() && res.getDecompiledFunction() != null) {
                w.println(res.getDecompiledFunction().getC());
            } else {
                w.println("DECOMPILE FAILED: " + res.getErrorMessage());
            }
            w.println();
        }
        ifc.dispose();
        w.close();
        println("decompiled functions written: " + OUT);
    }
}
