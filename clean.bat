@echo off
chcp 65001 >nul 2>&1
title RMBG-2-Studio Cleanup

echo ================================================
echo   RMBG-2-Studio Cleanup
echo ================================================
echo.
echo This will delete:
echo   - All processed images
echo   - The AI model cache (~176MB)
echo.
set /p CONFIRM="Continue? (Y/N): "
if /i not "%CONFIRM%"=="Y" (
    echo Cleanup cancelled.
    pause
    exit /b 0
)

echo.

:: Delete processed images (keep the directory)
echo Deleting processed images...
if exist "%~dp0output_images" (
    del /q "%~dp0output_images\*" >nul 2>&1
    echo Processed images deleted.
) else (
    echo No output_images directory found.
)

:: Delete model cache
echo Deleting model cache...
if exist "%USERPROFILE%\.cache\huggingface\hub\models--cocktailpeanut--rm" (
    rd /s /q "%USERPROFILE%\.cache\huggingface\hub\models--cocktailpeanut--rm"
    echo Model cache deleted.
) else (
    echo No model cache found.
)

echo.
echo ================================================
echo   Cleanup complete!
echo ================================================
echo.
echo   Run setup.bat again to re-download the
echo   model if needed.
echo.
echo ================================================
echo.

pause