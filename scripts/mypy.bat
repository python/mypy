@echo off

setlocal
if exist "%~dp0\python.exe" (
    "%~dp0\python" "-m" "mypy" %*
) else (
    "%~dp0..\python" "-m" "mypy" %*
)
endlocal
