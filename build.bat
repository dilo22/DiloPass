@echo off
echo =============================================
echo  DiloPass - Build executable Windows
echo =============================================
echo.

:: Verifier que pyinstaller est installe
python -m PyInstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] PyInstaller non trouve. Installation...
    pip install pyinstaller
    echo.
)

:: Nettoyer les anciens builds
if exist "build" (
    echo [*] Nettoyage du dossier build...
    rmdir /s /q build
)
if exist "dist\DiloPass.exe" (
    echo [*] Suppression de l'ancien executable...
    del /f /q dist\DiloPass.exe
)

:: Lancer le build
echo [*] Compilation en cours...
echo.
python -m PyInstaller dilopass.spec

echo.
if exist "dist\DiloPass.exe" (
    echo [OK] Build reussi !
    echo [OK] Executable : dist\DiloPass.exe
    echo.
    echo Taille :
    for %%A in ("dist\DiloPass.exe") do echo   %%~zA octets
) else (
    echo [ERREUR] Le build a echoue. Voir les logs ci-dessus.
    exit /b 1
)

echo.
pause
