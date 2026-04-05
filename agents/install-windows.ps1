<#
==============================================================================
Name:        Philipp Fischer
Kontakt:     p.fischer@itconex.de
Version:     2026.02.20.19.00.09
Beschreibung: LogBot Agent v2026.02.20.19.00.09 - Windows Installer
              Start per Menue: 1=Install/Update, 2=Tests senden,
              3=Vollstaendig deinstallieren (Task + Daten, PS1 bleibt)
              Modi: UDP Syslog (klassisch) oder HTTPS (verschluesselt + auth)
==============================================================================
#>

#Requires -RunAsAdministrator

param(
    [string]$ServerFqdn = "",
    [string]$ServerIP = "",
    [int]$ServerPort = 0
)

$ErrorActionPreference = "Stop"

# Konfiguration
$INSTALL_DIR = "$env:ProgramData\LogBot-Agent"
$SCRIPT_NAME = "LogBotAgent.ps1"
$TASK_NAME = "LogBotAgent"
$AGENT_VERSION = "2026.02.20.19.00.09"

# ==============================================================================
# Hilfsfunktionen
# ==============================================================================

function Write-LogInfo($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-LogSuccess($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-LogWarn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-LogError($msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red }

function Test-ServerReachable {
    param([string]$TargetHost, [int]$Port, [string]$Label)
    Write-LogInfo "Pruefe $Label ($TargetHost`:$Port)..."
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $result = $tcp.BeginConnect($TargetHost, $Port, $null, $null)
        $wait = $result.AsyncWaitHandle.WaitOne(3000, $false)
        if ($wait -and $tcp.Connected) {
            $tcp.Close()
            Write-LogSuccess "$Label erreichbar"
            return $true
        }
        $tcp.Close()
    } catch {}
    Write-LogWarn "$Label NICHT erreichbar"
    return $false
}

function Test-DnsResolve {
    param([string]$Fqdn)
    try {
        $resolved = [System.Net.Dns]::GetHostAddresses($Fqdn)
        if ($resolved.Count -gt 0) {
            Write-LogSuccess "DNS aufgeloest: $Fqdn -> $($resolved[0])"
            return $true
        }
    } catch {}
    Write-LogWarn "DNS-Aufloesung fehlgeschlagen: $Fqdn"
    return $false
}

# ==============================================================================
# Agent Script - Syslog Modus (UDP, wie bisher)
# ==============================================================================

$AgentScriptSyslog = @'
<#
==============================================================================
LogBot Agent - Windows Event Log Forwarder (Syslog/UDP)
==============================================================================
#>
param([string]$ConfigFile = "$PSScriptRoot\config.json")

if (Test-Path $ConfigFile) {
    $Config = Get-Content $ConfigFile -Raw | ConvertFrom-Json
} else { Write-Error "Konfiguration nicht gefunden: $ConfigFile"; exit 1 }

$ServerFqdn = $Config.server_fqdn
$ServerIP = $Config.server_ip
$ServerPort = $Config.server_port
$LogSources = $Config.log_sources
$MinLevel = $Config.min_level
$Hostname = if ($Config.hostname) { $Config.hostname } else { $env:COMPUTERNAME }

$LevelMap = @{ 1=2; 2=3; 3=4; 4=6; 0=6; 5=7 }
$MinLevelNum = @{ "debug"=7; "info"=6; "notice"=5; "warning"=4; "error"=3; "critical"=2 }[$MinLevel]
if (-not $MinLevelNum) { $MinLevelNum = 6 }

$UdpClient = New-Object System.Net.Sockets.UdpClient

# Aktiven Server ermitteln (FQDN first, IP fallback)
function Get-ActiveServer {
    if ($ServerFqdn) {
        try {
            [System.Net.Dns]::GetHostAddresses($ServerFqdn) | Out-Null
            return $ServerFqdn
        } catch {}
    }
    if ($ServerIP) { return $ServerIP }
    return $ServerFqdn
}

function Send-Syslog {
    param([string]$Message, [int]$Severity = 6, [string]$Source = "EventLog")
    $Priority = 8 + $Severity
    $Timestamp = Get-Date -Format "MMM dd HH:mm:ss"
    $SyslogMsg = "<$Priority>$Timestamp $Hostname $Source`: $Message"
    $Target = Get-ActiveServer
    try {
        $Bytes = [System.Text.Encoding]::UTF8.GetBytes($SyslogMsg)
        $UdpClient.Send($Bytes, $Bytes.Length, $Target, $ServerPort) | Out-Null
    } catch { Write-Warning "Sendefehler ($Target): $_" }
}

function Process-Event {
    param($Event, [string]$LogName)
    $Level = $LevelMap[[int]$Event.Level]
    if (-not $Level) { $Level = 6 }
    if ($Level -gt $MinLevelNum) { return }
    $Message = $Event.Message
    if (-not $Message) { $Message = "EventID: $($Event.Id)" }
    $Message = ($Message -replace "`r`n|`n|`r", " ").Substring(0, [Math]::Min(1024, $Message.Length))
    Send-Syslog -Message $Message -Severity $Level -Source "$LogName/$($Event.ProviderName)"
}

Write-Host "LogBot Agent (Syslog) gestartet - Server: $(Get-ActiveServer):$ServerPort"
$StartTime = (Get-Date).AddMinutes(-1)

while ($true) {
    foreach ($LogName in $LogSources) {
        try {
            $Events = Get-WinEvent -LogName $LogName -MaxEvents 100 -ErrorAction SilentlyContinue |
                      Where-Object { $_.TimeCreated -gt $StartTime }
            foreach ($Event in $Events) { Process-Event -Event $Event -LogName $LogName }
        } catch {}
    }
    $StartTime = Get-Date
    Start-Sleep -Seconds 5
}
'@

# ==============================================================================
# Agent Script - HTTPS Modus (verschluesselt + authentifiziert, ALLE Logs)
# ==============================================================================

$AgentScriptHttps = @'
<#
==============================================================================
LogBot Agent - Windows Event Log Forwarder (HTTPS + Token Auth)
Sammelt ALLE verfuegbaren Event Logs und sendet sie verschluesselt
==============================================================================
#>
param([string]$ConfigFile = "$PSScriptRoot\config.json")

if (Test-Path $ConfigFile) {
    $Config = Get-Content $ConfigFile -Raw | ConvertFrom-Json
} else { Write-Error "Konfiguration nicht gefunden: $ConfigFile"; exit 1 }

$ServerFqdn = $Config.server_fqdn
$ServerIP = $Config.server_ip
$ServerPort = $Config.server_port
$AgentToken = $Config.agent_token
$SkipTlsVerify = $Config.skip_tls_verify
$MinLevel = $Config.min_level
$Hostname = if ($Config.hostname) { $Config.hostname } else { $env:COMPUTERNAME }

$LevelMap = @{ 1="critical"; 2="error"; 3="warning"; 4="info"; 0="info"; 5="debug" }
$LevelPriority = @{ "debug"=7; "info"=6; "notice"=5; "warning"=4; "error"=3; "critical"=2 }
$MinLevelNum = $LevelPriority[$MinLevel]
if (-not $MinLevelNum) { $MinLevelNum = 6 }

# TLS-Zertifikat-Pruefung deaktivieren wenn gewuenscht
if ($SkipTlsVerify) {
    [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
    if ($PSVersionTable.PSVersion.Major -ge 6) {
        $script:TlsParam = @{ SkipCertificateCheck = $true }
    } else {
        $script:TlsParam = @{}
        Add-Type @"
using System.Net;
using System.Net.Security;
using System.Security.Cryptography.X509Certificates;
public class TrustAll {
    public static void Enable() {
        ServicePointManager.ServerCertificateValidationCallback = delegate { return true; };
    }
}
"@
        [TrustAll]::Enable()
    }
} else {
    $script:TlsParam = @{}
}

$Headers = @{
    "Authorization" = "Bearer $AgentToken"
    "Content-Type" = "application/json"
}

# Aktive Server-URL ermitteln (FQDN first, IP fallback)
$script:CurrentUrl = $null

function Get-IngestUrl {
    # Wenn aktuelle URL funktioniert, beibehalten
    if ($script:CurrentUrl) { return $script:CurrentUrl }

    # FQDN versuchen
    if ($ServerFqdn) {
        $url = "https://${ServerFqdn}:${ServerPort}/api/agents/ingest"
        if ($ServerPort -eq 443) { $url = "https://${ServerFqdn}/api/agents/ingest" }
        try {
            [System.Net.Dns]::GetHostAddresses($ServerFqdn) | Out-Null
            $script:CurrentUrl = $url
            return $url
        } catch {
            Write-Warning "FQDN nicht aufloesbar: $ServerFqdn - Fallback auf IP"
        }
    }

    # IP Fallback
    if ($ServerIP) {
        $url = "https://${ServerIP}:${ServerPort}/api/agents/ingest"
        if ($ServerPort -eq 443) { $url = "https://${ServerIP}/api/agents/ingest" }
        $script:CurrentUrl = $url
        return $url
    }

    return $null
}

function Send-LogBatch {
    param([array]$Events)
    if ($Events.Count -eq 0) { return }

    $url = Get-IngestUrl
    if (-not $url) { Write-Warning "Kein Server erreichbar"; return }

    $body = @{
        hostname = $Hostname
        events = $Events
    } | ConvertTo-Json -Depth 3

    try {
        Invoke-RestMethod -Uri $url -Method POST -Headers $Headers -Body $body @script:TlsParam | Out-Null
    } catch {
        Write-Warning "Sendefehler ($url): $_"
        # URL zuruecksetzen fuer naechsten Versuch (Fallback-Logik)
        $script:CurrentUrl = $null
    }
}

# Alle verfuegbaren Event Logs ermitteln
function Get-ActiveLogNames {
    $logs = Get-WinEvent -ListLog * -ErrorAction SilentlyContinue |
            Where-Object { $_.RecordCount -gt 0 } |
            Select-Object -ExpandProperty LogName
    return $logs
}

Write-Host "LogBot Agent (HTTPS) gestartet"
Write-Host "Hostname: $Hostname"
Write-Host "Ermittle alle verfuegbaren Event Logs..."

$AllLogs = Get-ActiveLogNames
Write-Host "Gefunden: $($AllLogs.Count) aktive Log-Kanaele"
Write-Host "---"

$StartTime = (Get-Date).AddMinutes(-1)
# Log-Liste alle 5 Minuten aktualisieren
$LogRefreshTime = Get-Date

while ($true) {
    # Log-Kanaele regelmaessig aktualisieren (neue Logs koennen hinzukommen)
    if ((Get-Date) -gt $LogRefreshTime.AddMinutes(5)) {
        $AllLogs = Get-ActiveLogNames
        $LogRefreshTime = Get-Date
    }

    $Batch = @()

    foreach ($LogName in $AllLogs) {
        try {
            $Events = Get-WinEvent -LogName $LogName -MaxEvents 100 -ErrorAction SilentlyContinue |
                      Where-Object { $_.TimeCreated -gt $StartTime }

            foreach ($Event in $Events) {
                $Level = $LevelMap[[int]$Event.Level]
                if (-not $Level) { $Level = "info" }
                $LevelNum = $LevelPriority[$Level]
                if (-not $LevelNum) { $LevelNum = 6 }
                if ($LevelNum -gt $MinLevelNum) { continue }

                $Message = $Event.Message
                if (-not $Message) { $Message = "EventID: $($Event.Id)" }
                $Message = ($Message -replace "`r`n|`n|`r", " ").Substring(0, [Math]::Min(2048, $Message.Length))

                $Batch += @{
                    level = $Level
                    source = "$LogName/$($Event.ProviderName)"
                    message = $Message
                }

                # Batch senden wenn 50 erreicht
                if ($Batch.Count -ge 50) {
                    Send-LogBatch -Events $Batch
                    $Batch = @()
                    Start-Sleep -Milliseconds 500
                }
            }
        } catch {}
    }

    # Restliche Events senden
    if ($Batch.Count -gt 0) {
        Send-LogBatch -Events $Batch
    }

    $StartTime = Get-Date
    Start-Sleep -Seconds 5
}
'@

# ==============================================================================
# Installation
# ==============================================================================

function Install-Agent {
    Write-LogInfo "Installiere LogBot Agent..."

    # Verzeichnis erstellen
    if (-not (Test-Path $INSTALL_DIR)) {
        New-Item -ItemType Directory -Path $INSTALL_DIR -Force | Out-Null
    }

    # --- Modus-Auswahl ---
    Write-Host ""
    Write-Host "Verbindungsmodus:"
    Write-Host "  1) Standard (UDP Syslog) - unverschluesselt"
    Write-Host "  2) Agent-basiert (HTTPS) - verschluesselt + authentifiziert"
    $ModeChoice = Read-Host "Auswahl [1]"

    $Mode = if ($ModeChoice -eq "2") { "https" } else { "syslog" }

    # --- Server-Adressen ---
    Write-Host ""
    if ([string]::IsNullOrEmpty($ServerFqdn)) {
        $ServerFqdn = Read-Host "LogBot Server FQDN (z.B. logbot.example.com)"
    }
    if ([string]::IsNullOrEmpty($ServerIP)) {
        $ServerIP = Read-Host "LogBot Server IP als Fallback (z.B. 192.168.1.10)"
    }

    if ([string]::IsNullOrEmpty($ServerFqdn) -and [string]::IsNullOrEmpty($ServerIP)) {
        Write-LogError "Mindestens FQDN oder IP muss angegeben werden!"
        exit 1
    }

    # --- Port ---
    if ($ServerPort -eq 0) {
        $DefaultPort = if ($Mode -eq "https") { 443 } else { 514 }
        $PortInput = Read-Host "Server Port [$DefaultPort]"
        if ([string]::IsNullOrEmpty($PortInput)) {
            $ServerPort = $DefaultPort
        } else {
            $ServerPort = [int]$PortInput
        }
    }

    # --- Erreichbarkeitscheck ---
    Write-Host ""
    Write-LogInfo "Pruefe Server-Erreichbarkeit..."

    $FqdnOk = $false
    $IpOk = $false

    if (-not [string]::IsNullOrEmpty($ServerFqdn)) {
        $DnsOk = Test-DnsResolve -Fqdn $ServerFqdn
        if ($DnsOk) {
            $FqdnOk = Test-ServerReachable -TargetHost $ServerFqdn -Port $ServerPort -Label "FQDN"
        }
    }

    if (-not [string]::IsNullOrEmpty($ServerIP)) {
        $IpOk = Test-ServerReachable -TargetHost $ServerIP -Port $ServerPort -Label "IP"
    }

    if (-not $FqdnOk -and -not $IpOk) {
        Write-LogError "Server weder ueber FQDN noch IP erreichbar!"
        $Continue = Read-Host "Trotzdem fortfahren? (j/N)"
        if ($Continue -ne "j") { exit 1 }
    }

    # --- Modus-spezifische Konfiguration ---
    $AgentToken = ""
    $SkipTlsVerify = $false
    $LogSources = @()

    if ($Mode -eq "https") {
        # Token abfragen
        Write-Host ""
        $AgentToken = Read-Host "Agent-Token (vom Admin im Web-UI erstellt)"
        if ([string]::IsNullOrEmpty($AgentToken)) {
            Write-LogError "Agent-Token ist erforderlich fuer HTTPS-Modus!"
            exit 1
        }

        # Token validieren
        Write-LogInfo "Validiere Token..."
        $TestUrl = $null
        if ($FqdnOk) {
            $TestUrl = if ($ServerPort -eq 443) { "https://$ServerFqdn/api" } else { "https://${ServerFqdn}:${ServerPort}/api" }
        } elseif ($IpOk) {
            $TestUrl = if ($ServerPort -eq 443) { "https://$ServerIP/api" } else { "https://${ServerIP}:${ServerPort}/api" }
        }

        if ($TestUrl) {
            try {
                Invoke-RestMethod -Uri $TestUrl -Method GET -TimeoutSec 5 | Out-Null
                Write-LogSuccess "Server-API erreichbar"
            } catch {
                if ($_.Exception.Message -match "SSL|certificate|trust") {
                    Write-LogWarn "TLS-Zertifikat nicht vertrauenswuerdig"
                    $SkipChoice = Read-Host "Selbstsignierte Zertifikate akzeptieren? (j/N)"
                    if ($SkipChoice -eq "j") {
                        $SkipTlsVerify = $true
                        # Temporaer fuer Validierung deaktivieren
                        [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
                    }
                } else {
                    Write-LogWarn "API-Check fehlgeschlagen: $_"
                }
            }
        }

        # HTTPS-Modus: ALLE Logs (Default)
        $LogSources = @("*")
        Write-LogInfo "HTTPS-Modus: Alle Event Logs werden gesammelt"

    } else {
        # Syslog-Modus: Log-Auswahl wie bisher
        Write-Host ""
        Write-Host "Welche Event Logs sollen weitergeleitet werden?"
        Write-Host "  1) Application + System (Standard)"
        Write-Host "  2) Application + System + Security"
        Write-Host "  3) Nur Application"
        $LogChoice = Read-Host "Auswahl [1]"

        $LogSources = switch ($LogChoice) {
            "2" { @("Application", "System", "Security") }
            "3" { @("Application") }
            default { @("Application", "System") }
        }
    }

    # Min-Level
    Write-Host ""
    Write-Host "Minimales Log-Level:"
    Write-Host "  1) Alle (info und hoeher)"
    Write-Host "  2) Nur Warnungen (warning und hoeher)"
    Write-Host "  3) Nur Fehler (error und hoeher)"
    $LevelChoice = Read-Host "Auswahl [1]"

    $MinLevel = switch ($LevelChoice) {
        "2" { "warning" }
        "3" { "error" }
        default { "info" }
    }

    # --- Agent Script speichern ---
    if ($Mode -eq "https") {
        $AgentScriptHttps | Set-Content "$INSTALL_DIR\$SCRIPT_NAME" -Encoding UTF8
    } else {
        $AgentScriptSyslog | Set-Content "$INSTALL_DIR\$SCRIPT_NAME" -Encoding UTF8
    }

    # --- Konfiguration speichern ---
    $Config = @{
        mode = $Mode
        server_fqdn = $ServerFqdn
        server_ip = $ServerIP
        server_port = $ServerPort
        hostname = $env:COMPUTERNAME
        log_sources = $LogSources
        min_level = $MinLevel
    }

    if ($Mode -eq "https") {
        $Config.agent_token = $AgentToken
        $Config.skip_tls_verify = $SkipTlsVerify
    }

    $Config | ConvertTo-Json | Set-Content "$INSTALL_DIR\config.json" -Encoding UTF8

    Write-LogSuccess "Agent installiert: $INSTALL_DIR (Modus: $Mode)"
}

function Install-ScheduledTask {
    Write-LogInfo "Erstelle Scheduled Task..."

    $Existing = Get-ScheduledTask -TaskName $TASK_NAME -ErrorAction SilentlyContinue
    if ($Existing) {
        Unregister-ScheduledTask -TaskName $TASK_NAME -Confirm:$false
    }

    $Action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$INSTALL_DIR\$SCRIPT_NAME`"" `
        -WorkingDirectory $INSTALL_DIR

    $Trigger = New-ScheduledTaskTrigger -AtStartup

    $Settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit (New-TimeSpan -Days 365)

    $Principal = New-ScheduledTaskPrincipal `
        -UserId "SYSTEM" `
        -LogonType ServiceAccount `
        -RunLevel Highest

    Register-ScheduledTask `
        -TaskName $TASK_NAME `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Description "LogBot Agent v$AGENT_VERSION - Windows Event Log Forwarder" | Out-Null

    Write-LogSuccess "Scheduled Task erstellt"
}

function Start-Agent {
    Write-LogInfo "Starte Agent..."
    Start-ScheduledTask -TaskName $TASK_NAME

    Start-Sleep -Seconds 3

    $Task = Get-ScheduledTask -TaskName $TASK_NAME
    if ($Task.State -eq "Running") {
        Write-LogSuccess "Agent laeuft"
    } else {
        Write-LogWarn "Agent-Status: $($Task.State)"
    }
}

# ==============================================================================
# Test
# ==============================================================================

function Send-TestMessage {
    Write-LogInfo "Sende Test-Nachrichten..."

    $ConfigFile = "$INSTALL_DIR\config.json"
    if (-not (Test-Path $ConfigFile)) {
        Write-LogError "Agent nicht installiert!"
        exit 1
    }

    $Config = Get-Content $ConfigFile -Raw | ConvertFrom-Json
    $Hostname = $env:COMPUTERNAME

    if ($Config.mode -eq "https") {
        # HTTPS-Test
        $Headers = @{
            "Authorization" = "Bearer $($Config.agent_token)"
            "Content-Type" = "application/json"
        }

        $TlsParam = @{}
        if ($Config.skip_tls_verify) {
            [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
            if ($PSVersionTable.PSVersion.Major -ge 6) {
                $TlsParam = @{ SkipCertificateCheck = $true }
            }
        }

        # Server-URL ermitteln
        $BaseUrl = $null
        if ($Config.server_fqdn) {
            try {
                [System.Net.Dns]::GetHostAddresses($Config.server_fqdn) | Out-Null
                $BaseUrl = if ($Config.server_port -eq 443) { "https://$($Config.server_fqdn)" } else { "https://$($Config.server_fqdn):$($Config.server_port)" }
            } catch {}
        }
        if (-not $BaseUrl -and $Config.server_ip) {
            $BaseUrl = if ($Config.server_port -eq 443) { "https://$($Config.server_ip)" } else { "https://$($Config.server_ip):$($Config.server_port)" }
        }

        $body = @{
            hostname = $Hostname
            events = @(
                @{ level = "info"; source = "logbot-test"; message = "LogBot Agent Test - Info Nachricht" },
                @{ level = "warning"; source = "logbot-test"; message = "LogBot Agent Test - Warning Nachricht" },
                @{ level = "error"; source = "logbot-test"; message = "LogBot Agent Test - Error Nachricht" }
            )
        } | ConvertTo-Json -Depth 3

        try {
            $response = Invoke-RestMethod -Uri "$BaseUrl/api/agents/ingest" -Method POST -Headers $Headers -Body $body @TlsParam
            Write-LogSuccess "3 Test-Nachrichten gesendet via HTTPS (akzeptiert: $($response.accepted))"
        } catch {
            Write-LogError "HTTPS-Test fehlgeschlagen: $_"
        }
    } else {
        # Syslog-Test (UDP)
        $UdpClient = New-Object System.Net.Sockets.UdpClient
        $Target = if ($Config.server_fqdn) { $Config.server_fqdn } else { $Config.server_ip }

        $Messages = @(
            @{ Level = 6; Text = "LogBot Agent Test - Info Nachricht" },
            @{ Level = 4; Text = "LogBot Agent Test - Warning Nachricht" },
            @{ Level = 3; Text = "LogBot Agent Test - Error Nachricht" }
        )

        foreach ($Msg in $Messages) {
            $Priority = 8 + $Msg.Level
            $Timestamp = Get-Date -Format "MMM dd HH:mm:ss"
            $SyslogMsg = "<$Priority>$Timestamp $Hostname logbot-test: $($Msg.Text)"
            try {
                $Bytes = [System.Text.Encoding]::UTF8.GetBytes($SyslogMsg)
                $UdpClient.Send($Bytes, $Bytes.Length, $Target, $Config.server_port) | Out-Null
                Write-Host "[SENT] $($Msg.Text)" -ForegroundColor Green
            } catch {
                Write-Host "[ERROR] $($Msg.Text): $_" -ForegroundColor Red
            }
        }
        $UdpClient.Close()
        Write-LogSuccess "Test abgeschlossen"
    }

    Write-LogInfo "Pruefe LogBot Web-Interface ob die Nachrichten angekommen sind"
}

# ==============================================================================
# Deinstallation
# ==============================================================================

function Stop-AgentProcesses {
    Write-LogInfo "Pruefe laufende Agent-Prozesse..."
    try {
        $processes = Get-CimInstance -ClassName Win32_Process -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -and $_.CommandLine -match [regex]::Escape("$INSTALL_DIR\$SCRIPT_NAME") }

        foreach ($proc in $processes) {
            Write-LogInfo "Beende Prozess PID $($proc.ProcessId)"
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
        }

        if (-not $processes) {
            Write-LogInfo "Keine laufenden Agent-Prozesse gefunden"
        }
    } catch {
        Write-LogWarn "Konnte Prozesse nicht ermitteln/stoppen: $_"
    }
}

function Remove-ScheduledTaskForce {
    Write-LogInfo "Entferne Scheduled Task..."

    # Versuche regulär über ScheduledTasks-Modul
    $task = Get-ScheduledTask -TaskName $TASK_NAME -ErrorAction SilentlyContinue
    if ($task) {
        try { Disable-ScheduledTask -TaskName $TASK_NAME -ErrorAction SilentlyContinue | Out-Null } catch {}
        try { Stop-ScheduledTask -TaskName $TASK_NAME -ErrorAction SilentlyContinue } catch {}
        try {
            Unregister-ScheduledTask -TaskName $TASK_NAME -Confirm:$false
            Write-LogInfo "Scheduled Task entfernt (Unregister-ScheduledTask)"
        } catch {
            Write-LogWarn "Unregister-ScheduledTask fehlgeschlagen: $_"
        }
    } else {
        Write-LogInfo "Kein Scheduled Task gefunden (Get-ScheduledTask)"
    }

    # Fallback via schtasks (deckt evtl. Ghost-Eintraege ab)
    foreach ($tn in @($TASK_NAME, "\$TASK_NAME")) {
        try {
            schtasks.exe /Delete /TN $tn /F 2>$null | Out-Null
        } catch {}
    }
}

function Uninstall-Agent {
    Write-LogInfo "Deinstalliere LogBot Agent..."

    $taskFile = Join-Path $env:SystemRoot "System32\\Tasks\\$TASK_NAME"
    $errors = @()

    # Laufende Agent-Instanzen beenden (vor Filesystem-Delete)
    Stop-AgentProcesses

    Remove-ScheduledTaskForce

    # Falls Task-Datei liegen bleibt, manuell loeschen
    if (Test-Path $taskFile) {
        try {
            Remove-Item -Path $taskFile -Force
            Write-LogInfo "Task-Datei aus Aufgabenplaner entfernt"
        } catch {
            Write-LogWarn "Konnte Task-Datei nicht entfernen: $_"
            $errors += "Task-Datei"
        }
    }

    # Mehrere moegliche Installationspfade (Altlasten)
    $installPaths = @(
        $INSTALL_DIR,
        "$env:ProgramData\\LogBotAgent",
        "$env:ProgramFiles\\LogBot-Agent",
        "$env:ProgramFiles(x86)\\LogBot-Agent"
    ) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique

    if ($installPaths.Count -eq 0) {
        Write-LogInfo "Keine Installationsverzeichnisse gefunden"
    }

    foreach ($path in $installPaths) {
        try {
            Remove-Item -Path $path -Recurse -Force
            Write-LogInfo "Verzeichnis entfernt: $path"
        } catch {
            Write-LogWarn "Konnte Verzeichnis nicht entfernen: $path - $_"
            $errors += "Verzeichnis $path"
        }
    }

    # Abschlusspruefung
    $stillTask = Get-ScheduledTask -TaskName $TASK_NAME -ErrorAction SilentlyContinue
    $stillFiles = Test-Path $INSTALL_DIR
    $stillTaskFile = Test-Path $taskFile

    if ($stillTask -or $stillFiles -or $stillTaskFile -or $errors.Count -gt 0) {
        Write-LogWarn "Deinstallation unvollstaendig. Offene Reste: $($errors -join ', ')"
        if ($stillTask) { Write-LogWarn "Aufgabenplaner-Eintrag existiert noch." }
        if ($stillTaskFile) { Write-LogWarn "Task-Datei unter $taskFile existiert noch." }
        if ($stillFiles) { Write-LogWarn "Verzeichnis $INSTALL_DIR existiert noch." }
        return
    }

    Write-LogSuccess "LogBot Agent vollstaendig deinstalliert"
}

# ==============================================================================
# Zusammenfassung
# ==============================================================================

function Show-Summary {
    Write-Host ""
    Write-Host "==============================================" -ForegroundColor Green
    Write-Host "  LogBot Agent v$AGENT_VERSION installiert!" -ForegroundColor Green
    Write-Host "==============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Installation: $INSTALL_DIR"
    Write-Host ""
    Write-Host "Nuetzliche Befehle (PowerShell als Admin):"
    Write-Host "  Get-ScheduledTask -TaskName $TASK_NAME        # Status"
    Write-Host "  Start-ScheduledTask -TaskName $TASK_NAME      # Starten"
    Write-Host "  Stop-ScheduledTask -TaskName $TASK_NAME       # Stoppen"
    Write-Host ""
    Write-Host "Test:"
    Write-Host "  Installer starten und Option 2 waehlen"
    Write-Host ""
    Write-Host "Deinstallation:"
    Write-Host "  Installer starten und Option 3 waehlen"
    Write-Host ""
}

# ==============================================================================
# Menue
# ==============================================================================

function Show-MainMenu {
    Write-Host ""
    Write-Host "Was moechtest du tun?"
    Write-Host "  1) Installieren / Neu installieren"
    Write-Host "  2) Testnachrichten senden (Installation erforderlich)"
    Write-Host "  3) Vollstaendig deinstallieren (alles ausser diesem Script wird entfernt)"
    Write-Host "  4) Abbrechen"
    $choice = Read-Host "Auswahl [1]"

    switch ($choice) {
        "2" { return "test" }
        "3" { return "uninstall" }
        "4" { return "exit" }
        default { return "install" }
    }
}

# ==============================================================================
# Hauptprogramm
# ==============================================================================

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  LogBot Agent v$AGENT_VERSION - Windows" -ForegroundColor Cyan
Write-Host "  (PowerShell Event Log Forwarder)" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

$Action = Show-MainMenu

switch ($Action) {
    "uninstall" { Uninstall-Agent }
    "test" { Send-TestMessage }
    "install" {
        Install-Agent
        Install-ScheduledTask
        Start-Agent
        Send-TestMessage
        Show-Summary
    }
    default { Write-LogInfo "Abgebrochen." }
}
