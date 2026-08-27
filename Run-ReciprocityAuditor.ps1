[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$PythonPath,

    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$AuditorArgs
)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$sourceRoot = Join-Path $projectRoot 'src'

function Test-PythonCandidate {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,
        [string[]]$PrefixArgs = @()
    )

    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        return $null
    }

    try {
        $versionText = & $Executable @PrefixArgs -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>$null
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($versionText)) {
            return $null
        }
        $version = [version]($versionText.Trim())
        if ($version -lt [version]'3.12.0') {
            return $null
        }
        return [pscustomobject]@{
            Executable = $Executable
            PrefixArgs = $PrefixArgs
            Version = $version
        }
    }
    catch {
        return $null
    }
}

$candidates = @()
if (-not [string]::IsNullOrWhiteSpace($PythonPath)) {
    $candidates += [pscustomobject]@{ Executable = $PythonPath; PrefixArgs = @() }
}

$pythonCommand = Get-Command 'python.exe' -ErrorAction SilentlyContinue
if ($null -ne $pythonCommand) {
    $candidates += [pscustomobject]@{ Executable = $pythonCommand.Source; PrefixArgs = @() }
}

$pyCommand = Get-Command 'py.exe' -ErrorAction SilentlyContinue
if ($null -ne $pyCommand) {
    $candidates += [pscustomobject]@{ Executable = $pyCommand.Source; PrefixArgs = @('-3.12') }
}

$selected = $null
foreach ($candidate in $candidates) {
    $selected = Test-PythonCandidate -Executable $candidate.Executable -PrefixArgs $candidate.PrefixArgs
    if ($null -ne $selected) {
        break
    }
}

if ($null -eq $selected) {
    Write-Error 'Python 3.12 or later was not found. Specify python.exe with -PythonPath.'
    exit 3
}

Write-Host ('Running Reciprocity Auditor locally with Python {0}. No network access is used.' -f $selected.Version)

$previousConsoleOutputEncoding = [Console]::OutputEncoding
try {
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding -ArgumentList $false
    $bootstrap = "import runpy, sys; sys.path.insert(0, sys.argv.pop(1)); runpy.run_module('reciprocity_auditor', run_name='__main__')"
    & $selected.Executable @($selected.PrefixArgs) -B -X utf8 -c $bootstrap $sourceRoot @AuditorArgs
    $exitCode = $LASTEXITCODE
}
finally {
    [Console]::OutputEncoding = $previousConsoleOutputEncoding
}

exit $exitCode

