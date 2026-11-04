$env:JAVA_HOME = "C:\Program Files\Java\jdk21"
$gh = "D:\apps\ghidra_12.1.4_PUBLIC\support\analyzeHeadless.bat"
$projLoc = "D:\lucia\rea\project\pvz\ghidra-project"
$projName = "PVZ"
$target = "D:\apps\pvz\Plants vs Zombies GotY_chs\PlantsVsZombies.exe"
$log = "D:\lucia\rea\project\pvz\logs\headless-import.log"

"=== Ghidra headless analysis started: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Out-File -LiteralPath $log -Encoding utf8
& $gh $projLoc $projName -import $target -overwrite 2>&1 | Out-File -LiteralPath $log -Append -Encoding utf8
"=== finished: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  EXIT_CODE: $LASTEXITCODE ===" | Out-File -LiteralPath $log -Append -Encoding utf8
