@echo off
chcp 65001 > nul
echo ========================================
echo 🌿 智能植物生长监测系统 - 服务器启动
echo ========================================
echo.

REM 检查Python
python --version > nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到Python，请先安装Python 3.7+
    pause
    exit /b 1
)

REM 安装依赖（如果需要）
echo 📦 检查依赖包...
pip install -r requirements.txt > nul 2>&1

REM 启动服务器
echo 🚀 启动服务器...
echo.
python server.py

pause