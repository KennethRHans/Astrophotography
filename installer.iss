[Setup]
AppId=Seestar Studio Preview
AppName=Seestar Studio Preview
AppVersion=0.5.0
DefaultDirName={autopf}\Seestar Studio
UsePreviousAppDir=no
DefaultGroupName=Seestar Studio
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=installer
OutputBaseFilename=SeestarStudio-0.5.0-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
[Files]
Source: "dist\SeestarStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Seestar Studio"; Filename: "{app}\SeestarStudio.exe"; WorkingDir: "{app}"; AppUserModelID: "SeestarStudio.Desktop"
Name: "{autodesktop}\Seestar Studio"; Filename: "{app}\SeestarStudio.exe"; WorkingDir: "{app}"; AppUserModelID: "SeestarStudio.Desktop"; Tasks: desktopicon
[Run]
Filename: "{app}\SeestarStudio.exe"; Description: "Launch Seestar Studio (right-click its taskbar icon to pin it)"; Flags: nowait postinstall skipifsilent runasoriginaluser
[Code]
procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID <> wpFinished then Exit;
  WizardForm.FinishedLabel.Caption :=
    'Seestar Studio has been installed.' + #13#10 + #13#10 +
    'To pin it to the taskbar: launch Seestar Studio, right-click its taskbar icon, and choose Pin to taskbar.';
end;
