@echo off
echo 正在启动 IndexTTS WebUI...
cd /d %~dp0
uv run python -m webui.app
pause 