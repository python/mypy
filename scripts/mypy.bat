@echo off

setlocal
"%~dp0..\python" "%~dp0mypy" %*
endlocal
