# MOV to MP4 Converter - Console UI (ASCII-safe, aligned)
# Developer: MUHAMMAD WASIM | +923257627554

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet(
        'banner-install', 'banner-run', 'steps-install',
        'success-install', 'success-run', 'error', 'checking', 'launching', 'footer',
        'progress'
    )]
    [string]$Action,

    [string]$Message = '',
    [int]$Percent = 0,
    [string]$Label = '',
    [string]$Detail = ''
)

$ErrorActionPreference = 'SilentlyContinue'

$script:Inner = 58
$script:Margin = '  '
$script:BarW = 44

$DevName  = 'MUHAMMAD WASIM'
$DevPhone = '+923257627554'
$AppVer   = 'v1.0.0'

function Get-PaddedText {
    param(
        [string]$Text,
        [int]$Width = 58,
        [string]$Align = 'Left'
    )
    if ($Text.Length -gt $Width) {
        $Text = $Text.Substring(0, $Width)
    }
    if ($Align -eq 'Center') {
        $pad = [int][Math]::Floor(($Width - $Text.Length) / 2)
        return (' ' * $pad) + $Text + (' ' * ($Width - $Text.Length - $pad))
    }
    if ($Align -eq 'Right') {
        return $Text.PadLeft($Width)
    }
    return $Text.PadRight($Width)
}

function Write-BoxTop {
    Write-Host ($Margin + '+' + ('=' * $Inner) + '+') -ForegroundColor DarkCyan
}

function Write-BoxMid {
    Write-Host ($Margin + '+' + ('-' * $Inner) + '+') -ForegroundColor DarkCyan
}

function Write-BoxBottom {
    Write-Host ($Margin + '+' + ('=' * $Inner) + '+') -ForegroundColor DarkCyan
}

function Write-BoxLine {
    param(
        [string]$Text,
        [string]$Color = 'White',
        [string]$Align = 'Left'
    )
    $p = Get-PaddedText -Text $Text -Width $Inner -Align $Align
    Write-Host ($Margin + '|' + $p + '|') -ForegroundColor $Color
}

function Write-BoxEmpty {
    Write-Host ($Margin + '|' + (' ' * $Inner) + '|') -ForegroundColor DarkCyan
}

function Show-Header {
    param([string]$Mode)

    Clear-Host
    try {
        $t = if ($Mode -eq 'install') { 'MOV to MP4 - Setup' } else { 'MOV to MP4 Converter' }
        $Host.UI.RawUI.WindowTitle = ($t + ' | ' + $DevName)
    }
    catch { }

    Write-Host ''
    Write-BoxTop
    Write-BoxEmpty
    Write-BoxLine -Text 'MOV  -->  MP4' -Color Magenta -Align Center
    Write-BoxLine -Text 'pCloud Streaming Converter' -Color Cyan -Align Center
    Write-BoxEmpty
    if ($Mode -eq 'install') {
        Write-BoxLine -Text 'FULL SETUP  *  Install All Components' -Color Yellow -Align Center
    }
    else {
        Write-BoxLine -Text 'LAUNCH  *  Video Converter Ready' -Color Yellow -Align Center
    }
    Write-BoxLine -Text ('Version ' + $AppVer) -Color DarkGray -Align Center
    Write-BoxMid
    Write-BoxLine -Text ('Developer : ' + $DevName) -Color White
    Write-BoxLine -Text ('Contact   : ' + $DevPhone) -Color Green
    Write-BoxBottom
    Write-Host ''
}

function Show-InstallSteps {
    Write-Host ($Margin + '>> Installation plan') -ForegroundColor Cyan
    Write-Host ($Margin + ('-' * $Inner)) -ForegroundColor DarkGray
    Write-Host ''
    Write-Host ($Margin + '  [1/4]  Python environment check') -ForegroundColor White
    Write-Host ($Margin + '  [2/4]  Application folders') -ForegroundColor White
    Write-Host ($Margin + '  [3/4]  Python packages (pip)') -ForegroundColor White
    Write-Host ($Margin + '  [4/4]  FFmpeg download (~90 MB)') -ForegroundColor White
    Write-Host ''
    Write-Host ($Margin + '>> Live progress (below)') -ForegroundColor Cyan
    Write-Host ($Margin + ('-' * $Inner)) -ForegroundColor DarkGray
    Write-Host ''
}

function Show-ProgressBar {
    param(
        [int]$Pct,
        [string]$Lbl,
        [string]$Det
    )
    $pctVal = [Math]::Max(0, [Math]::Min(100, $Pct))
    $filled = [int][Math]::Floor($BarW * $pctVal / 100)
    $empty = $BarW - $filled
    $bar = ('#' * $filled) + ('.' * $empty)
    $pctStr = [math]::Round($pctVal, 1).ToString().PadLeft(5)
    $pctStr = $pctStr + [char]37
    $lbl = $Lbl
    if ($lbl.Length -gt 22) { $lbl = $lbl.Substring(0, 22) }
    $lbl = $lbl.PadRight(22)
    $line = $Margin + '  ' + $lbl + ' [' + $bar + '] ' + $pctStr
    if ($Det) { $line = $line + '  ' + $Det }
    Write-Host $line -ForegroundColor Green
}

function Show-Success {
    param([string]$Mode)

    Write-Host ''
    Write-BoxTop
    if ($Mode -eq 'install') {
        Write-BoxLine -Text '[OK] SETUP COMPLETED SUCCESSFULLY' -Color Green -Align Center
    }
    else {
        Write-BoxLine -Text '[OK] ALL SYSTEMS READY' -Color Green -Align Center
    }
    Write-BoxBottom
    Write-Host ''
    if ($Mode -eq 'install') {
        Write-Host ($Margin + '  Next: Double-click ') -NoNewline -ForegroundColor Yellow
        Write-Host 'run.bat' -NoNewline -ForegroundColor White
        Write-Host (' to open the converter.') -ForegroundColor Yellow
    }
    else {
        Write-Host ($Margin + '  Opening application window...') -ForegroundColor Yellow
    }
    Write-Host ''
    Write-Host ($Margin + '  ' + $DevName + '  *  ' + $DevPhone) -ForegroundColor DarkGray
    Write-Host ''
}

function Show-ErrorBox {
    Write-Host ''
    Write-BoxTop
    Write-BoxLine -Text '[X] SETUP FAILED' -Color Red -Align Center
    Write-BoxMid
    if ($Message) {
        Write-BoxLine -Text $Message -Color Yellow
    }
    Write-BoxBottom
    Write-Host ''
    Write-Host ($Margin + '  Run install.bat as Administrator') -ForegroundColor White
    Write-Host ($Margin + '  ' + $DevName + '  *  ' + $DevPhone) -ForegroundColor Green
    Write-Host ''
}

switch ($Action) {
    'banner-install'  { Show-Header -Mode 'install' }
    'banner-run'      { Show-Header -Mode 'run' }
    'steps-install'   { Show-InstallSteps }
    'success-install' { Show-Success -Mode 'install' }
    'success-run'     { Show-Success -Mode 'run' }
    'checking' {
        Write-Host ($Margin + '>> Checking installed components...') -ForegroundColor Cyan
        Write-Host ($Margin + ('-' * $Inner)) -ForegroundColor DarkGray
        Write-Host ''
    }
    'launching' {
        Write-Host ($Margin + '>> Starting MOV to MP4 Converter...') -ForegroundColor Cyan
        Write-Host ''
    }
    'progress' {
        Show-ProgressBar -Pct $Percent -Lbl $Label -Det $Detail
    }
    'error' {
        Show-ErrorBox
        exit 1
    }
    'footer' {
        Write-Host ($Margin + ('-' * $Inner)) -ForegroundColor DarkGray
        Write-Host ($Margin + '  (c) ' + $DevName + '  *  ' + $DevPhone) -ForegroundColor DarkGray
        Write-Host ''
    }
}

exit 0
