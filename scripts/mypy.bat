@echo off

setlocal
if exist "%~dp0\python.exe" (
    "%~dp0\python" "%~dp0mypy" %*
) else (
    "%~dp0..\python" "%~dp0mypy" %*
)
endlocal
