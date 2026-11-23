# 一鍵打包：dist\ClawdPet\（程式資料夾）+ dist\ClawdPet-Setup-<版本>.exe（安裝包）
# 用法：在專案資料夾執行  .\build.ps1
# GitHub Actions（.github\workflows\release.yml）也是呼叫這個腳本。
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "建立虛擬環境並安裝套件…"
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3.13 -m venv .venv } else { python -m venv .venv }
    .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { throw "安裝套件失敗" }
}

$version = (.\.venv\Scripts\python.exe -c "from services.version import __version__; print(__version__)").Trim()
Write-Host "版本：$version"

# 重新產生素材（改過 tools\make_sprites.py 時會用到）
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe tools\make_sprites.py | Out-Null
Remove-Item Env:QT_QPA_PLATFORM

# 先請正在執行的 ClawdPet 正常結束（從 dist 執行的那隻），否則無法覆蓋
if (Test-Path "dist\ClawdPet\ClawdPet.exe") {
    Start-Process "dist\ClawdPet\ClawdPet.exe" -ArgumentList "--quit" -Wait -WindowStyle Hidden
}

# 打包設定在 ClawdPet.spec（資料夾模式，並拿掉用不到的元件來瘦身）
.\.venv\Scripts\pyinstaller.exe --noconfirm --clean ClawdPet.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 打包失敗" }
Write-Host ""
Write-Host "完成：$PSScriptRoot\dist\ClawdPet\ClawdPet.exe" -ForegroundColor Green

# 產生安裝包（需要 Inno Setup 6：winget install JRSoftware.InnoSetup）
$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($iscc) {
    & $iscc /Q "/DAppVersion=$version" installer\ClawdPet.iss
    if ($LASTEXITCODE -ne 0) { throw "安裝包編譯失敗" }
    $setup = Get-Item "dist\ClawdPet-Setup-$version.exe"
    $hash = (Get-FileHash $setup.FullName -Algorithm SHA256).Hash
    Set-Content -Path "$($setup.FullName).sha256" -Value "$hash  $($setup.Name)" -Encoding ascii
    Write-Host "安裝包：$($setup.FullName)" -ForegroundColor Green
    Write-Host "SHA-256：$hash"
} else {
    Write-Host "沒有找到 Inno Setup，略過安裝包（winget install JRSoftware.InnoSetup）" -ForegroundColor Yellow
}
