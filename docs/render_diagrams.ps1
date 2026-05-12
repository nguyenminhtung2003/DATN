$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$DiagramDir = Join-Path $RepoRoot "docs\diagrams"
$ImageDir = Join-Path $RepoRoot "docs\images"
$PlantUmlJar = Join-Path $RepoRoot "tools\plantuml\plantuml.jar"
$PuppeteerConfig = Join-Path $DiagramDir "puppeteer-config.json"

New-Item -ItemType Directory -Force -Path $ImageDir | Out-Null

function Invoke-Render {
    param(
        [string]$Tool,
        [string[]]$CommandArgs,
        [string]$Source,
        [string]$Output
    )

    Write-Host "Rendering $Source -> $Output"
    & $Tool @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Render failed: $Source"
    }
    if (-not (Test-Path $Output)) {
        throw "Output missing: $Output"
    }
}

$MermaidFiles = @(
    "system_overview",
    "hardware_block",
    "rfid_workflow",
    "database_erd",
    "drowsiness_algorithm_flow",
    "project_mindmap",
    "alert_state_flow"
)

foreach ($Name in $MermaidFiles) {
    $Source = Join-Path $DiagramDir "$Name.mmd"
    $Output = Join-Path $ImageDir "$Name.svg"
    Invoke-Render `
        -Tool "cmd" `
        -CommandArgs @("/c", "npx", "mmdc", "-p", $PuppeteerConfig, "-i", $Source, "-o", $Output) `
        -Source $Source `
        -Output $Output
}

$D2Files = @(
    "software_architecture",
    "ai_pipeline",
    "demo_network"
)

foreach ($Name in $D2Files) {
    $Source = Join-Path $DiagramDir "$Name.d2"
    $Output = Join-Path $ImageDir "$Name.svg"
    Invoke-Render `
        -Tool "d2" `
        -CommandArgs @($Source, $Output) `
        -Source $Source `
        -Output $Output
}

if (-not (Test-Path $PlantUmlJar)) {
    throw "Missing tools/plantuml/plantuml.jar. Place PlantUML jar there before rendering websocket_sequence.svg."
}

$PlantSource = Join-Path $DiagramDir "websocket_sequence.puml"
$PlantOutput = Join-Path $ImageDir "websocket_sequence.svg"
Invoke-Render `
    -Tool "java" `
    -CommandArgs @("-jar", $PlantUmlJar, "-tsvg", "-o", "..\images", $PlantSource) `
    -Source $PlantSource `
    -Output $PlantOutput

Write-Host "Diagram rendering complete."
