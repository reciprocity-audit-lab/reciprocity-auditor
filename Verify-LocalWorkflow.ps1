[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$PythonPath,

    [Parameter(Mandatory = $false)]
    [switch]$KeepWork
)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$runner = Join-Path $projectRoot 'Run-ReciprocityAuditor.ps1'
$fixture = Join-Path $projectRoot 'fixtures\analysis-valid.json'
$proposal = Join-Path $projectRoot 'fixtures\proposal.txt'
$verificationRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('reciprocity-auditor-verify-' + [guid]::NewGuid().ToString('N'))
$caseDir = Join-Path $verificationRoot 'case-001'

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

try {
    New-Item -ItemType Directory -Path $verificationRoot | Out-Null
    Invoke-Auditor @('prepare', '--input', $proposal, '--output', $caseDir, '--case-id', 'case-001')
    Copy-Item -LiteralPath $fixture -Destination (Join-Path $caseDir 'analysis.json')
    Invoke-Auditor @('validate', '--input', (Join-Path $caseDir 'analysis.json'))
    Invoke-Auditor @('render', '--input', (Join-Path $caseDir 'analysis.json'))
    Invoke-Auditor @('review', '--case', $caseDir, '--state', 'reviewed', '--reviewer-label', 'verification-reviewer')
    Invoke-Auditor @('status', '--case', $caseDir)

    $review = Get-Content -LiteralPath (Join-Path $caseDir 'review.json') -Raw | ConvertFrom-Json
    if ($review.review_state -ne 'reviewed' -or $review.review_scope -ne 'audit_report') {
        throw 'The final review record did not reach the expected reviewed audit-report state.'
    }
    Write-Host 'VERIFICATION PASS: prepare -> validate -> render -> review -> status'
    Write-Host 'This verifies the local workflow, not semantic audit accuracy.'
    if ($KeepWork) {
        Write-Host ('Temporary verification files kept at: {0}' -f $verificationRoot)
    }
}
finally {
    if (-not $KeepWork -and (Test-Path -LiteralPath $verificationRoot)) {
        Remove-Item -LiteralPath $verificationRoot -Recurse -Force
    }
}

