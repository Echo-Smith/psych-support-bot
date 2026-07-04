@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "ROOT=%~dp0"
cd /d "%ROOT%"

echo ======================================
echo   心理学Bot 一键启动
echo ======================================
echo.

echo [1/5] 检查 Python...
where python >nul 2>nul
if errorlevel 1 (
    echo 未检测到 Python。
    echo.
    echo 请先安装 Python 3.12 或更高版本，然后重新双击本文件。
    echo 下载地址: https://www.python.org/downloads/
    echo 安装时请勾选 "Add Python to PATH"。
    echo.
    pause
    exit /b 1
)

echo [2/5] 检查 uv...
where uv >nul 2>nul
if errorlevel 1 (
    echo 未检测到 uv，正在自动安装...
    python -m pip install uv
    if errorlevel 1 (
        echo.
        echo uv 安装失败，请确认网络正常，或手动执行:
        echo python -m pip install uv
        echo.
        pause
        exit /b 1
    )
)

if not exist ".env" (
    if exist ".env.example" (
        copy /y ".env.example" ".env" >nul
        echo 已自动创建 .env 配置文件。
        echo 如果你有自己的 API Key，稍后可以用记事本打开 .env 进行填写。
        echo.
    )
)

echo [3/5] 安装或更新依赖...
call uv sync
if errorlevel 1 (
    echo.
    echo 依赖安装失败，请检查网络后重试。
    echo.
    pause
    exit /b 1
)

echo [4/5] 检查服务是否已启动...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/health' -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
if not errorlevel 1 (
    echo 检测到服务已经在运行，正在直接打开网页...
    start "" "http://127.0.0.1:8000"
    echo.
    echo 网页已尝试打开。如果没有自动弹出，请手动访问:
    echo http://127.0.0.1:8000
    echo.
    pause
    exit /b 0
)

echo [5/5] 启动服务并等待网页打开...
start "Psych Support Bot Server" cmd /k "cd /d ""%ROOT%"" && uv run uvicorn psych_support_bot.app:app --host 127.0.0.1 --port 8000"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$url = 'http://127.0.0.1:8000/health'; $deadline = (Get-Date).AddSeconds(60); do { try { $r = Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 2; if ($r.StatusCode -eq 200) { Start-Process 'http://127.0.0.1:8000'; exit 0 } } catch { } Start-Sleep -Seconds 1 } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 (
    echo.
    echo 服务启动超过 60 秒仍未就绪。
    echo 请查看刚才弹出的 "Psych Support Bot Server" 窗口，检查报错信息。
    echo 如果网页没有自动打开，也可以稍后手动访问:
    echo http://127.0.0.1:8000
    echo.
    pause
    exit /b 1
)

echo.
echo 启动完成，网页已自动打开。
echo 停止服务有两种方法:
echo 1. 直接关闭 "Psych Support Bot Server" 窗口
echo 2. 双击运行 "一键停止服务.bat"
echo.
pause
