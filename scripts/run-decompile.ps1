$env:JAVA_HOME = "C:\Program Files\Java\jdk21"
$gh = "D:\apps\ghidra_12.1.4_PUBLIC\support\analyzeHeadless.bat"
$projLoc = "D:\lucia\rea\project\pvz\ghidra-project"
$log = "D:\lucia\rea\project\pvz\logs\decompile.log"

& $gh $projLoc PVZ -process PlantsVsZombies.exe -noanalysis `
  -scriptPath "D:\lucia\rea\project\pvz\scripts" `
  -postScript DecompileFunctions.java 2>&1 | Out-File -LiteralPath $log -Encoding utf8
"EXIT_CODE: $LASTEXITCODE"
