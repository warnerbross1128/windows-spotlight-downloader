@echo off
cd /d "%~dp0"
py -3 spotlight_downloader.py
if errorlevel 1 (
  python spotlight_downloader.py
)
