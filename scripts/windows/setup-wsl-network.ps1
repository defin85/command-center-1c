#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Setup network access from WSL2 to Windows services (RAS, etc.)

.DESCRIPTION
    This script diagnoses and configures:
    - Port forwarding via netsh portproxy (for services listening on 127.0.0.1)
    - Windows Firewall rules
    - Hyper-V Firewall for WSL2

.PARAMETER Diagnose
    Diagnose only, no changes

.PARAMETER Setup
    Configure port proxy and firewall

.PARAMETER Remove
    Remove port proxy settings

.PARAMETER Ports
    List of ports to configure (default: 1545)

.EXAMPLE
    .\setup-wsl-network.ps1 -Diagnose
    .\setup-wsl-network.ps1 -Setup -Ports 1545,1546
    .\setup-wsl-network.ps1 -Remove -Ports 1545
#>

param(
    [switch]$Diagnose,
    [switch]$Setup,
    [switch]$Remove,
    [int[]]$Ports = @(1545)
)

$ErrorActionPreference = "Stop"

function Write-Success { Write-Host "[OK] $args" -ForegroundColor Green }
function Write-Fail { Write-Host "[FAIL] $args" -ForegroundColor Red }
function Write-Warn { Write-Host "[WARN] $args" -ForegroundColor Yellow }
function Write-Info { Write-Host "[INFO] $args" -ForegroundColor Cyan }
function Write-Header {
    Write-Host ""
    Write-Host "=== $args ===" -ForegroundColor Blue
}

function Test-PortListening {
    param([int]$Port)
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $connections
}

function Get-PortBindAddress {
    param([int]$Port)
    $connections = Test-PortListening -Port $Port
    if ($connections) {
        return $connections | Select-Object -ExpandProperty LocalAddress -Unique
    }
    return $null
}

function Test-FirewallRule {
    param([int]$Port)
    $rules = Get-NetFirewallRule -Direction Inbound -Action Allow -Enabled True -ErrorAction SilentlyContinue |
        Get-NetFirewallPortFilter -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalPort -eq $Port -or $_.LocalPort -eq "Any" }
    return ($null -ne $rules)
}

function Test-PortProxy {
    param([int]$Port)
    $proxies = netsh interface portproxy show v4tov4 | Select-String -Pattern "\s+$Port\s+"
    return ($null -ne $proxies)
}

function Show-Diagnostics {
    Write-Header "WSL2 Network Configuration Diagnostics"
    Write-Host "Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Write-Host ""

    # 1. WSL2 status
    Write-Header "1. WSL2 Status"
    try {
        $wslStatus = wsl --list --verbose 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "WSL2 installed"
            $wslStatus | Where-Object { $_ -match '\S' } | ForEach-Object { Write-Host "    $_" }
        } else {
            Write-Fail "WSL2 not installed or not running"
        }
    } catch {
        Write-Fail "Cannot check WSL2: $_"
    }

    # 2. Port check
    Write-Header "2. Port Status"
    foreach ($port in $Ports) {
        Write-Info "Port $port"

        $bindAddresses = Get-PortBindAddress -Port $port
        if ($bindAddresses) {
            foreach ($addr in $bindAddresses) {
                if ($addr -eq "0.0.0.0" -or $addr -eq "::") {
                    Write-Success "  Listening on $addr (accessible from outside)"
                }
                elseif ($addr -eq "127.0.0.1" -or $addr -eq "::1") {
                    Write-Warn "  Listening on $addr (localhost only - needs port proxy)"
                }
                else {
                    Write-Info "  Listening on $addr"
                }
            }
        } else {
            Write-Fail "  Port not listening (service not running?)"
        }
    }

    # 3. Port Proxy
    Write-Header "3. Port Proxy (netsh portproxy)"
    $proxyList = netsh interface portproxy show v4tov4 2>&1
    if ($proxyList -match "Listen on") {
        Write-Success "Port proxy rules configured:"
        $proxyList | Where-Object { $_ -match '\d+\.\d+\.\d+\.\d+' } | ForEach-Object { Write-Host "    $_" }
    } else {
        Write-Info "Port proxy not configured"
    }

    # 4. Windows Firewall
    Write-Header "4. Windows Firewall"
    foreach ($port in $Ports) {
        if (Test-FirewallRule -Port $port) {
            Write-Success "Port $port allowed in Firewall"
        } else {
            Write-Warn "Port $port NOT allowed in Firewall (incoming connections blocked)"
        }
    }

    # 5. Hyper-V Firewall
    Write-Header "5. Hyper-V Firewall for WSL2"
    try {
        $hvFirewall = Get-NetFirewallHyperVVMSetting -PolicyStore ActiveStore -ErrorAction SilentlyContinue
        if ($hvFirewall) {
            $wslRule = $hvFirewall | Where-Object { $_.Name -eq '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' }
            if ($wslRule -and $wslRule.DefaultInboundAction -eq 'Allow') {
                Write-Success "Hyper-V Firewall allows incoming for WSL2"
            } else {
                Write-Warn "Hyper-V Firewall may block WSL2"
            }
        } else {
            Write-Info "Hyper-V Firewall not configured (may not apply)"
        }
    } catch {
        Write-Info "Hyper-V Firewall check unavailable: $_"
    }

    # 6. Recommendations
    Write-Header "6. Recommendations"

    $needsProxy = $false
    $needsFirewall = $false

    foreach ($port in $Ports) {
        $bindAddresses = Get-PortBindAddress -Port $port

        if (-not $bindAddresses) {
            Write-Warn "Port $port : Start the service (RAS) on this port"
        }
        elseif ($bindAddresses -contains "127.0.0.1" -and -not ($bindAddresses -contains "0.0.0.0")) {
            if (-not (Test-PortProxy -Port $port)) {
                Write-Warn "Port $port : Needs port proxy (service listens on localhost only)"
                $needsProxy = $true
            }
        }

        if (-not (Test-FirewallRule -Port $port)) {
            Write-Warn "Port $port : Needs Firewall rule"
            $needsFirewall = $true
        }
    }

    if ($needsProxy -or $needsFirewall) {
        Write-Host ""
        Write-Info "Run to fix:"
        Write-Host "    .\setup-wsl-network.ps1 -Setup -Ports $($Ports -join ',')" -ForegroundColor Yellow
    } else {
        Write-Success "Configuration is OK!"
    }
}

function Add-PortProxy {
    param([int]$Port)

    Write-Info "Adding port proxy for port $Port..."

    if (Test-PortProxy -Port $Port) {
        Write-Warn "Port proxy for port $Port already exists"
        return
    }

    $result = netsh interface portproxy add v4tov4 listenport=$Port listenaddress=0.0.0.0 connectport=$Port connectaddress=127.0.0.1 2>&1

    if ($LASTEXITCODE -eq 0) {
        Write-Success "Port proxy added: 0.0.0.0:$Port -> 127.0.0.1:$Port"
    } else {
        Write-Fail "Failed to add port proxy: $result"
    }
}

function Add-FirewallRule {
    param([int]$Port)

    $ruleName = "WSL2 Port $Port"

    Write-Info "Adding Firewall rule for port $Port..."

    $existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    if ($existingRule) {
        Write-Warn "Rule '$ruleName' already exists"
        return
    }

    try {
        New-NetFirewallRule -DisplayName $ruleName `
            -Direction Inbound `
            -Protocol TCP `
            -LocalPort $Port `
            -Action Allow `
            -Profile Any `
            -Description "Allow WSL2 access to port $Port" | Out-Null

        Write-Success "Firewall rule added: $ruleName"
    } catch {
        Write-Fail "Failed to add Firewall rule: $_"
    }
}

function Enable-HyperVFirewall {
    Write-Info "Configuring Hyper-V Firewall for WSL2..."

    try {
        Set-NetFirewallHyperVVMSetting -Name '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -DefaultInboundAction Allow -ErrorAction Stop
        Write-Success "Hyper-V Firewall configured for WSL2"
    } catch {
        Write-Warn "Cannot configure Hyper-V Firewall (may not apply): $_"
    }
}

function Invoke-Setup {
    Write-Header "Setting up network access for WSL2"

    foreach ($port in $Ports) {
        $bindAddresses = Get-PortBindAddress -Port $port

        if ($bindAddresses -contains "127.0.0.1" -and -not ($bindAddresses -contains "0.0.0.0")) {
            Add-PortProxy -Port $port
        }
        elseif (-not $bindAddresses) {
            Write-Warn "Port $port not listening - skipping port proxy (start service first)"
        }
        else {
            Write-Info "Port $port already listening on 0.0.0.0 - port proxy not needed"
        }

        Add-FirewallRule -Port $port
    }

    Enable-HyperVFirewall

    Write-Host ""
    Write-Success "Setup complete!"
    Write-Info "Test connection from WSL2:"
    Write-Host "    timeout 2 bash -c 'echo >/dev/tcp/localhost/$($Ports[0])' && echo OK || echo FAIL" -ForegroundColor Yellow
}

function Remove-PortProxy {
    param([int]$Port)

    Write-Info "Removing port proxy for port $Port..."

    if (-not (Test-PortProxy -Port $Port)) {
        Write-Warn "Port proxy for port $Port does not exist"
        return
    }

    $result = netsh interface portproxy delete v4tov4 listenport=$Port listenaddress=0.0.0.0 2>&1

    if ($LASTEXITCODE -eq 0) {
        Write-Success "Port proxy removed for port $Port"
    } else {
        Write-Fail "Failed to remove port proxy: $result"
    }
}

function Remove-FirewallRuleForPort {
    param([int]$Port)

    $ruleName = "WSL2 Port $Port"

    Write-Info "Removing Firewall rule for port $Port..."

    try {
        Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction Stop
        Write-Success "Firewall rule removed: $ruleName"
    } catch {
        Write-Warn "Rule '$ruleName' not found or already removed"
    }
}

function Invoke-Remove {
    Write-Header "Removing port proxy settings"

    foreach ($port in $Ports) {
        Remove-PortProxy -Port $port
        Remove-FirewallRuleForPort -Port $port
    }

    Write-Host ""
    Write-Success "Removal complete!"
}

# Main
if (-not ($Diagnose -or $Setup -or $Remove)) {
    $Diagnose = $true
}

if ($Diagnose) {
    Show-Diagnostics
}

if ($Setup) {
    Invoke-Setup
}

if ($Remove) {
    Invoke-Remove
}
