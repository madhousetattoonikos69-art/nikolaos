#define MyAppName "GreekDub AI"
#define MyAppVersion "0.1.0"
[Setup]
AppId={{D22C12AA-CA71-49D0-A833-7A29A78C3E92}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\GreekDub AI
DefaultGroupName=GreekDub AI
OutputDir=dist
OutputBaseFilename=GreekDubAI_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
[Files]
Source: "dist\GreekDubAI\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
[Icons]
Name: "{autoprograms}\GreekDub AI"; Filename: "{app}\GreekDubAI.exe"
Name: "{autodesktop}\GreekDub AI"; Filename: "{app}\GreekDubAI.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Εικονίδιο στην επιφάνεια εργασίας"; Flags: unchecked
[Run]
Filename: "{app}\GreekDubAI.exe"; Description: "Άνοιγμα GreekDub AI"; Flags: nowait postinstall skipifsilent
