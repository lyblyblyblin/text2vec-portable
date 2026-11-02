@echo off
chcp 65001 >nul
setlocal EnableExtensions

rem ============================================================
rem  可选安装：把模型接到 C:\paraphrase-multilingual-MiniLM-L12-v2-onnx-Q
rem  并在桌面生成一个快捷方式。
rem  不做这一步也能用（程序优先读自己旁边的 model 目录）。
rem ============================================================

set "HERE=%~dp0"
set "MODEL_SRC=%HERE%model"
set "MODEL_DIR=C:\paraphrase-multilingual-MiniLM-L12-v2-onnx-Q"
set "PY=%HERE%python\python.exe"

set "WHICH=%~1"
if /i "%WHICH%"=="/auto" goto :auto
if /i "%WHICH%"=="auto" goto :auto

echo.
echo ============================================================
echo  安装助手
echo ============================================================
echo   1. 模型接到 %MODEL_DIR%
echo      这样其它程序（比如笔记向量脚本）也能按默认路径找到它
echo   2. 桌面生成「文本转向量」快捷方式
echo.
echo   本工具本身是免安装的，做完这几步才能在其他目录直接调用。
echo.
choice /c YN /n /m "现在执行？[Y=是 / N=退出] "
if errorlevel 2 goto :eof

:auto
echo.
if not exist "%HERE%python\python.exe" (
    echo [x] 这个目录不完整：找不到 python\python.exe
    goto :end
)
if not exist "%MODEL_SRC%\model_optimized.onnx" (
    echo [x] 这个目录不完整：找不到 model\model_optimized.onnx
    goto :end
)

echo [1/3] 处理默认模型目录 ...
if exist "%MODEL_DIR%\model_optimized.onnx" (
    echo       已存在，跳过
    goto :shortcut
)
if exist "%MODEL_DIR%" (
    echo       目录已存在但没有模型，直接写入 ...
    goto :copy
)
mklink /J "%MODEL_DIR%" "%MODEL_SRC%" >nul 2>nul
if exist "%MODEL_DIR%\model_optimized.onnx" (
    echo       已建立目录联接（不占额外空间）
    goto :shortcut
)
:copy
echo       建立联接失败，改为复制（约 240MB，稍等）...
xcopy "%MODEL_SRC%" "%MODEL_DIR%\" /e /i /y /q >nul
if exist "%MODEL_DIR%\model_optimized.onnx" (
    echo       复制完成
) else (
    echo       [x] 复制失败，请手动把 model 目录复制到 %MODEL_DIR%
)

:shortcut
echo [2/3] 生成桌面快捷方式 ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d '文本转向量.lnk')); $s.TargetPath='%HERE%向量.cmd'; $s.WorkingDirectory='%HERE%'; $s.IconLocation='%SystemRoot%\System32\shell32.dll,167'; $s.Description='文本转 384 维向量 base64'; $s.Save()" >nul 2>nul
if exist "%USERPROFILE%\Desktop\文本转向量.lnk" (
    echo       已放到桌面
) else if exist "%USERPROFILE%\OneDrive\Desktop\文本转向量.lnk" (
    echo       已放到桌面（OneDrive）
) else (
    echo       [i] 快捷方式没建成，可直接双击本目录的 向量.cmd
)

echo [3/3] 自检 ...
echo.
"%PY%" "%HERE%embed.py" --check
echo.

:end
echo.
pause
endlocal
exit /b 0
