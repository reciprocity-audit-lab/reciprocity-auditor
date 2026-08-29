[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$OutputRoot,

    [Parameter(Mandatory = $false)]
    [string]$PythonPath
)

$ErrorActionPreference = 'Stop'
$exampleRoot = $PSScriptRoot
$projectRoot = Split-Path -Parent (Split-Path -Parent $exampleRoot)
$runner = Join-Path $projectRoot 'Run-ReciprocityAuditor.ps1'
$proposal = Join-Path $exampleRoot 'proposal.txt'
$fixture = Join-Path $projectRoot 'fixtures\analysis-valid.json'
$expectedPath = Join-Path $exampleRoot 'EXPECTED-SUMMARY.json'
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $projectRoot 'work\three-perspective-demo'
}
if (Test-Path -LiteralPath $OutputRoot) {
    throw 'OutputRoot already exists. Remove it only after reviewing its contents, or choose another path.'
}

function Invoke-Auditor {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    $invokeArgs = @()
    if (-not [string]::IsNullOrWhiteSpace($PythonPath)) {
        $invokeArgs += @('-PythonPath', $PythonPath)
    }
    $invokeArgs += $Arguments
    & $runner @invokeArgs
    if ($LASTEXITCODE -ne 0) {
        throw ('Reciprocity Auditor command failed: ' + ($Arguments -join ' '))
    }
}

New-Item -ItemType Directory -Path $OutputRoot | Out-Null
foreach ($perspective in @('justice', 'reversal', 'tower')) {
    $caseId = 'three-perspective-' + $perspective
    $caseDir = Join-Path $OutputRoot $perspective
    Invoke-Auditor @('prepare', '--input', $proposal, '--output', $caseDir, '--case-id', $caseId, '--perspective', $perspective)

    $analysis = Get-Content -LiteralPath $fixture -Raw | ConvertFrom-Json
    $analysis.audit_metadata.report_id = $caseId
    $json = $analysis | ConvertTo-Json -Depth 100
    [System.IO.File]::WriteAllText(
        (Join-Path $caseDir 'analysis.json'),
        $json + [Environment]::NewLine,
        (New-Object System.Text.UTF8Encoding -ArgumentList $false)
    )
    Invoke-Auditor @('validate', '--input', (Join-Path $caseDir 'analysis.json'))
    Invoke-Auditor @('record-run-config', '--case', $caseDir, '--evidence-source', 'unavailable')
}

$comparisonDir = Join-Path $OutputRoot 'comparison'
Invoke-Auditor @(
    'compare-perspectives',
    '--justice', (Join-Path $OutputRoot 'justice'),
    '--reversal', (Join-Path $OutputRoot 'reversal'),
    '--tower', (Join-Path $OutputRoot 'tower'),
    '--output', $comparisonDir
)

$actual = Get-Content -LiteralPath (Join-Path $comparisonDir 'perspective-comparison.json') -Raw | ConvertFrom-Json
$expected = Get-Content -LiteralPath $expectedPath -Raw | ConvertFrom-Json
foreach ($name in @('consistent', 'complementary', 'tension', 'direct_conflict', 'cannot_compare')) {
    if ($actual.summary.$name -ne $expected.$name) {
        throw ('Unexpected comparison count for {0}: expected {1}, got {2}' -f $name, $expected.$name, $actual.summary.$name)
    }
}

Write-Host ('DEMO PASS: output written to {0}' -f $OutputRoot)
Write-Host 'The fixed analyses are identical apart from case IDs; this demonstrates mechanics, not semantic independence or accuracy.'

