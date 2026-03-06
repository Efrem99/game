#define AppName "King Wizard RPG"
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#define AppPublisher "AntiGravity Studios"
#define AppExeName "KingWizardRPG.exe"

[Setup]
AppId={{8B7C3450-5A2E-47D7-BB15-3DAB3AB5D4A2}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\King Wizard RPG
DefaultGroupName=King Wizard RPG
DisableProgramGroupPage=yes
OutputDir=..\out
OutputBaseFilename=KingWizardRPG_Setup_{#AppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\KingWizardRPG\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\King Wizard RPG"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall King Wizard RPG"; Filename: "{uninstallexe}"
Name: "{autodesktop}\King Wizard RPG"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,King Wizard RPG}"; Flags: nowait postinstall skipifsilent
