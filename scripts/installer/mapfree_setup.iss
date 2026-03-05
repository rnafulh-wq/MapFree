; MapFree Engine Windows Installer (Inno Setup)
; Build: run iscc from repo root: iscc scripts/installer/mapfree_setup.iss
; Requires: PyInstaller output in dist/MapFree/

#define MyAppName "MapFree Engine"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "MapFree"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\MapFree
DefaultGroupName=MapFree
OutputDir=Output
OutputBaseFilename=MapFree-Setup-{#MyAppVersion}
SetupIconFile=..\..\mapfree\gui\resources\icons\mapfree.ico
UninstallDisplayIcon={app}\MapFree.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "indonesian"; MessagesFile: "compiler:Languages\Indonesian.isl"

[Tasks]
Name: "desktopicon"; Description: "Buat shortcut di Desktop"; GroupDescription: "Shortcut:"; Flags: unchecked
Name: "startmenuicon"; Description: "Tambahkan ke Start Menu"; GroupDescription: "Shortcut:"; Flags: checkedonce

[Files]
Source: "..\..\dist\MapFree\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\MapFree Engine"; Filename: "{app}\MapFree.exe"
Name: "{userdesktop}\MapFree Engine"; Filename: "{app}\MapFree.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MapFree.exe"; Description: "Jalankan MapFree Engine"; Flags: postinstall nowait skipifsilent

[Code]
var
  HardwarePage: TOutputMsgMemoWizardPage;
  ComponentsPage: TOutputMsgMemoWizardPage;
  CheckCOLMAP: TNewCheckBox;
  CheckOpenMVS: TNewCheckBox;
  CheckPDAL: TNewCheckBox;
  LabelTotalSize: TNewStaticText;
  WantOpenMVS: Boolean;
  WantPDAL: Boolean;

procedure CurPageChanged(CurPageID: Integer);
var
  TotalMB: Integer;
begin
  if CurPageID = ComponentsPage.ID then
  begin
    TotalMB := 180;
    if CheckOpenMVS.Checked then TotalMB := TotalMB + 85;
    if CheckPDAL.Checked then TotalMB := TotalMB + 200;
    LabelTotalSize.Caption := 'Total download (first run): ' + IntToStr(TotalMB) + ' MB';
  end;
end;

procedure InitializeWizard;
begin
  { Hardware info page }
  HardwarePage := CreateOutputMsgMemoPage(wpWelcome,
    'Deteksi Hardware', 'MapFree akan mendeteksi GPU dan sistem Anda saat pertama dijalankan',
    'Pada peluncuran pertama, MapFree akan mendeteksi GPU (NVIDIA/AMD/Intel) dan mengunduh COLMAP yang sesuai (CUDA atau CPU-only) serta komponen opsional yang Anda pilih di halaman berikut.' + #13#10 + #13#10 +
    'Tidak perlu konfigurasi manual.',
    ''
  );

  { Component selection page }
  ComponentsPage := CreateOutputMsgMemoPage(HardwarePage.ID,
    'Pilih Komponen', 'Pilih komponen yang akan diunduh saat pertama menjalankan MapFree',
    'COLMAP wajib. Komponen lain opsional.',
    ''
  );
  CheckCOLMAP := TNewCheckBox.Create(ComponentsPage);
  CheckCOLMAP.Parent := ComponentsPage.Surface;
  CheckCOLMAP.Left := ScaleX(8);
  CheckCOLMAP.Top := ScaleY(100);
  CheckCOLMAP.Width := ScaleX(400);
  CheckCOLMAP.Caption := 'COLMAP (Wajib) — versi CUDA atau CPU dipilih otomatis sesuai GPU';
  CheckCOLMAP.Checked := True;
  CheckCOLMAP.Enabled := False;

  CheckOpenMVS := TNewCheckBox.Create(ComponentsPage);
  CheckOpenMVS.Parent := ComponentsPage.Surface;
  CheckOpenMVS.Left := ScaleX(8);
  CheckOpenMVS.Top := ScaleY(130);
  CheckOpenMVS.Width := ScaleX(400);
  CheckOpenMVS.Caption := 'OpenMVS (Opsional) — untuk mesh 3D berkualitas tinggi (~85 MB)';
  CheckOpenMVS.Checked := False;

  CheckPDAL := TNewCheckBox.Create(ComponentsPage);
  CheckPDAL.Parent := ComponentsPage.Surface;
  CheckPDAL.Left := ScaleX(8);
  CheckPDAL.Top := ScaleY(160);
  CheckPDAL.Width := ScaleX(400);
  CheckPDAL.Caption := 'PDAL + GDAL (Opsional) — untuk DTM dan orthophoto (~200 MB)';
  CheckPDAL.Checked := False;

  LabelTotalSize := TNewStaticText.Create(ComponentsPage);
  LabelTotalSize.Parent := ComponentsPage.Surface;
  LabelTotalSize.Left := ScaleX(8);
  LabelTotalSize.Top := ScaleY(200);
  LabelTotalSize.Caption := 'Total download (first run): 180 MB';
  LabelTotalSize.AutoSize := True;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = ComponentsPage.ID then
  begin
    WantOpenMVS := CheckOpenMVS.Checked;
    WantPDAL := CheckPDAL.Checked;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  JsonPath: String;
  JsonContent: AnsiString;
begin
  if CurStep = ssPostInstall then
  begin
    JsonPath := ExpandConstant('{app}\components.json');
    JsonContent := '{"colmap":true,"openmvs":' + LowerCase(BoolToStr(WantOpenMVS, True)) +
      ',"pdal_gdal":' + LowerCase(BoolToStr(WantPDAL, True)) + '}';
    SaveStringToFile(JsonPath, JsonContent, False);
  end;
end;
