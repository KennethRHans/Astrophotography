[Setup]
AppId=Seestar Studio Preview
AppName=Easy Astro Studio
AppVersion=0.16.0
DefaultDirName={autopf}\Easy Astro Studio
UsePreviousAppDir=yes
DefaultGroupName=Easy Astro Studio
UsePreviousGroup=no
UninstallDisplayIcon={app}\EasyAstroStudio.exe
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=installer
OutputBaseFilename=EasyAstroStudio-0.16.0-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
[Files]
Source: "dist\EasyAstroStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[InstallDelete]
; Keep the stable AppId above so Windows upgrades the existing app entry.
; Delete only the old executable and app-created shortcuts, never user images.
Type: files; Name: "{app}\SeestarStudio.exe"
Type: files; Name: "{app}\AstroStudioForSeestar.exe"
Type: files; Name: "{commondesktop}\Astro Studio for Seestar.lnk"
Type: files; Name: "{commonprograms}\Astro Studio for Seestar\Astro Studio for Seestar.lnk"
Type: dirifempty; Name: "{commonprograms}\Astro Studio for Seestar"
Type: files; Name: "{commondesktop}\Seestar Studio.lnk"
Type: files; Name: "{commonprograms}\Seestar Studio\Seestar Studio.lnk"
Type: dirifempty; Name: "{commonprograms}\Seestar Studio"
[Icons]
Name: "{group}\Easy Astro Studio"; Filename: "{app}\EasyAstroStudio.exe"; WorkingDir: "{app}"; AppUserModelID: "EasyAstroStudio.Desktop"
Name: "{autodesktop}\Easy Astro Studio"; Filename: "{app}\EasyAstroStudio.exe"; WorkingDir: "{app}"; AppUserModelID: "EasyAstroStudio.Desktop"; Tasks: desktopicon
[Run]
Filename: "{app}\EasyAstroStudio.exe"; Description: "Launch Easy Astro Studio (right-click its taskbar icon to pin it)"; Flags: nowait postinstall skipifsilent runasoriginaluser
[Code]
procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID <> wpFinished then Exit;
  WizardForm.FinishedLabel.Caption :=
    'Easy Astro Studio has been installed.' + #13#10 + #13#10 +
    'To pin it to the taskbar: launch Easy Astro Studio, right-click its taskbar icon, and choose Pin to taskbar.';
end;
