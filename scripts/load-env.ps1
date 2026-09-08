# Reads simple KEY=value configuration without evaluating it as PowerShell code.
$projectPath = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $projectPath '.env'
if (Test-Path -LiteralPath $envPath) {
    foreach ($line in Get-Content -LiteralPath $envPath) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
            $settingName = $Matches[1]
            $settingValue = $Matches[2]
            if ($settingValue.Length -ge 2 -and (($settingValue.StartsWith('"') -and $settingValue.EndsWith('"')) -or ($settingValue.StartsWith("'") -and $settingValue.EndsWith("'")))) {
                $settingValue = $settingValue.Substring(1, $settingValue.Length - 2)
            }
            [Environment]::SetEnvironmentVariable($settingName, $settingValue, 'Process')
        }
    }
}
