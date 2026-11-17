; SwiftDownloader Inno Setup Script
; Generates SwiftDownloader_Setup.exe

#define MyAppName "SwiftDownloader"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "SwiftDownloader Contributors"
#define MyAppURL "https://github.com/swiftdownloader/swiftdownloader"
#define MyAppExeName "SwiftDownloader.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
LicenseFile=..\LICENSE
OutputDir=Output
OutputBaseFilename=SwiftDownloader_Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequiredOverridesAllowed=dialog
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupentry"; Description: "Start SwiftDownloader with Windows"; GroupDescription: "System integration:"
Name: "nativemessaging"; Description: "Install browser integration (Chrome, Edge, Firefox)"; GroupDescription: "Browser integration:"

[Files]
; Main application files (from PyInstaller output)
Source: "..\dist\SwiftDownloader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

; Native messaging host
Source: "..\browser_extensions\native_host\native_host.py"; DestDir: "{app}\native_host"; Flags: ignoreversion
Source: "..\browser_extensions\native_host\com.swiftdownloader.host.json"; DestDir: "{app}\native_host"; Flags: ignoreversion

; Browser extensions
Source: "..\browser_extensions\chrome\*"; DestDir: "{app}\extensions\chrome"; Flags: ignoreversion recursesubdirs
Source: "..\browser_extensions\firefox\*"; DestDir: "{app}\extensions\firefox"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch SwiftDownloader"; Flags: nowait postinstall skipifsilent

[Registry]
; Native messaging host registration for Chrome/Edge
Root: HKCU; Subkey: "Software\Google\Chrome\NativeMessagingHosts\com.swiftdownloader.host"; ValueType: string; ValueData: "{app}\native_host\com.swiftdownloader.host.json"; Flags: uninsdeletekey; Tasks: nativemessaging
Root: HKCU; Subkey: "Software\Microsoft\Edge\NativeMessagingHosts\com.swiftdownloader.host"; ValueType: string; ValueData: "{app}\native_host\com.swiftdownloader.host.json"; Flags: uninsdeletekey; Tasks: nativemessaging

; Startup entry
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"" --minimized"; Flags: uninsdeletevalue; Tasks: startupentry

[UninstallDelete]
Type: dirifempty; Name: "{app}"

[Code]
// Architecture detection at install time
function IsX64: Boolean;
begin
  Result := IsX64Compatible;
end;

function InitializeSetup: Boolean;
begin
  if not IsX64 then
  begin
    MsgBox('SwiftDownloader requires a 64-bit version of Windows 10 or later.', mbError, MB_OK);
    Result := False;
  end
  else
    Result := True;
end;

// Ask user whether to remove app data on uninstall
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if MsgBox('Do you want to remove your SwiftDownloader settings and download history?',
              mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
    begin
      DelTree(ExpandConstant('{localappdata}\SwiftDownloader'), True, True, True);
    end;
  end;
end;
