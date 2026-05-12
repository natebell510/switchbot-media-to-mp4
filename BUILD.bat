@echo off
:: Build SwitchBot_Converter.exe from Python source
echo Checking Python...
python --version >nul 2>&1 || (echo Error: Python not found. Get it at https://www.python.org/downloads/ && pause && exit /b 1)

echo Installing build dependencies...
pip install pyinstaller tqdm || (echo Error: pip install failed. && pause && exit /b 1)

echo Building executable...
pyinstaller switchbot_converter.spec || (echo Error: PyInstaller failed. && pause && exit /b 1)

echo.
echo =====================================================
echo  Build complete!
echo  Executable: dist\SwitchBot_Converter.exe
echo =====================================================
pause
