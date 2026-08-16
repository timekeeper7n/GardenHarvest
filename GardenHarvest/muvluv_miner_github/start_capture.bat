@echo off
chcp 65001 >nul
cd /d %~dp0
echo ============================================
echo  截图工具：游戏窗口在前台时按 F2 截图
echo  截图保存在 screenshots 文件夹，按 F10 退出
echo ============================================
python tools\capture_tool.py
pause
