@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Kontrola elektro vykresu

REM ============================================================
REM  Zkopiruj tento soubor do slozky s DWG vykresy a spust ho.
REM  Vygeneruje export i kontrolu primo do teto slozky.
REM ============================================================

REM Slozka, kde lezi tento .bat = slozka ke kontrole
set "TARGET=%~dp0"
if "%TARGET:~-1%"=="\" set "TARGET=%TARGET:~0,-1%"

REM Umisteni skriptu (uprav, pokud presunes slozku elektro_check)
set "TOOLS=D:\CLAUDE_CODE\elektro_check"

echo ================================================================
echo  Kontrola a export elektro vykresu
echo  Slozka: "%TARGET%"
echo ================================================================
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo [CHYBA] Python launcher 'py' nenalezen. Nainstaluj Python z python.org
  echo.
  pause
  exit /b 1
)

if not exist "%TOOLS%\export_all.py" (
  echo [CHYBA] Nenalezeny skripty v: %TOOLS%
  echo Uprav radek "set TOOLS=..." v tomto .bat na spravnou cestu.
  echo.
  pause
  exit /b 1
)

echo [1/2] Kompletni export ^(export_full.xlsx + export_csv^)...
echo.
py "%TOOLS%\export_all.py" "%TARGET%"
echo.

echo [2/2] Kontrola vykresu ^(report_dwg.xlsx^)...
echo.
py "%TOOLS%\dwg_checker.py" "%TARGET%"
echo.

echo ================================================================
echo  HOTOVO. Vystupy v teto slozce:
echo    - export_full.xlsx   (vsechna data, 7 listu)
echo    - export_csv\         (CSV verze)
echo    - report_dwg.xlsx     (nalezene chyby)
echo ================================================================
echo.
pause
endlocal
