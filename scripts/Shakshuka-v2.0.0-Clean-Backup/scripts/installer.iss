; Shakshuka Installer Script for Inno Setup
; This creates a professional Windows installer

#define MyAppName "Shakshuka"
#define MyAppVersion "2.0.0-b3"
#define MyAppPublisher "vibinandvanshika.in"
#define MyAppURL "https://github.com/shakshuka-python"
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
; Force reinstall to ensure updates work properly
DisableDirPage=no
DisableProgramGroupPage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode
Name: "autostart"; Description: "Start Shakshuka automatically when Windows starts"; GroupDescription: "Startup Options:"

[Files]
; Main executable
Source: "..\Shakshuka.exe"; DestDir: "{app}"; Flags: ignoreversion
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
Source: "build.bat"; DestDir: "{app}"; Flags: ignoreversion
; Documentation
Source: "..\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\Start-Shakshuka-Silent.vbs"; IconFilename: "{app}\assets\static\images\icon.ico"
Name: "{group}\Start Shakshuka (Silent)"; Filename: "{app}\Start-Shakshuka-Silent.vbs"; IconFilename: "{app}\assets\static\images\icon.ico"
Name: "{group}\Start Shakshuka (Verbose)"; Filename: "{app}\Start-Shakshuka-Verbose.bat"; IconFilename: "{app}\assets\static\images\icon.ico"
Name: "{group}\Stop Shakshuka"; Filename: "{app}\Stop-Shakshuka.bat"; IconFilename: "{app}\assets\static\images\icon.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\Start-Shakshuka-Silent.vbs"; IconFilename: "{app}\assets\static\images\icon.ico"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\Start-Shakshuka-Silent.vbs"; IconFilename: "{app}\assets\static\images\icon.ico"; Tasks: quicklaunchicon

[Run]
; No automatic launch - user can start manually from shortcuts

[UninstallRun]
Filename: "{app}\Stop-Shakshuka.bat"; RunOnceId: "StopShakshuka"

[Registry]
; Add to Windows startup if selected - use batch file for better reliability
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Shakshuka"; ValueData: """{app}\Start-Shakshuka-Autostart.bat"""; Flags: uninsdeletevalue; Tasks: autostart

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
      // Create user data directory structure
      ForceDirectories(ExpandConstant('{userappdata}\Shakshuka\data\users'));
      ForceDirectories(ExpandConstant('{userappdata}\Shakshuka\data\backups'));
      ForceDirectories(ExpandConstant('{userappdata}\Shakshuka\logs'));
    end;
  end;
end;

function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
  UninstallString: String;
begin
  Result := True;
  
  // Check if Shakshuka is already running
  if CheckForMutexes('ShakshukaMutex') then
  begin
    if MsgBox('Shakshuka is currently running. The installer will stop it before continuing.', mbConfirmation, MB_OKCANCEL) = IDOK then
    begin
      // Try to stop Shakshuka processes with multiple methods
      Exec('taskkill', '/F /IM Shakshuka.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      Exec('taskkill', '/F /IM python.exe /FI "WINDOWTITLE eq Shakshuka*"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      Exec('taskkill', '/F /IM python.exe /FI "COMMANDLINE eq *main.py*"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      Exec('taskkill', '/F /IM python.exe /FI "COMMANDLINE eq *app.py*"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      
      // Also try to kill any processes with "shakshuka" in the command line
      Exec('taskkill', '/F /IM python.exe /FI "COMMANDLINE eq *shakshuka*"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      
      Sleep(3000); // Wait longer for processes to terminate
      
      // Check if processes are still running and try again
      if CheckForMutexes('ShakshukaMutex') then
      begin
        if MsgBox('Shakshuka is still running. Do you want to force close it?', mbConfirmation, MB_YESNO) = IDYES then
        begin
          // Force kill with more aggressive methods
          Exec('taskkill', '/F /T /IM Shakshuka.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
          Exec('taskkill', '/F /T /IM python.exe /FI "WINDOWTITLE eq Shakshuka*"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
          Sleep(2000);
        end
        else
        begin
          Result := False;
        end;
      end;
    end
    else
    begin
      Result := False;
    end;
  end;
  
  // Check for existing installation
  if RegQueryStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppName}_is1', 'UninstallString', UninstallString) then
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
    
    // Ask if user wants to keep data
    if MsgBox('Do you want to keep your Shakshuka data (tasks, settings, etc.)?', mbConfirmation, MB_YESNO) = IDNO then
    begin
      DelTree(ExpandConstant('{userappdata}\Shakshuka'), True, True, True);
    end;
  end;
end;






