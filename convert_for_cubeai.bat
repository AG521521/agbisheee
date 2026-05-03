@echo off
echo 🚀 开始转换模型为Cube.AI格式...

REM 检查文件是否存在
if not exist "plant_growth_model.onnx" (
    echo ❌ 错误: 找不到 plant_growth_model.onnx
    pause
    exit /b 1
)

echo ✅ 找到ONNX模型文件

REM 检查模型大小
for %%F in ("plant_growth_model.onnx") do set MODEL_SIZE=%%~zF
echo 📊 模型大小: %MODEL_SIZE% 字节

if %MODEL_SIZE% GTR 50000 (
    echo ⚠️ 警告: 模型可能太大，建议简化
)

echo.
echo 📋 Cube.AI部署步骤:
echo 1. 打开STM32CubeMX 6.15.0
echo 2. 创建STM32G071RB工程
echo 3. 安装X-CUBE-AI扩展包
echo 4. 在Middleware中启用X-CUBE-AI
echo 5. 点击"Add Network"，选择plant_growth_model.onnx
echo 6. 配置量化选项 (推荐FP16)
echo 7. 生成代码
echo.
echo 💡 提示:
echo - 确保Cube.AI版本 ^>= 7.0.0
echo - 如果遇到内存问题，尝试INT8量化
echo - 生成代码后检查ai_interface.c文件
echo.
echo 🎉 转换完成！现在可以在CubeMX中导入模型了。
pause
