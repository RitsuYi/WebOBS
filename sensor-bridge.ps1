param([string]$ConfigPath = (Join-Path $PSScriptRoot 'config.json'))
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$libraryDirectory = Join-Path $PSScriptRoot 'vendor\LibreHardwareMonitor'

try {
    # Resolve dependencies from the official release, without changing system DLLs.
    $resolver = [System.ResolveEventHandler] {
        param($sender, $eventArgs)
        $name = (New-Object System.Reflection.AssemblyName($eventArgs.Name)).Name
        $path = Join-Path $libraryDirectory ($name + '.dll')
        if (Test-Path -LiteralPath $path) {
            return [System.Reflection.Assembly]::LoadFrom($path)
        }
        return $null
    }
    [AppDomain]::CurrentDomain.add_AssemblyResolve($resolver)
    [void][System.Reflection.Assembly]::LoadFrom((Join-Path $libraryDirectory 'LibreHardwareMonitorLib.dll'))
    $computer = New-Object LibreHardwareMonitor.Hardware.Computer
    $computer.IsCpuEnabled = $true
    $computer.IsGpuEnabled = $true
    $configPath = $ConfigPath
    $bridgeConfig = $null
    if (Test-Path -LiteralPath $configPath) {
        $bridgeConfig = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    $computer.IsMotherboardEnabled = ($null -ne $bridgeConfig -and $bridgeConfig.motherboardSensors -eq $true)
    $computer.IsPowerMonitorEnabled = ($null -ne $bridgeConfig -and $bridgeConfig.powerMode -eq 'measured')
    $computer.Open()

    function Read-Hardware($hardware) {
        $hardware.Update()
        $sensors = @($hardware.Sensors | ForEach-Object {
            $voltageParameters = $null
            if ($_.SensorType.ToString() -eq 'Voltage' -and $_.Parameters.Count -eq 3 -and
                $_.Parameters[0].Name.StartsWith('Ri [') -and $_.Parameters[1].Name.StartsWith('Rf [') -and
                $_.Parameters[2].Name.StartsWith('Vf [')) {
                $voltageParameters = @{ ri = $_.Parameters[0].Value; rf = $_.Parameters[1].Value; vf = $_.Parameters[2].Value }
            }
            [ordered]@{ id = $_.Identifier.ToString(); name = $_.Name; type = $_.SensorType.ToString();
                value = $_.Value; voltageParameters = $voltageParameters }
        })
        if ($hardware.HardwareType.ToString() -eq 'Cpu') {
            $validLowLevel = @($sensors | Where-Object { ($_.type -eq 'Clock' -or $_.type -eq 'Temperature') -and $null -ne $_.value })
            if ($validLowLevel.Count -eq 0) {
                foreach ($sensor in $sensors) {
                    if ($sensor.type -eq 'Power' -and $sensor.value -eq 0) { $sensor.value = $null }
                }
            }
        }
        $parentId = if ($null -ne $hardware.Parent) { $hardware.Parent.Identifier.ToString() } else { $null }
        [ordered]@{ id = $hardware.Identifier.ToString(); name = $hardware.Name; type = $hardware.HardwareType.ToString();
            parentId = $parentId; sensors = $sensors }
        foreach ($child in $hardware.SubHardware) { Read-Hardware $child }
    }

    while ($true) {
        $interval = 1000
        try {
            if (Test-Path -LiteralPath $configPath) {
                $bridgeConfig = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
                $interval = [Math]::Max(1000, [Math]::Min(10000, $bridgeConfig.sensorIntervalMs))
                $computer.IsMotherboardEnabled = ($bridgeConfig.motherboardSensors -eq $true)
                $computer.IsPowerMonitorEnabled = ($bridgeConfig.powerMode -eq 'measured')
            }
            $devices = @($computer.Hardware | ForEach-Object { Read-Hardware $_ })
            $packet = [ordered]@{ hardware = $devices; error = $null }
            [Console]::WriteLine(($packet | ConvertTo-Json -Depth 8 -Compress))
        } catch {
            [Console]::WriteLine((@{ hardware = @(); error = $_.Exception.Message } | ConvertTo-Json -Compress))
        }
        Start-Sleep -Milliseconds $interval
    }
} catch {
    [Console]::WriteLine((@{ hardware = @(); error = $_.Exception.Message } | ConvertTo-Json -Compress))
    exit 1
} finally {
    if ($null -ne $computer) { $computer.Close() }
}
