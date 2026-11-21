; Windows per-user preview. No runtime/model downloads and no user-data cleanup.
#ifndef PayloadDir
  #error PayloadDir is required
#endif
#ifndef OutputDir
  #error OutputDir is required
#endif
[Setup]
AppId={{E075C2AE-10DA-43F8-9C83-55BAAC22DB57}
AppName=Reflow Studio Desktop Preview
AppVersion=0.7
AppVerName=Reflow Studio Desktop Preview
DefaultDirName={localappdata}\Programs\ReflowStudio
DefaultGroupName=Reflow Studio
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=ReflowStudio-windows-x64-desktop-preview-setup
SetupIconFile={#PayloadDir}\assets\icon.ico
UninstallDisplayIcon={app}\ReflowStudio.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
CloseApplications=no
RestartApplications=no
SetupLogging=yes
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked
[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Reflow Studio"; Filename: "{app}\ReflowStudio.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Reflow Studio"; Filename: "{app}\ReflowStudio.exe"; WorkingDir: "{app}"; Tasks: desktopicon
[Run]
Filename: "{app}\ReflowStudio.exe"; Description: "Open Reflow Studio"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
[Code]
function CreateFile(FileName: String; Access, Share: LongWord; Security: Integer;
  Creation, Attributes: LongWord; Template: Integer): Integer;
  external 'CreateFileW@kernel32.dll stdcall';
function LockFile(Handle: Integer; Low, High, CountLow, CountHigh: LongWord): Boolean;
  external 'LockFile@kernel32.dll stdcall';
function CloseHandle(Handle: Integer): Boolean;
  external 'CloseHandle@kernel32.dll stdcall';
function ApplicationIsIdle(): Boolean;
var Handle: Integer; FileName: String;
begin
  Result := True;
  FileName := ExpandConstant('{app}\.reflow-instance.lock');
  if not FileExists(FileName) then exit;
  Handle := CreateFile(FileName, $C0000000, 3, 0, 3, 0, 0);
  if Handle = -1 then begin Result := False; exit; end;
  Result := LockFile(Handle, 0, 0, 1, 0);
  CloseHandle(Handle);
end;
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if not ApplicationIsIdle() then
    Result := 'Close Reflow Studio, including its tray icon, before updating.';
end;
function InitializeUninstall(): Boolean;
begin
  Result := ApplicationIsIdle();
  if not Result then
    MsgBox('Close Reflow Studio, including its tray icon, before uninstalling.', mbError, MB_OK);
end;
