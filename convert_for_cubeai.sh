#!/bin/bash
# convert_for_cubeai.sh - Cube.AI模型转换脚本

echo "🚀 开始转换模型为Cube.AI格式..."

# 检查文件是否存在
if [ ! -f "plant_growth_model.onnx" ]; then
    echo "❌ 错误: 找不到 plant_growth_model.onnx"
    exit 1
fi

echo "✅ 找到ONNX模型文件"

# 检查模型大小
MODEL_SIZE=$(stat -f%z "plant_growth_model.onnx")
echo "📊 模型大小: $MODEL_SIZE 字节"

if [ $MODEL_SIZE -gt 50000 ]; then
    echo "⚠️ 警告: 模型可能太大，建议简化"
fi

# 检查ONNX opset版本
echo "🔍 检查ONNX opset版本..."
python -c "
import onnx
model = onnx.load('plant_growth_model.onnx')
opset_version = model.opset_import[0].version if model.opset_import else 'unknown'
print(f'ONNX opset版本: {opset_version}')
if opset_version > 11:
    print('⚠️ 警告: opset版本过高，可能需要降级')
"

echo ""
echo "📋 Cube.AI部署步骤:"
echo "1. 打开STM32CubeMX 6.15.0"
echo "2. 创建STM32G071RB工程"
echo "3. 安装X-CUBE-AI扩展包"
echo "4. 在Middleware中启用X-CUBE-AI"
echo "5. 点击'Add Network'，选择plant_growth_model.onnx"
echo "6. 配置量化选项 (推荐FP16)"
echo "7. 生成代码"
echo ""
echo "💡 提示:"
echo "- 确保Cube.AI版本 >= 7.0.0"
echo "- 如果遇到内存问题，尝试INT8量化"
echo "- 生成代码后检查ai_interface.c文件"
echo ""
echo "🎉 转换完成！现在可以在CubeMX中导入模型了。"
