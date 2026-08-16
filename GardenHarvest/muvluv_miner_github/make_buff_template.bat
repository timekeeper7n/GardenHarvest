@echo off
chcp 65001 >nul
cd /d %~dp0
echo ============================================================
echo  制作 buff SELECT 模板
echo  先用 start_capture.bat 在 buff 界面按F2截一张图,
echo  然后运行本工具框选最右边buff的 SELECT 蓝色按钮:
echo    1. 鼠标拖框框住 SELECT, 按回车(Enter)确认
echo    2. 输入名字: buff_select  (回车)
echo    3. 按 ESC 关闭窗口
echo ============================================================
if not exist "screenshots\shot_*.png" (
  echo [提示] screenshots 里没有截图, 请先运行 start_capture.bat 截图。
  pause
  exit /b
)
for /f "delims=" %%f in ('dir /b /o-d screenshots\shot_*.png ^| findstr /v "_raw"') do set LATEST=%%f
python tools\crop_tool.py screenshots\%LATEST%
pause
