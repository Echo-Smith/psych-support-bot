@echo off
setlocal EnableExtensions
chcp 65001 >nul

echo 正在关闭心理学Bot服务...

powershell -NoProfile -ExecutionPolicy Bypass -Command "$targets = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'uvicorn psych_support_bot\.app:app' -or $_.CommandLine -match 'psych_support_bot\.main' }; if (-not $targets) { Write-Host '没有发现正在运行的服务。'; exit 0 }; foreach ($item in $targets) { try { Stop-Process -Id $item.ProcessId -Force -ErrorAction Stop; Write-Host ('已关闭进程 PID: ' + $item.ProcessId) } catch { Write-Host ('关闭失败 PID: ' + $item.ProcessId) } }"

echo.
pause
