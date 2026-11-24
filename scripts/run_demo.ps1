# Start 3 LAN Chat instances on ONE Windows machine (3 console windows).
# Usage:
#   .\scripts\run_demo.ps1
#   .\scripts\run_demo.ps1 -Names Quan,Minh,Huy -BasePort 5001
#   .\scripts\run_demo.ps1 -Broadcast 127.255.255.255   # offline / no LAN
#
# In each window:  /list   /chat <name>   /send <file>   /help   /quit

param(
    [string[]]$Names = @("Quan", "Minh", "Huy"),
    [int]$BasePort = 5001,
    [int]$UdpPort = 9999,
    [string]$Broadcast = "255.255.255.255"
)

$root = Split-Path -Parent $PSScriptRoot
Write-Host "Project : $root"
Write-Host "Peers   : $($Names -join ', ')"
Write-Host "Broadcast: $Broadcast`:$UdpPort"
Write-Host ""

for ($i = 0; $i -lt $Names.Count; $i++) {
    $peer = $Names[$i]
    $port = $BasePort + $i
    Start-Process -FilePath "python" `
        -ArgumentList @("-m", "lanchat", "--name", $peer, "--port", "$port",
                        "--udp-port", "$UdpPort", "--bcast", $Broadcast) `
        -WorkingDirectory $root
    Write-Host "  started $peer on TCP $port"
    Start-Sleep -Milliseconds 500
}

Write-Host ""
Write-Host "Open the three windows and try: /list  ->  /chat <name>  ->  /send <file>"
