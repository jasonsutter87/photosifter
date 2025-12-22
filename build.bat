@echo off
REM Build PhotoSift for Windows distribution

echo Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

echo Building executable...
pyinstaller photosift.spec --clean

echo Done! Executable is in dist\PhotoSift.exe
pause
