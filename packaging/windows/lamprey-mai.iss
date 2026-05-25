; Inno Setup script for Lamprey MAI on Windows.
;
; Status: SCAFFOLD ONLY. Not yet built or signed. PACKAGING-01 will
; harden this — see packaging/windows/README.md.
;
; Build (from the repo root, with Inno Setup 6 installed):
;   ISCC.exe packaging\windows\lamprey-mai.iss
;
; Inputs expected next to the .iss file at build time:
;   bin\lamprey-mai.exe       (front-door launcher; this crate)
;   bin\lamprey-mai-api.exe   (headless inference + compliance daemon)
;   bin\lamprey-mai-admin.exe (CLI: demos, audit, ops)
;
; The wizard splash uses the canonical install-screen asset embedded
; under docs/assets/.

#define MyAppName       "Lamprey MAI"
#define MyAppPublisher  "Island Mountain (USS-Parks LLC)"
#define MyAppURL        "https://islandmountain.io"
#define MyAppVersion    "1.1.1"
#define MyAppExeName    "lamprey-mai.exe"

[Setup]
AppId={{4F4D2A55-5F4E-4D60-9D8A-1A5A1A5A1A5A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\Lamprey MAI
DefaultGroupName=Lamprey MAI
DisableProgramGroupPage=yes
OutputBaseFilename=lamprey-mai-setup-{#MyAppVersion}
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
; Splash screens: the install-screen PNG is the gold "LAMPREY MAI"
; badge that brackets the wizard.
WizardImageFile=..\..\docs\assets\lamprey-mai-install-screen.png
WizardSmallImageFile=..\..\docs\assets\lamprey-mai-install-screen.png
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "bin\lamprey-mai.exe";       DestDir: "{app}"; Flags: ignoreversion
Source: "bin\lamprey-mai-api.exe";   DestDir: "{app}"; Flags: ignoreversion
Source: "bin\lamprey-mai-admin.exe"; DestDir: "{app}"; Flags: ignoreversion
; Asset payload used by the launcher's splash + banner. These are baked
; into the exe via include_bytes! so duplicating them at install time
; is optional — kept here for operator inspection.
Source: "..\..\docs\assets\lamprey-startup-image.png";     DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\..\docs\assets\lamprey-mai-install-screen.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\..\docs\assets\lamprey-banner.txt";            DestDir: "{app}\assets"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}";        Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}";  Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Lamprey MAI"; Flags: nowait postinstall skipifsilent
