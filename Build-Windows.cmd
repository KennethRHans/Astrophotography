@echo off
cd /d "%~dp0"
py -3.12 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python -m pip install -r requirements.txt "pyinstaller>=6.16,<7"
if errorlevel 1 goto fail
.venv\Scripts\python -m pip uninstall -y pytest
.venv\Scripts\python -m PyInstaller --noconfirm --clean --windowed --name EasyAstroStudio --version-file version_info.txt --add-data "assets;assets" --collect-data pyopencl --hidden-import sep --collect-submodules skimage.transform app.py
if errorlevel 1 goto fail
echo Ready: dist\EasyAstroStudio\EasyAstroStudio.exe
pause
exit /b 0
:fail
echo Build failed. See the error above. Python 3.12 x64 is required.
pause
exit /b 1
