; Shakshuka Installer Script for Inno Setup
; This creates a professional Windows installer

#define MyAppName "Shakshuka"
#define MyAppVersion "24.5"
#define MyAppPublisher "vibinandvanshika.in"
#define MyAppURL "https://github.com/shakshuka-python"
#define MyAppExeName "Shakshuka.exe"
#define MyAppId "A1B2C3D4-E5F6-7890-ABCD-EF1234567890"

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
AppContact=support@vibinandvanshika.in
AppCopyright=Copyright (C) 2025 vibinandvanshika.in
VersionInfoVersion=24.5.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Shakshuka Task Manager - Professional productivity tool
VersionInfoCopyright=Copyright (C) 2025 vibinandvanshika.in
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion=24.5.0.0
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=..\docs\LICENSE.txt
OutputDir=dist
OutputBaseFilename=Shakshuka-Setup-v{#MyAppVersion}
SetupIconFile=..\assets\static\images\icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
AppMutex=ShakshukaSingleInstanceMutex
; Force reinstall to ensure updates work properly
DisableDirPage=no
DisableProgramGroupPage=no
; Code signing configuration (uncomment when you have a certificate)
; SignTool=signtool sign /f "C:\path\to\certificate.pfx" /p "password" /tr http://timestamp.digicert.com /td SHA256 /fd SHA256 /d "Shakshuka Task Manager" $f
; SignedUninstaller=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode
Name: "autostart"; Description: "Start Shakshuka automatically when Windows starts"; GroupDescription: "Startup Options:"
Name: "firewall"; Description: "Add Windows Firewall rule for phone pairing"; GroupDescription: "Network Options:"

[Files]
; Main executable
Source: "..\scripts\dist\Shakshuka.exe"; DestDir: "{app}"; Flags: ignoreversion
; Static files
Source: "..\assets\static\*"; DestDir: "{app}\assets\static"; Flags: ignoreversion recursesubdirs createallsubdirs
; Templates
Source: "..\assets\templates\*"; DestDir: "{app}\assets\templates"; Flags: ignoreversion recursesubdirs createallsubdirs
; Data directory (for initial setup)
Source: "..\data\*"; DestDir: "{app}\data"; Flags: ignoreversion recursesubdirs createallsubdirs
; Configuration files
Source: "..\config\*"; DestDir: "{app}\config"; Flags: ignoreversion recursesubdirs createallsubdirs
; Management scripts
Source: "Start-Shakshuka.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "Start-Shakshuka-Verbose.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "Start-Shakshuka-Silent.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "Start-Shakshuka-Silent.vbs"; DestDir: "{app}"; Flags: ignoreversion
Source: "Start-Shakshuka-Autostart.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "Stop-Shakshuka.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "run.bat"; DestDir: "{app}"; Flags: ignoreversion
; Source: "build.bat"; DestDir: "{app}"; Flags: ignoreversion   ; developer build script, not needed at runtime
; Documentation
Source: "..\\docs\\*"; DestDir: "{app}\\docs"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Primary shortcut uses the EXE with embedded icon
Name: "{group}\{#MyAppName}"; Filename: "{app}\Start-Shakshuka-Silent.vbs"; IconFilename: "{app}\assets\static\images\icon.ico"; WorkingDir: "{app}"
; Additional shortcuts
Name: "{group}\Start Shakshuka (Silent)"; Filename: "{app}\Start-Shakshuka-Silent.vbs"; IconFilename: "{app}\assets\static\images\icon.ico"; WorkingDir: "{app}"
Name: "{group}\Start Shakshuka (Verbose)"; Filename: "{app}\Start-Shakshuka-Verbose.bat"; IconFilename: "{app}\assets\static\images\icon.ico"; WorkingDir: "{app}"
Name: "{group}\Stop Shakshuka"; Filename: "{app}\Stop-Shakshuka.bat"; IconFilename: "{app}\assets\static\images\icon.ico"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
; Desktop shortcut points to EXE to leverage embedded icon
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\Start-Shakshuka-Silent.vbs"; IconFilename: "{app}\assets\static\images\icon.ico"; WorkingDir: "{app}"; Tasks: desktopicon
; Quick Launch (legacy) to EXE
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\Shakshuka.exe"; WorkingDir: "{app}"; Tasks: quicklaunchicon

[Run]
; Launch Shakshuka after installation (silent mode)
Filename: "{sys}\wscript.exe"; Parameters: """{app}\Start-Shakshuka-Silent.vbs"""; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent; Check: not WizardSilent

; Visit website after installation (checked by default)
Filename: "https://vibinandvanshika.in/?utm_source=tech&utm_medium=inno&utm_campaign=shakshuka"; Description: "Check my website!"; Flags: shellexec postinstall skipifsilent; Check: not WizardSilent

[UninstallRun]
Filename: "{app}\Stop-Shakshuka.bat"; RunOnceId: "StopShakshuka"

[Registry]
; Add to Windows startup if selected - use VBS script for silent start
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Shakshuka"; ValueData: "wscript.exe ""{app}\Start-Shakshuka-Silent.vbs"""; Flags: uninsdeletevalue; Tasks: autostart

[Code]
var
  ShutdownForm: TSetupForm;
  ShutdownTitle: TNewStaticText;
  ShutdownLabel: TNewStaticText;
  ShutdownProgress: TNewProgressBar;

procedure ShowShutdownForm(const Msg: String);
begin
  if ShutdownForm <> nil then
  begin
    if ShutdownLabel <> nil then
      ShutdownLabel.Caption := Msg;
    try
      ShutdownForm.Update;
    except
    end;
    Exit;
  end;

  ShutdownForm := CreateCustomForm;
  ShutdownForm.BorderStyle := bsDialog;
  ShutdownForm.Caption := '{#MyAppName} Setup';
  ShutdownForm.ClientWidth := ScaleX(520);
  ShutdownForm.ClientHeight := ScaleY(170);
  ShutdownForm.Position := poScreenCenter;
  ShutdownForm.Color := clWhite;
  ShutdownForm.Font.Name := 'Segoe UI';
  ShutdownForm.Font.Size := 10;

  ShutdownTitle := TNewStaticText.Create(ShutdownForm);
  ShutdownTitle.Parent := ShutdownForm;
  ShutdownTitle.Left := ScaleX(20);
  ShutdownTitle.Top := ScaleY(22);
  ShutdownTitle.Width := ShutdownForm.ClientWidth - ScaleX(40);
  ShutdownTitle.Height := ScaleY(24);
  ShutdownTitle.AutoSize := False;
  ShutdownTitle.Caption := 'Closing {#MyAppName}...';
  ShutdownTitle.Font.Size := 12;
  ShutdownTitle.Font.Style := [fsBold];
  ShutdownTitle.Font.Color := clBlack;

  ShutdownLabel := TNewStaticText.Create(ShutdownForm);
  ShutdownLabel.Parent := ShutdownForm;
  ShutdownLabel.Left := ScaleX(20);
  ShutdownLabel.Top := ScaleY(58);
  ShutdownLabel.Width := ShutdownForm.ClientWidth - ScaleX(40);
  ShutdownLabel.Height := ScaleY(44);
  ShutdownLabel.WordWrap := True;
  ShutdownLabel.AutoSize := False;
  ShutdownLabel.Caption := Msg;
  ShutdownLabel.Font.Size := 10;
  ShutdownLabel.Font.Color := $00666666;

  ShutdownProgress := TNewProgressBar.Create(ShutdownForm);
  ShutdownProgress.Parent := ShutdownForm;
  ShutdownProgress.Left := ScaleX(20);
  ShutdownProgress.Top := ScaleY(118);
  ShutdownProgress.Width := ShutdownForm.ClientWidth - ScaleX(40);
  ShutdownProgress.Height := ScaleY(16);
  ShutdownProgress.Min := 0;
  ShutdownProgress.Max := 100;
  ShutdownProgress.Position := 10;

  ShutdownForm.Show;
  ShutdownForm.BringToFront;
  ShutdownForm.Update;
end;

procedure HideShutdownForm();
begin
  if ShutdownForm = nil then
    Exit;

  try
    ShutdownForm.Hide;
  except
  end;

  try
    ShutdownForm.Free;
  except
  end;

  ShutdownForm := nil;
  ShutdownTitle := nil;
  ShutdownLabel := nil;
  ShutdownProgress := nil;
end;

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
      // Create user data directory structure
      ForceDirectories(ExpandConstant('{userappdata}\Shakshuka\data\users'));
      ForceDirectories(ExpandConstant('{userappdata}\Shakshuka\data\backups'));
      ForceDirectories(ExpandConstant('{userappdata}\Shakshuka\logs'));
    end;
    
    // Add firewall rule if selected
    if IsTaskSelected('firewall') then
    begin
      // Add inbound rule for Shakshuka (allow incoming connections for phone pairing)
      Exec('netsh', 'advfirewall firewall add rule name="Shakshuka Phone Pairing" dir=in action=allow program="' + ExpandConstant('{app}\{#MyAppExeName}') + '" enable=yes', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      
      // Add outbound rule (allow Shakshuka to communicate)
      Exec('netsh', 'advfirewall firewall add rule name="Shakshuka Outbound" dir=out action=allow program="' + ExpandConstant('{app}\{#MyAppExeName}') + '" enable=yes', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    end;
  end;
end;

function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
  UninstallString: String;
  InstalledDir: String;
  UninstallKey: String;
  HasExistingInstall: Boolean;
begin
  Result := True;

  // Proactively stop a running Shakshuka instance before copying files.
  // Do NOT rely on a mutex name here because older builds / different entrypoints
  // may not create it. Instead, try graceful shutdown via the installed EXE,
  // then fall back to taskkill.
  UninstallKey := 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{' + '{#MyAppId}' + '}_is1';
  InstalledDir := '';
  HasExistingInstall := RegQueryStringValue(HKEY_LOCAL_MACHINE, UninstallKey, 'UninstallString', UninstallString);

  if HasExistingInstall then
  begin
    ShowShutdownForm('Checking for previous installation...');
    if ShutdownProgress <> nil then ShutdownProgress.Position := 5;
  end;

  if not RegQueryStringValue(HKEY_LOCAL_MACHINE, UninstallKey, 'Inno Setup: App Path', InstalledDir) then
  begin
    if not RegQueryStringValue(HKEY_LOCAL_MACHINE, UninstallKey, 'InstallLocation', InstalledDir) then
    begin
      InstalledDir := '';
    end;
  end;

  if HasExistingInstall and (InstalledDir <> '') and FileExists(InstalledDir + '\{#MyAppExeName}') then
  begin
    ShowShutdownForm('Closing {#MyAppName} (if running)...');
    if ShutdownProgress <> nil then ShutdownProgress.Position := 25;
    Exec(InstalledDir + '\{#MyAppExeName}', '--shutdown', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(1500);
    if ShutdownProgress <> nil then ShutdownProgress.Position := 55;
  end;

  // Last-resort: force kill any remaining Shakshuka.exe.
  if HasExistingInstall then
  begin
    ShowShutdownForm('Ensuring {#MyAppName} is closed...');
    if ShutdownProgress <> nil then ShutdownProgress.Position := 75;
    Exec('taskkill', '/F /T /IM {#MyAppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(1000);
    if ShutdownProgress <> nil then ShutdownProgress.Position := 100;
    HideShutdownForm();
  end;
  
  // Check for existing installation
  if HasExistingInstall then
  begin
    if MsgBox('Shakshuka is already installed. Do you want to update to the latest version?', mbConfirmation, MB_YESNO) = IDYES then
    begin
      // Uninstall existing version first
      Exec(UninstallString, '/SILENT', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
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
    
    // Remove firewall rules if they exist
    Exec('netsh', 'advfirewall firewall delete rule name="Shakshuka Phone Pairing"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec('netsh', 'advfirewall firewall delete rule name="Shakshuka Outbound"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    
    // Ask if user wants to keep data
    if MsgBox('Do you want to keep your Shakshuka data (tasks, settings, etc.)?', mbConfirmation, MB_YESNO) = IDNO then
    begin
      DelTree(ExpandConstant('{userappdata}\Shakshuka'), True, True, True);
    end;
  end;
end;






