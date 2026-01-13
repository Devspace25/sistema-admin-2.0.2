; Script de Inno Setup para Sistema Admin
; Generado automticamente

#define MyAppName "Sistema Admin"
#define MyAppVersion "2.0.2"
#define MyAppPublisher "DevSpace25"
#define MyAppExeName "SistemaAdmin.exe"

[Setup]
; Identificador unico - no cambiar en futuras versiones
AppId={{A87D0392-4DA0-4813-9114-04F123456789}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Carpeta donde se guardara el instalador generado
OutputDir=releases
OutputBaseFilename=SistemaAdmin_Setup_v{#MyAppVersion}
; Icono del instalador (debe existir)
; SetupIconFile=assets\icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; Requiere permisos de administrador para instalar en Program Files
PrivilegesRequired=admin

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Archivos principales de la aplicacion (generados por PyInstaller en dist/SistemaAdmin)
Source: "dist\SistemaAdmin\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTA: Incluye automaticamente la carpeta alembic y alembic.ini si estan en dist/SistemaAdmin

; Configuracion y recursos adicionales
Source: ".env"; DestDir: "{app}"; Flags: ignoreversion
Source: "Formato Recibo\*"; DestDir: "{app}\Formato Recibo"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Ejecutar la aplicacion al finalizar la instalacion
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Dirs]
; Asegurar que existan carpetas de datos si fueran necesarias (aunque la app las crea)
Name: "{app}\data"; Permissions: users-modify


