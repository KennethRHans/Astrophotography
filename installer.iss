[Setup]
AppName=Seestar Studio Preview
AppVersion=0.2.0
DefaultDirName={localappdata}\Programs\SeestarStudio
DefaultGroupName=Seestar Studio
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=SeestarStudio-0.2.0-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
[Files]
Source: "dist\SeestarStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Seestar Studio"; Filename: "{app}\SeestarStudio.exe"
[Run]
Filename: "{app}\SeestarStudio.exe"; Description: "Launch Seestar Studio"; Flags: nowait postinstall skipifsilent
