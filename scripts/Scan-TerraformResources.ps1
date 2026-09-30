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

function Remove-HclHeredocs {
    param([Parameter(Mandatory)][string] $Content)

    $lines = $Content -split "(?<=`n)"
    $result = [System.Text.StringBuilder]::new($Content.Length)
    $terminator = $null

    foreach ($line in $lines) {
        if ($null -ne $terminator) {
            if ($line.Trim() -eq $terminator) {
                $terminator = $null
            }

            $replacement = $line -replace "[^`r`n]", ' '
            [void] $result.Append($replacement)
            continue
        }

        $match = [regex]::Match($line, '<<-?(?<terminator>[A-Za-z_][A-Za-z0-9_]*)')
        if ($match.Success) {
            $terminator = $match.Groups['terminator'].Value
        }

        [void] $result.Append($line)
    }

    return $result.ToString()
}

function Get-HclBraceDepth {
    param(
        [Parameter(Mandatory)][string] $Content,
        [Parameter(Mandatory)][int] $Offset
    )

    $depth = 0
    $inString = $false
    $escaped = $false

    for ($index = 0; $index -lt $Offset; $index++) {
        $character = $Content[$index]

        if ($inString) {
            if ($escaped) {
                $escaped = $false
            }
            elseif ($character -eq '\') {
                $escaped = $true
            }
            elseif ($character -eq '"') {
                $inString = $false
            }
            continue
        }

        if ($character -eq '"') {
            $inString = $true
        }
        elseif ($character -eq '{') {
            $depth++
        }
        elseif ($character -eq '}') {
            $depth--
        }
    }

    return $depth
}

function Get-PortableRelativePath {
    param(
        [Parameter(Mandatory)][string] $BasePath,
        [Parameter(Mandatory)][string] $TargetPath
    )

    $baseUri = [Uri]::new($BasePath.TrimEnd('\') + '\')
    $targetUri = [Uri]::new($TargetPath)
    return [Uri]::UnescapeDataString($baseUri.MakeRelativeUri($targetUri).ToString()).Replace('/', '\')
}

function Add-InventoryBlock {
    param(
        [Parameter(Mandatory)][AllowEmptyCollection()][System.Collections.Generic.List[object]] $Blocks,
        [Parameter(Mandatory)][string] $Kind,
        [AllowNull()][string] $Type,
        [Parameter(Mandatory)][string] $Label,
        [Parameter(Mandatory)][string] $File,
        [Parameter(Mandatory)][int] $Line,
        [Parameter(Mandatory)][hashtable] $PolicyRules
    )

    $coverage = if ($Kind -eq 'resource' -and $PolicyRules.ContainsKey($Type)) {
        $PolicyRules[$Type]
    }
    else {
        $null
    }

    $Blocks.Add([ordered]@{
        kind          = $Kind
        terraformType = $Type
        label         = $Label
        file          = $File
        line          = $Line
        policyRule    = if ($coverage) { $coverage.rule } else { $null }
        policyStatus  = if ($coverage) { $coverage.status } else { $null }
    })
}

$resolvedRepoPath = (Resolve-Path -LiteralPath $RepoPath).Path
$policyRuleByTerraformType = @{}

if ($PolicyPath) {
    $policy = Get-Content -LiteralPath $PolicyPath -Raw | ConvertFrom-Json
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

$terraformFiles = Get-ChildItem -LiteralPath $resolvedRepoPath -File -Recurse |
    Where-Object {
        ($_.Name.EndsWith('.tf') -or $_.Name.EndsWith('.tf.json')) -and
        $_.FullName -notmatch '[\\/]\.terraform[\\/]'
    }

foreach ($file in $terraformFiles) {
    $relativePath = Get-PortableRelativePath -BasePath $resolvedRepoPath -TargetPath $file.FullName

    if ($file.Name.EndsWith('.tf.json')) {
        $configuration = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json

        foreach ($kind in @('resource', 'data')) {
            $kindProperty = $configuration.PSObject.Properties[$kind]
            if ($null -eq $kindProperty) {
                continue
            }

            foreach ($typeProperty in $kindProperty.Value.PSObject.Properties) {
                foreach ($labelProperty in $typeProperty.Value.PSObject.Properties) {
                    Add-InventoryBlock -Blocks $blocks -Kind $kind -Type $typeProperty.Name `
                        -Label $labelProperty.Name -File $relativePath -Line 1 `
                        -PolicyRules $policyRuleByTerraformType
                }
            }
        }

        $moduleProperty = $configuration.PSObject.Properties['module']
        if ($null -ne $moduleProperty) {
            foreach ($labelProperty in $moduleProperty.Value.PSObject.Properties) {
                Add-InventoryBlock -Blocks $blocks -Kind 'module' -Type $null `
                    -Label $labelProperty.Name -File $relativePath -Line 1 `
                    -PolicyRules $policyRuleByTerraformType
            }
        }

        continue
    }

    $content = Get-Content -LiteralPath $file.FullName -Raw
    $scanContent = Remove-HclHeredocs -Content (Remove-HclComments -Content $content)

    foreach ($match in $blockPattern.Matches($scanContent)) {
        if ((Get-HclBraceDepth -Content $scanContent -Offset $match.Index) -ne 0) {
            continue
        }

        $kind = if ($match.Groups['moduleKind'].Success) { 'module' } else { $match.Groups['kind'].Value }
        $type = if ($kind -eq 'module') { $null } else { $match.Groups['type'].Value }
        $label = if ($kind -eq 'module') { $match.Groups['moduleLabel'].Value } else { $match.Groups['label'].Value }

        Add-InventoryBlock -Blocks $blocks -Kind $kind -Type $type -Label $label `
            -File $relativePath -Line (Get-LineNumber -Content $scanContent -Offset $match.Index) `
            -PolicyRules $policyRuleByTerraformType
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
