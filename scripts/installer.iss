; Shakshuka Installer Script for Inno Setup
; This creates a professional Windows installer

#define MyAppName "Shakshuka"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Shakshuka Team"
#define MyAppURL "https://github.com/shakshuka/shakshuka"
#define MyAppExeName "Shakshuka.exe"

[Setup]
; NOTE: The value of AppId uniquely identifies this application.
; Do not use the same AppId value in installers for other applications.
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=LICENSE.txt
OutputDir=dist
OutputBaseFilename=Shakshuka-Setup-v{#MyAppVersion}
SetupIconFile=static\images\icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode
Name: "autostart"; Description: "Start Shakshuka automatically when Windows starts"; GroupDescription: "Startup Options:"

[Files]
; Main executable
Source: "Shakshuka.exe"; DestDir: "{app}"; Flags: ignoreversion
; Static files
Source: "static\*"; DestDir: "{app}\static"; Flags: ignoreversion recursesubdirs createallsubdirs
; Templates
Source: "templates\*"; DestDir: "{app}\templates"; Flags: ignoreversion recursesubdirs createallsubdirs
; Data directory (for initial setup)
Source: "data\*"; DestDir: "{app}\data"; Flags: ignoreversion recursesubdirs createallsubdirs
; Configuration files
Source: "version.json"; DestDir: "{app}"; Flags: ignoreversion
; Management scripts
Source: "Start-Shakshuka.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "Stop-Shakshuka.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "server-manager.ps1"; DestDir: "{app}"; Flags: ignoreversion
; Documentation
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "INSTALLATION.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "TROUBLESHOOTING.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "QUICK-START.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Start Shakshuka"; Filename: "{app}\Start-Shakshuka.bat"
Name: "{group}\Stop Shakshuka"; Filename: "{app}\Stop-Shakshuka.bat"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
Filename: "{app}\Start-Shakshuka.bat"; Description: "Start Shakshuka Server"; Flags: postinstall skipifsilent

[UninstallRun]
Filename: "{app}\Stop-Shakshuka.bat"; RunOnceId: "StopShakshuka"

[Registry]
; Add to Windows startup if selected
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Shakshuka"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: autostart

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    // Create data directory in user's AppData
    ForceDirectories(ExpandConstant('{userappdata}\Shakshuka\data'));
    
    // Copy initial data if user data doesn't exist
    if not DirExists(ExpandConstant('{userappdata}\Shakshuka\data\users')) then
    begin
      DirCopy(ExpandConstant('{app}\data'), ExpandConstant('{userappdata}\Shakshuka\data'), False);
    end;
  end;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  
  // Check if Shakshuka is already running
  if CheckForMutexes('ShakshukaMutex') then
  begin
    if MsgBox('Shakshuka is currently running. Please close it before continuing with the installation.', mbConfirmation, MB_OKCANCEL) = IDOK then
    begin
      // Try to stop Shakshuka
      Exec('taskkill', '/F /IM Shakshuka.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    end
    else
    begin
      Result := False;
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    // Stop Shakshuka if running
    Exec('taskkill', '/F /IM Shakshuka.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    
    // Ask if user wants to keep data
    if MsgBox('Do you want to keep your Shakshuka data (tasks, settings, etc.)?', mbConfirmation, MB_YESNO) = IDNO then
    begin
      DelTree(ExpandConstant('{userappdata}\Shakshuka'), True, True, True);
    end;
  end;
end;


