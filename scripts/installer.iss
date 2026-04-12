; Inno Setup Script — Batikam Rénove
; Généré automatiquement par build_windows.ps1
; Ne pas éditer manuellement — utiliser les variables en haut.

#define AppName      "Batikam Renove"
#define AppVersion   "@VERSION@"
#define AppPublisher "Batikam"
#define AppExeName   "BatikamRenove.exe"
#define AppId        "{{A3F9C2D1-84B7-4E2A-9F3C-1D2E5A6B7C8D}"
#define SourceDir    "@SOURCEDIR@"
#define IconFile     "@ICONFILE@"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://batikam.fr
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=@OUTPUTDIR@
OutputBaseFilename=BatikamRenove-Setup-{#AppVersion}
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableWelcomePage=no
LicenseFile=
InfoBeforeFile=
InfoAfterFile=
ShowLanguageDialog=no
LanguageDetectionMethod=none

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon";    Description: "Créer une icône sur le bureau";      GroupDescription: "Icônes supplémentaires"; Flags: unchecked
Name: "startupicon";   Description: "Lancer au démarrage de Windows";     GroupDescription: "Démarrage automatique";  Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Menu Démarrer
Name: "{group}\{#AppName}";         Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"
Name: "{group}\Désinstaller {#AppName}"; Filename: "{uninstallexe}"
; Bureau (optionnel)
Name: "{autodesktop}\{#AppName}";   Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon
; Démarrage auto (optionnel)
Name: "{userstartup}\{#AppName}";   Filename: "{app}\{#AppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Lancer {#AppName} maintenant"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Ne supprime PAS les données utilisateur dans %APPDATA%\Batikam
; (DB, préférences) — intentionnel pour ne pas perdre les devis
Type: filesandordirs; Name: "{app}"
