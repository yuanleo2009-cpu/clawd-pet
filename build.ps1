# 一鍵打包成單一 exe：dist\ClawdPet.exe
# 用法：在專案資料夾執行  .\build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "建立虛擬環境並安裝套件…"
    py -3.13 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}

# 重新產生素材（改過 tools\make_sprites.py 時會用到）
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe tools\make_sprites.py | Out-Null
Remove-Item Env:QT_QPA_PLATFORM

# 先結束正在執行的 ClawdPet.exe，否則無法覆蓋
Get-Process ClawdPet -ErrorAction SilentlyContinue | Stop-Process -Force

# 打包設定在 ClawdPet.spec（包含拿掉用不到的元件來瘦身）
.\.venv\Scripts\pyinstaller.exe --noconfirm --clean ClawdPet.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 打包失敗" }

Write-Host ""
Write-Host "完成：$PSScriptRoot\dist\ClawdPet.exe" -ForegroundColor Green

# 產生安裝包（需要 Inno Setup 6：winget install JRSoftware.InnoSetup）
$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($iscc) {
    & $iscc /Q installer\ClawdPet.iss
    if ($LASTEXITCODE -ne 0) { throw "安裝包編譯失敗" }
    $setup = Get-ChildItem dist\ClawdPet-Setup-*.exe | Sort-Object LastWriteTime | Select-Object -Last 1
    Write-Host "安裝包：$($setup.FullName)" -ForegroundColor Green
} else {
    Write-Host "沒有找到 Inno Setup，略過安裝包（winget install JRSoftware.InnoSetup）" -ForegroundColor Yellow
}
