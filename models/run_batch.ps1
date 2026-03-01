$BlenderPath = "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
$ScriptPath = "generate_character.py"

Write-Host "Starting Premium Character Generation..."

for ($i = 1; $i -le 100; $i++) {
    Write-Host "Iteration $i..."
    $output = & $BlenderPath --background --python $ScriptPath 2>&1
    
    $outStr = $output -join "`n"
    Write-Host $outStr

    if ($outStr -match "ANIM_IMPORTED") {
        Write-Host "Animation imported. Continuing..."
    }
    elseif ($outStr -match "ALL_ANIMATIONS_DONE") {
        Write-Host "SUCCESS: All animations processed!"
        break
    }
    else {
        Write-Host "Error or no progress in iteration $i. Check output."
    }
    
    Start-Sleep -Seconds 1
}
