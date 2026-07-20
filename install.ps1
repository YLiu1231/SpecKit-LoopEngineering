[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("install", "project", "all", "doctor", "help")]
    [string]$Command = "install",

    [Parameter(Position = 1)]
    [string]$ProjectDir = ".",

    [string]$ClaudeHome,
    [string]$PythonBin
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $ClaudeHome) {
    if ($env:CLAUDE_HOME) {
        $ClaudeHome = $env:CLAUDE_HOME
    } else {
        $ClaudeHome = Join-Path $HOME ".claude"
    }
}
if (-not $PythonBin -and $env:PYTHON_BIN) {
    $PythonBin = $env:PYTHON_BIN
}

$script:PythonExe = $null
$script:PythonPrefix = @()

function Show-Usage {
    @"
Portable Spec Kit + Four-Loop Engineering for native Windows

Usage:
  .\install.ps1 install                  Install for the current user
  .\install.ps1 project [DIR]            Initialize/update one project
  .\install.ps1 all [DIR]                Install, then initialize project
  .\install.ps1 doctor                   Read-only installation check

Environment:
  SPECIFY_CLI_SOURCE=C:\path\pkg         Internal wheel, directory, or package source
  ALLOW_ONLINE_INSTALL=1                 Permit uv to download specify-cli
  SKIP_SPECIFY_CLI=1                    Skip Spec Kit CLI installation
  FORCE_CONSTITUTION=1                  Replace an established project constitution
  CLAUDE_HOME=C:\custom\path            Override %USERPROFILE%\.claude
  PYTHON_BIN=C:\path\python.exe         Override Python 3 executable

Native Windows requires Git for Windows. For OS-enforced strict sandboxing,
run Claude Code in WSL2 and use install.sh instead.
"@
}

function Test-PythonCandidate {
    param(
        [string]$Executable,
        [string[]]$Prefix = @()
    )
    try {
        & $Executable @Prefix -c "import sys; raise SystemExit(sys.version_info < (3, 9))" 2>$null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Find-Python {
    $candidates = @()
    if ($PythonBin) {
        $candidates += [PSCustomObject]@{
            Executable = $PythonBin
            Prefix = @()
        }
    }
    foreach ($name in @("python", "py", "python3")) {
        $found = Get-Command $name -ErrorAction SilentlyContinue
        if ($found) {
            $prefix = if ($name -eq "py") { @("-3") } else { @() }
            $candidates += [PSCustomObject]@{
                Executable = $found.Source
                Prefix = $prefix
            }
        }
    }

    foreach ($candidate in $candidates) {
        $executable = [string]$candidate.Executable
        $prefix = [string[]]$candidate.Prefix
        if (Test-PythonCandidate -Executable $executable -Prefix $prefix) {
            $script:PythonExe = $executable
            $script:PythonPrefix = $prefix
            return
        }
    }
    throw "Python 3.9+ was not found. Install it or set PYTHON_BIN."
}

function Invoke-Python {
    param([string[]]$Arguments)
    $pythonPrefix = $script:PythonPrefix
    & $script:PythonExe @pythonPrefix @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE."
    }
}

function Find-GitBash {
    if ($env:CLAUDE_CODE_GIT_BASH_PATH -and (Test-Path -LiteralPath $env:CLAUDE_CODE_GIT_BASH_PATH)) {
        return $env:CLAUDE_CODE_GIT_BASH_PATH
    }
    $paths = @()
    if ($env:ProgramFiles) {
        $paths += (Join-Path $env:ProgramFiles "Git\bin\bash.exe")
    }
    if (${env:ProgramFiles(x86)}) {
        $paths += (Join-Path ${env:ProgramFiles(x86)} "Git\bin\bash.exe")
    }
    if ($env:LOCALAPPDATA) {
        $paths += (Join-Path $env:LOCALAPPDATA "Programs\Git\bin\bash.exe")
    }
    foreach ($path in $paths) {
        if (Test-Path -LiteralPath $path) {
            return $path
        }
    }
    $git = Get-Command git -ErrorAction SilentlyContinue
    if ($git) {
        $gitRoot = Split-Path -Parent (Split-Path -Parent $git.Source)
        $gitBash = Join-Path $gitRoot "bin\bash.exe"
        if (Test-Path -LiteralPath $gitBash) {
            return $gitBash
        }
    }
    return $null
}

function Assert-Bundle {
    $required = @(
        "CLAUDE.md",
        "PROJECT-CONSTITUTION.md",
        "runtime\global_installer.py.md",
        "runtime\bootstrap_project.py.md",
        "runtime\loopctl.py.md",
        "runtime\run-python.sh.md",
        "runtime\security_guard.py.md",
        "runtime\policy.json.md",
        "runtime\workflow.yml.md"
    )
    foreach ($relative in $required) {
        $path = Join-Path $ScriptDir $relative
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Bundle is incomplete: $path"
        }
    }
}

function Invoke-External {
    param(
        [string]$Executable,
        [string[]]$Arguments
    )
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable failed with exit code $LASTEXITCODE."
    }
}

function Install-SpecifyCli {
    if ($env:SKIP_SPECIFY_CLI -eq "1") {
        Write-Host "Spec Kit CLI installation skipped by SKIP_SPECIFY_CLI=1."
        return
    }
    $specify = Get-Command specify -ErrorAction SilentlyContinue
    if ($specify) {
        Write-Host "Spec Kit CLI already available: $($specify.Source)"
        return
    }

    if ($env:SPECIFY_CLI_SOURCE) {
        $uv = Get-Command uv -ErrorAction SilentlyContinue
        if ($uv) {
            Invoke-External -Executable $uv.Source -Arguments @("tool", "install", $env:SPECIFY_CLI_SOURCE)
        } else {
            Invoke-Python -Arguments @("-m", "pip", "install", "--user", $env:SPECIFY_CLI_SOURCE)
        }
    } elseif ($env:ALLOW_ONLINE_INSTALL -eq "1") {
        $uv = Get-Command uv -ErrorAction SilentlyContinue
        if (-not $uv) {
            throw "ALLOW_ONLINE_INSTALL=1 requires uv. No download was attempted."
        }
        Write-Host "Installing specify-cli from the configured package source..."
        Invoke-External -Executable $uv.Source -Arguments @("tool", "install", "specify-cli")
    } else {
        Write-Warning "specify CLI is unavailable; no network request was made. Offline direct-skill mode remains available."
    }
}

function Install-GlobalRuntime {
    $gitBash = Find-GitBash
    if (-not $gitBash) {
        throw "Git Bash was not found. Install Git for Windows or set CLAUDE_CODE_GIT_BASH_PATH."
    }
    Write-Host "Git Bash: $gitBash"
    Install-SpecifyCli
    Invoke-Python -Arguments @(
        (Join-Path $ScriptDir "runtime\global_installer.py.md"),
        "--bundle-root", $ScriptDir,
        "--claude-home", $ClaudeHome,
        "--platform-mode", "native-windows"
    )
    Write-Host ""
    Write-Host "Global installation complete in native-Windows guarded mode."
    Write-Host "Restart Claude Code before using /loop-init or the Loop skills."
    Write-Warning "Native Windows has no Claude OS sandbox. Use WSL2 for strict OS-enforced isolation."
}

function Install-ProjectRuntime {
    if (-not (Test-Path -LiteralPath $ProjectDir -PathType Container)) {
        throw "Project directory does not exist: $ProjectDir"
    }
    $resolvedProject = (Resolve-Path -LiteralPath $ProjectDir).Path
    $bootstrap = Join-Path $ClaudeHome "loop-engineering\bootstrap_project.py"
    if (-not (Test-Path -LiteralPath $bootstrap -PathType Leaf)) {
        throw "Global runtime is missing. Run .\install.ps1 install first."
    }

    $offline = $false
    $specifyDir = Join-Path $resolvedProject ".specify"
    if (-not (Test-Path -LiteralPath $specifyDir -PathType Container)) {
        $specify = Get-Command specify -ErrorAction SilentlyContinue
        if (($env:SKIP_SPECIFY_CLI -ne "1") -and $specify) {
            Write-Host "Initializing Spec Kit in: $resolvedProject"
            Push-Location $resolvedProject
            try {
                Invoke-External -Executable $specify.Source -Arguments @(
                    "init", "--here", "--integration", "claude", "--script", "sh"
                )
            } finally {
                Pop-Location
            }
        } else {
            Write-Host "Using bundled offline Spec Kit project structure: $resolvedProject"
            $offline = $true
        }
    }

    $arguments = @($bootstrap, "--project-root", $resolvedProject)
    if ($offline) {
        $arguments += "--offline-init"
    }
    if ($env:FORCE_CONSTITUTION -eq "1") {
        $arguments += "--force-constitution"
    }
    Invoke-Python -Arguments $arguments

    $loopctl = Join-Path $resolvedProject ".specify\scripts\loopctl.py"
    Invoke-Python -Arguments @("-m", "py_compile", $loopctl)
    Invoke-Python -Arguments @($loopctl, "--help")
    Write-Host ""
    Write-Host "Project runtime ready: $resolvedProject"
    Write-Host "Start Claude in that directory and run /loop-requirements <feature>."
}

function Invoke-Doctor {
    $ok = $true
    $claude = Get-Command claude -ErrorAction SilentlyContinue
    if ($claude) {
        Write-Host "OK claude: $($claude.Source)"
    } else {
        Write-Error "MISSING claude executable" -ErrorAction Continue
        $ok = $false
    }
    $gitBash = Find-GitBash
    if ($gitBash) {
        Write-Host "OK Git Bash: $gitBash"
    } else {
        Write-Error "MISSING Git Bash" -ErrorAction Continue
        $ok = $false
    }
    $specify = Get-Command specify -ErrorAction SilentlyContinue
    if ($specify) {
        Write-Host "OK specify: $($specify.Source)"
    } else {
        Write-Host "OPTIONAL specify CLI missing; offline direct-skill mode remains available."
    }

    $required = @(
        "settings.json",
        "CLAUDE.md",
        "hooks\security_guard.py",
        "skills\loop-init\SKILL.md",
        "skills\loop-requirements\SKILL.md",
        "skills\loop-design\SKILL.md",
        "skills\loop-implementation\SKILL.md",
        "skills\loop-convergence\SKILL.md",
        "skills\speckit-specify\SKILL.md",
        "loop-engineering\bootstrap_project.py",
        "loop-engineering\run-python.sh"
    )
    foreach ($relative in $required) {
        $path = Join-Path $ClaudeHome $relative
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            Write-Host "OK $path"
        } else {
            Write-Error "MISSING $path" -ErrorAction Continue
            $ok = $false
        }
    }

    $settingsPath = Join-Path $ClaudeHome "settings.json"
    if (Test-Path -LiteralPath $settingsPath -PathType Leaf) {
        try {
            $settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
            if (($settings.sandbox.enabled -ne $false) -or
                ($settings.permissions.defaultMode -ne "default")) {
                throw "Expected native-Windows guarded settings."
            }
            Write-Host "OK native-Windows guarded mode (permission prompts + deny rules + Hook)"
        } catch {
            Write-Error "INVALID settings.json: $($_.Exception.Message)" -ErrorAction Continue
            $ok = $false
        }
    }
    if (-not $ok) {
        throw "Doctor found one or more problems."
    }
}

if ($Command -eq "help") {
    Show-Usage
    exit 0
}

Find-Python
Assert-Bundle

switch ($Command) {
    "install" { Install-GlobalRuntime }
    "project" { Install-ProjectRuntime }
    "all" {
        Install-GlobalRuntime
        Install-ProjectRuntime
    }
    "doctor" { Invoke-Doctor }
}
