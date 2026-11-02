[Setup]
AppId=Seestar Studio Preview
AppName=Astro Studio for Seestar
AppVersion=0.10.0
DefaultDirName={autopf}\Astro Studio for Seestar
UsePreviousAppDir=yes
DefaultGroupName=Astro Studio for Seestar
UsePreviousGroup=no
UninstallDisplayIcon={app}\AstroStudioForSeestar.exe
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=installer
OutputBaseFilename=AstroStudioForSeestar-0.10.0-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
[Files]
Source: "dist\AstroStudioForSeestar\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[InstallDelete]
; Keep the stable AppId above so Windows upgrades the existing app entry.
; Delete only the old executable and app-created shortcuts, never user images.
Type: files; Name: "{app}\SeestarStudio.exe"
Type: files; Name: "{commondesktop}\Seestar Studio.lnk"
Type: files; Name: "{commonprograms}\Seestar Studio\Seestar Studio.lnk"
Type: dirifempty; Name: "{commonprograms}\Seestar Studio"
[Icons]
Name: "{group}\Astro Studio for Seestar"; Filename: "{app}\AstroStudioForSeestar.exe"; WorkingDir: "{app}"; AppUserModelID: "AstroStudioForSeestar.Desktop"
Name: "{autodesktop}\Astro Studio for Seestar"; Filename: "{app}\AstroStudioForSeestar.exe"; WorkingDir: "{app}"; AppUserModelID: "AstroStudioForSeestar.Desktop"; Tasks: desktopicon
[Run]
Filename: "{app}\AstroStudioForSeestar.exe"; Description: "Launch Astro Studio for Seestar (right-click its taskbar icon to pin it)"; Flags: nowait postinstall skipifsilent runasoriginaluser
[Code]
procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID <> wpFinished then Exit;
  WizardForm.FinishedLabel.Caption :=
    'Astro Studio for Seestar has been installed.' + #13#10 + #13#10 +
    'To pin it to the taskbar: launch Astro Studio for Seestar, right-click its taskbar icon, and choose Pin to taskbar.';
end;
