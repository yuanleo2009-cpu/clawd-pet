; ClawdPet 安裝包（Inno Setup 6）
; 編譯：在專案資料夾執行 .\build.ps1（會先打包，再產生 dist\ClawdPet-Setup-<版本>.exe）
; 版本號來自 services\version.py，由 build.ps1 用 /DAppVersion=x.y.z 傳進來。

#define AppName        "Clawd 桌寵"
#ifndef AppVersion
  #define AppVersion   "0.0.0"
#endif
#define AppExe         "ClawdPet.exe"

[Setup]
AppId={{8F3C2B1E-6A4D-4E7B-9C1A-3D5E7F9A2B41}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=ClawdPet (fan-made)
AppPublisherURL=https://github.com/yuanleo2009-cpu/clawd-pet
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
VersionInfoVersion={#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
; 更新安裝時：PrepareToInstall 會先請 Clawd 自己正常結束；還在的話再由系統關閉
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
cht.DeleteData=要一併刪除 Clawd 的設定與台詞嗎？%n（位置、大小、自訂台詞等，存放在 %1）%n%n選「否」會保留，之後重新安裝可以繼續使用。
chs.DeleteData=要一并删除 Clawd 的设置与台词吗？%n（位置、大小、自定义台词等，存放在 %1）%n%n选“否”会保留，之后重新安装可以继续使用。
en.DeleteData=Also delete Clawd's settings and phrases?%n(position, size, custom phrases, stored in %1)%n%nChoose No to keep them for a future reinstall.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart";   Description: "{cm:AutoStart}";        GroupDescription: "{cm:Other}"

[Files]
; 資料夾模式：ClawdPet.exe + _internal\
Source: "..\dist\ClawdPet\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; 舊版（單一 exe）沒有 _internal；新版整個覆蓋前先清掉舊的元件，避免殘留
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}";  Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
    ValueName: "ClawdPet"; ValueData: """{app}\{#AppExe}"""; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchNow}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; 先請 Clawd 自己正常結束（會存好位置）；沒結束的話再強制關閉
Filename: "{app}\{#AppExe}"; Parameters: "--quit"; Flags: runhidden waituntilterminated skipifdoesntexist; RunOnceId: "QuitClawd"
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM {#AppExe}"; Flags: runhidden; RunOnceId: "KillClawd"

[Code]
{ 檢查這台電腦有沒有 Claude 桌面版（官方 MSIX / 舊版安裝程式 / claude:// 協定） }
function ClaudeInstalled: Boolean;
begin
  Result := DirExists(ExpandConstant('{localappdata}\Packages\Claude_pzs8sxrjxfjjc'))
         or FileExists(ExpandConstant('{localappdata}\AnthropicClaude\claude.exe'))
         or RegKeyExists(HKEY_CURRENT_USER, 'Software\Classes\claude\shell\open\command')
         or RegKeyExists(HKEY_CLASSES_ROOT, 'claude\shell\open\command');
end;

{ 更新安裝前：請正在執行的 Clawd 正常結束 }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Exe: String;
  ResultCode: Integer;
begin
  Result := '';
  Exe := ExpandConstant('{app}\{#AppExe}');
  if FileExists(Exe) then
  begin
    Exec(Exe, '--quit', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(500);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ErrCode: Integer;
begin
  if (CurStep = ssPostInstall) and (not WizardSilent) and (not ClaudeInstalled) then
    if MsgBox(CustomMessage('NoClaude'), mbConfirmation, MB_YESNO) = IDYES then
      ShellExec('open', 'https://claude.ai/download', '', '', SW_SHOWNORMAL, ewNoWait, ErrCode);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    { 清掉從 Clawd 右鍵選單開啟的「開機自動啟動」 }
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'ClawdPet');
    { 使用者資料：問過才刪（靜默解除安裝時保留） }
    DataDir := ExpandConstant('{userappdata}\ClawdPet');
    if DirExists(DataDir) and (not UninstallSilent) then
      if MsgBox(FmtMessage(CustomMessage('DeleteData'), [DataDir]), mbConfirmation, MB_YESNO) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;
