@echo off
set /p msg="Commit message: "
cd /d "%~dp0.."
git add .
git commit -m "%msg%"
git push
