@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem ============================================================
rem  文本转向量 · 一条文本 -> 384 维 base64
rem  内置 Python 与模型，解压即用，不联网、不装依赖
rem ============================================================

set "HERE=%~dp0"
set "PY=%HERE%python\python.exe"
set "EMBED=%HERE%embed.py"
set "TMPOUT=%TEMP%\t2v_out.txt"
set "TMPERR=%TEMP%\t2v_err.txt"

if not exist "%PY%" (
    echo [x] 找不到内置的 python\python.exe
    echo     请把整个文件夹一起解压出来再运行，不要单独拷走这个 cmd。
    pause
    exit /b 1
)
if not exist "%EMBED%" (
    echo [x] 找不到 embed.py，同样请确认是整个文件夹一起解压的。
    pause
    exit /b 1
)

if /i "%~1"=="--check" goto :check
if /i "%~1"=="/check" goto :check
if /i "%~1"=="-c" goto :check
if not "%~1"=="" goto :once

rem ---------- 无参数：交互输入 ----------
:loop
echo.
echo ============================================================
echo   文本转向量   384 维 / base64   （直接回车退出）
echo ============================================================
set "TXT="
set /p "TXT=请输入文本: "
if not defined TXT goto :done

call :run "%TXT%"
goto :loop

:once
rem ---------- 有参数：直接算，标准输出只有 base64 ----------
"%PY%" "%EMBED%" %* 
rem 换行只走 stderr，避免污染 PowerShell 赋值
>&2 echo.
exit /b %errorlevel%

:check
"%PY%" "%EMBED%" --check
echo.
pause
exit /b 0

:run
set "TXT=%~1"
if "%TXT%"=="" exit /b 1
"%PY%" "%EMBED%" "%TXT%" > "%TMPOUT%" 2> "%TMPERR%"
if errorlevel 1 (
    echo.
    echo [x] 计算失败：
    type "%TMPERR%"
    del "%TMPOUT%" "%TMPERR%" >nul 2>nul
    exit /b 1
)
set "OUT="
set /p OUT=<"%TMPOUT%"
del "%TMPOUT%" "%TMPERR%" >nul 2>nul
echo.
echo ---- base64 向量（已复制到剪贴板）----
echo !OUT!
echo --------------------------------------
echo !OUT! | clip
exit /b 0

:done
endlocal
exit /b 0
