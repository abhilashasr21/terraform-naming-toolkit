[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Container })]
    [string] $RepoPath,

    [Parameter()]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string] $PolicyPath,

    [Parameter()]
    [string] $OutputPath = (Join-Path (Get-Location) 'terraform-resource-inventory.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Remove-HclComments {
    param([Parameter(Mandatory)][string] $Content)

    $result = [System.Text.StringBuilder]::new($Content.Length)
    $state = 'normal'
    $escaped = $false

    for ($index = 0; $index -lt $Content.Length; $index++) {
        $character = $Content[$index]
        $next = if ($index + 1 -lt $Content.Length) { $Content[$index + 1] } else { [char]0 }

        switch ($state) {
            'string' {
                [void] $result.Append($character)
                if ($escaped) {
                    $escaped = $false
                }
                elseif ($character -eq '\') {
                    $escaped = $true
                }
                elseif ($character -eq '"') {
                    $state = 'normal'
                }
            }
            'line-comment' {
                if ($character -eq "`n") {
                    [void] $result.Append($character)
                    $state = 'normal'
                }
                else {
                    [void] $result.Append(' ')
                }
            }
            'block-comment' {
                if ($character -eq '*' -and $next -eq '/') {
                    [void] $result.Append(' ')
                    [void] $result.Append(' ')
                    $index++
                    $state = 'normal'
                }
                elseif ($character -eq "`n") {
                    [void] $result.Append($character)
                }
                else {
                    [void] $result.Append(' ')
                }
            }
            default {
                if ($character -eq '"') {
                    [void] $result.Append($character)
                    $state = 'string'
                }
                elseif ($character -eq '#' -or ($character -eq '/' -and $next -eq '/')) {
                    [void] $result.Append(' ')
                    if ($character -eq '/') {
                        [void] $result.Append(' ')
                        $index++
                    }
                    $state = 'line-comment'
                }
                elseif ($character -eq '/' -and $next -eq '*') {
                    [void] $result.Append(' ')
                    [void] $result.Append(' ')
                    $index++
                    $state = 'block-comment'
                }
                else {
                    [void] $result.Append($character)
                }
            }
        }
    }

    return $result.ToString()
}

function Get-LineNumber {
    param(
        [Parameter(Mandatory)][string] $Content,
        [Parameter(Mandatory)][int] $Offset
    )

    if ($Offset -eq 0) {
        return 1
    }

    return ([regex]::Matches($Content.Substring(0, $Offset), "`n").Count + 1)
}

$resolvedRepoPath = (Resolve-Path -LiteralPath $RepoPath).Path
$policyRuleByTerraformType = @{}

if ($PolicyPath) {
    $policy = Get-Content -LiteralPath $PolicyPath -Raw | ConvertFrom-Json -Depth 100
    foreach ($ruleProperty in $policy.rules.PSObject.Properties) {
        $terraformTypes = @($ruleProperty.Value.terraform_resource_types)
        foreach ($terraformType in $terraformTypes) {
            if ($terraformType) {
                $policyRuleByTerraformType[$terraformType] = [ordered]@{
                    rule   = $ruleProperty.Name
                    status = $ruleProperty.Value.status
                }
            }
        }
    }
}

$blocks = [System.Collections.Generic.List[object]]::new()
$blockPattern = [regex]::new(
    '(?m)\b(?<kind>resource|data)\s+"(?<type>[^"]+)"\s+"(?<label>[^"]+)"\s*\{|\b(?<moduleKind>module)\s+"(?<moduleLabel>[^"]+)"\s*\{',
    [System.Text.RegularExpressions.RegexOptions]::CultureInvariant
)

$terraformFiles = Get-ChildItem -LiteralPath $resolvedRepoPath -Filter '*.tf' -File -Recurse |
    Where-Object { $_.FullName -notmatch '[\\/]\.terraform[\\/]' }

foreach ($file in $terraformFiles) {
    $content = Get-Content -LiteralPath $file.FullName -Raw
    $scanContent = Remove-HclComments -Content $content

    foreach ($match in $blockPattern.Matches($scanContent)) {
        $kind = if ($match.Groups['moduleKind'].Success) { 'module' } else { $match.Groups['kind'].Value }
        $type = if ($kind -eq 'module') { $null } else { $match.Groups['type'].Value }
        $label = if ($kind -eq 'module') { $match.Groups['moduleLabel'].Value } else { $match.Groups['label'].Value }
        $coverage = if ($kind -eq 'resource' -and $policyRuleByTerraformType.ContainsKey($type)) {
            $policyRuleByTerraformType[$type]
        }
        else {
            $null
        }

        $blocks.Add([ordered]@{
            kind          = $kind
            terraformType = $type
            label         = $label
            file          = [System.IO.Path]::GetRelativePath($resolvedRepoPath, $file.FullName)
            line          = Get-LineNumber -Content $scanContent -Offset $match.Index
            policyRule    = if ($coverage) { $coverage.rule } else { $null }
            policyStatus  = if ($coverage) { $coverage.status } else { $null }
        })
    }
}

$resources = @($blocks | Where-Object kind -eq 'resource')
$coveredResources = @($resources | Where-Object policyRule)
$report = [ordered]@{
    generatedAt = [DateTimeOffset]::UtcNow.ToString('o')
    repository  = $resolvedRepoPath
    policy      = if ($PolicyPath) { (Resolve-Path -LiteralPath $PolicyPath).Path } else { $null }
    summary     = [ordered]@{
        terraformFiles    = @($terraformFiles).Count
        resources         = $resources.Count
        dataSources       = @($blocks | Where-Object kind -eq 'data').Count
        modules           = @($blocks | Where-Object kind -eq 'module').Count
        policyCovered     = $coveredResources.Count
        policyNotCovered  = $resources.Count - $coveredResources.Count
    }
    blocks      = @($blocks)
}

$outputDirectory = Split-Path -Parent $OutputPath
if ($outputDirectory -and -not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory | Out-Null
}

$report | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $OutputPath -Encoding utf8
$report.summary | Format-List
Write-Host "Inventory written to $OutputPath"
