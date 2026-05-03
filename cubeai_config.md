# Cube.AI Configuration for Plant Growth Model

## 1. 项目设置
PROJECT_NAME = "PlantGrowthPredictor"
TARGET_DEVICE = "STM32G071RB"
CLOCK_FREQUENCY = 64  # MHz
RAM_SIZE = 36  # KB
FLASH_SIZE = 128  # KB

## 2. 模型信息
MODEL_TYPE = "ONNX"
MODEL_FILE = "plant_growth_model.onnx"
INPUT_SHAPE = [1, 7]
OUTPUT_SHAPE = [1, 2]

## 3. Cube.AI设置
### 3.1 量化设置
QUANTIZATION = "FP16"  # 或者 "INT8" (更小但精度较低)
CALIBRATION_DATA = "calibration_data.csv"

### 3.2 内存优化
USE_STATIC_MEMORY = true
OPTIMIZATION_LEVEL = 3

### 3.3 运行时设置
USE_CMSIS_NN = true  # 使用CMSIS-NN加速
USE_HEAP = false  # 避免使用堆内存

## 4. 输入/输出配置
### 4.1 输入特征
INPUT_FEATURES = [
    {"name": "Sunlight_Hours", "type": "float", "range": [0.0, 24.0]},
    {"name": "Temperature", "type": "float", "range": [-10.0, 50.0]},
    {"name": "Humidity", "type": "float", "range": [0.0, 100.0]},
    {"name": "Soil_Type", "type": "int32", "mapping": {"sandy": 0, "loam": 1, "clay": 2}},
    {"name": "Water_Frequency", "type": "int32", "mapping": {"weekly": 0, "bi-weekly": 1, "daily": 2}},
    {"name": "Fertilizer_Type", "type": "int32", "mapping": {"none": 0, "organic": 1, "chemical": 2}},
    {"name": "Environment_Score", "type": "float", "range": [0.0, 1.0]}
]

### 4.2 输出
OUTPUT_CLASSES = ["未达标", "已达标"]

## 5. CubeMX配置步骤

### 步骤1: 安装Cube.AI
1. 打开STM32CubeMX 6.15.0
2. 点击 Help -> Manage embedded software packages
3. 安装 X-CUBE-AI 扩展包

### 步骤2: 创建工程
1. 选择STM32G071RB
2. 配置系统时钟到64MHz
3. 启用USART2用于调试输出

### 步骤3: 添加AI模型
1. 在Software Packs中启用X-CUBE-AI
2. 点击 "Add Network"
3. 选择生成的 plant_growth_model.onnx 文件
4. 配置参数:
   - Compression: FP16
   - Network Runtime: STM32
   - Validation: Enable

### 步骤4: 生成代码
1. 点击 Generate Code
2. CubeMX会自动生成包含AI模型的代码

## 6. 内存使用估算
- 模型权重: ~5-10 KB
- 激活内存: ~2-3 KB
- 运行时内存: ~5 KB
- 总计: ~15 KB (在STM32G071RB能力范围内)

## 7. 性能估算
- 推理时间: ~10-20 ms
- 每秒推理次数: 50-100次
- 功耗: < 5 mA (推理时)

## 8. 验证方法
1. 使用提供的 test_model.py 验证精度
2. 在Cube.AI Analyzer中验证内存使用
3. 在目标硬件上验证实时性能

## 9. 故障排除
### 问题1: 内存不足
- 解决方案: 使用INT8量化或减小网络大小

### 问题2: 精度损失太大
- 解决方案: 使用FP16量化或增加校准数据

### 问题3: Cube.AI无法导入ONNX
- 解决方案: 确保ONNX opset <= 11
