; ClawdPet 安裝包（Inno Setup 6）
; 編譯：在專案資料夾執行 .\build.ps1（會先打包 exe，再產生 dist\ClawdPet-Setup-<版本>.exe）

#define AppName        "Clawd 桌寵"
#define AppVersion     "1.0.0"
#define AppExe         "ClawdPet.exe"

[Setup]
AppId={{8F3C2B1E-6A4D-4E7B-9C1A-3D5E7F9A2B41}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=ClawdPet (fan-made)
; 只安裝給目前使用者：不需要系統管理員權限，不會跳出 UAC
PrivilegesRequired=lowest
DefaultDirName={autopf}\ClawdPet
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
OutputDir=..\dist
OutputBaseFilename=ClawdPet-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
; 更新安裝時，先關掉正在執行的 Clawd
CloseApplications=force
RestartApplications=no
ShowLanguageDialog=auto
LanguageDetectionMethod=uilanguage

[Languages]
Name: "cht"; MessagesFile: "lang\ChineseTraditional.isl"
Name: "chs"; MessagesFile: "lang\ChineseSimplified.isl"
Name: "en";  MessagesFile: "compiler:Default.isl"

[CustomMessages]
cht.AutoStart=開機時自動啟動 Clawd
chs.AutoStart=开机时自动启动 Clawd
en.AutoStart=Start Clawd when Windows starts
cht.Other=其他：
chs.Other=其他：
en.Other=Other:
cht.LaunchNow=立即啟動 Clawd（雙擊牠就能開啟 Claude）
chs.LaunchNow=立即启动 Clawd（双击它就能打开 Claude）
en.LaunchNow=Launch Clawd now (double-click it to open Claude)
cht.NoClaude=這台電腦還沒有安裝 Claude 桌面版。%n%nClawd 雙擊時會開啟 Claude 桌面版，要現在打開下載頁面嗎？
chs.NoClaude=这台电脑还没有安装 Claude 桌面版。%n%nClawd 双击时会打开 Claude 桌面版，要现在打开下载页面吗？
en.NoClaude=The Claude desktop app is not installed on this PC.%n%nDouble-clicking Clawd opens Claude. Open the download page now?

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart";   Description: "{cm:AutoStart}";        GroupDescription: "{cm:Other}"

[Files]
Source: "..\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}";  Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
    ValueName: "ClawdPet"; ValueData: """{app}\{#AppExe}"""; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchNow}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM {#AppExe}"; Flags: runhidden; RunOnceId: "KillClawd"

[Code]
{ 檢查這台電腦有沒有 Claude 桌面版（Microsoft Store / 官網 MSIX / 舊版安裝程式） }
function ClaudeInstalled: Boolean;
var
  FindRec: TFindRec;
begin
  Result := FileExists(ExpandConstant('{localappdata}\AnthropicClaude\claude.exe'));
  if not Result then
    if FindFirst(ExpandConstant('{localappdata}\Packages\Claude_*'), FindRec) then
    begin
      Result := True;
      FindClose(FindRec);
    end;
  if not Result then
    Result := RegKeyExists(HKEY_CURRENT_USER, 'Software\Classes\claude\shell\open\command')
           or RegKeyExists(HKEY_CLASSES_ROOT, 'claude\shell\open\command');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ErrCode: Integer;
begin
  if (CurStep = ssPostInstall) and (not WizardSilent) and (not ClaudeInstalled) then
    if MsgBox(CustomMessage('NoClaude'), mbConfirmation, MB_YESNO) = IDYES then
      ShellExec('open', 'https://claude.ai/download', '', '', SW_SHOWNORMAL, ewNoWait, ErrCode);
end;

{ 解除安裝：也清掉從 Clawd 右鍵選單開啟的「開機自動啟動」 }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'ClawdPet');
end;
