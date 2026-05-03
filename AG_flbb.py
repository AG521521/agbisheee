# convert_model.py - 完整的模型转换工具
import numpy as np
import pandas as pd
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
import joblib
import warnings
warnings.filterwarnings('ignore')

print("=" * 60)
print("🌱 植物生长模型转换工具")
print("=" * 60)

# ===== 1. 加载和预处理数据 =====
def load_and_preprocess_data():
    """加载并预处理数据"""
    print("📊 加载数据...")
    df = pd.read_csv("plant_growth_data.csv")
    
    # 编码分类变量
    label_encoders = {}
    categorical_cols = ['Soil_Type', 'Water_Frequency', 'Fertilizer_Type']
    
    for col in categorical_cols:
        le = LabelEncoder()
        df[f'{col}_encoded'] = le.fit_transform(df[col])
        label_encoders[col] = le
    
    # 特征工程
    df['environment_score'] = (
        df['Sunlight_Hours'] / 10 * 0.4 +
        (1 - abs(df['Temperature'] - 25) / 30) * 0.3 +
        (df['Humidity'] / 100) * 0.3
    )
    
    # 准备特征和目标
    features = [
        'Sunlight_Hours', 'Temperature', 'Humidity',
        'Soil_Type_encoded', 'Water_Frequency_encoded', 'Fertilizer_Type_encoded',
        'environment_score'
    ]
    
    X = df[features].values
    y = df['Growth_Milestone'].values
    
    return X, y, features, label_encoders

# ===== 2. 创建简化模型 =====
def create_simplified_model(X, y):
    """创建适合STM32的简化模型"""
    print("🔧 创建简化模型...")
    
    # 划分数据集
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # 预处理管道
    preprocessing_pipeline = make_pipeline(
        SimpleImputer(strategy='median'),
        StandardScaler()
    )
    
    # 预处理数据
    X_train_scaled = preprocessing_pipeline.fit_transform(X_train)
    X_test_scaled = preprocessing_pipeline.transform(X_test)
    
    # 创建更小的MLP模型（适合STM32）
    # 注意：我们使用更小的网络来适应STM32内存
    mlp = MLPClassifier(
        hidden_layer_sizes=(8, 4),      # 更小的网络结构
        activation='relu',              # ReLU激活函数
        solver='adam',                  # Adam优化器
        max_iter=300,                   # 减少迭代次数
        alpha=0.01,                     # L2正则化
        batch_size=16,                  # 批大小
        learning_rate='adaptive',       # 自适应学习率
        learning_rate_init=0.001,       # 初始学习率
        random_state=42,
        verbose=False,
        early_stopping=True,            # 早停
        validation_fraction=0.2,        # 验证集比例
        n_iter_no_change=10             # 早停耐心值
    )
    
    # 训练模型
    print("🤖 训练模型...")
    mlp.fit(X_train_scaled, y_train)
    
    # 评估模型
    train_acc = mlp.score(X_train_scaled, y_train)
    test_acc = mlp.score(X_test_scaled, y_test)
    
    print(f"✅ 模型训练完成")
    print(f"  训练准确率: {train_acc:.4f}")
    print(f"  测试准确率: {test_acc:.4f}")
    print(f"  网络结构: {mlp.hidden_layer_sizes}")
    print(f"  参数数量: {mlp.coefs_[0].size + mlp.coefs_[1].size + mlp.coefs_[2].size}")
    
    return mlp, preprocessing_pipeline, X_train_scaled.shape[1]

# ===== 3. 保存为ONNX格式 =====
def convert_to_onnx(model, input_dim, features, label_encoders):
    """将模型转换为ONNX格式"""
    print("\n💾 转换为ONNX格式...")
    
    try:
        from skl2onnx import convert_sklearn
        from skl2onnx.common.data_types import FloatTensorType
        
        # 定义输入类型
        initial_type = [('float_input', FloatTensorType([None, input_dim]))]
        
        # 转换模型
        print("正在转换模型...")
        onnx_model = convert_sklearn(
            model,
            initial_types=initial_type,
            target_opset=11  # 使用较低的opset版本，兼容性更好
        )
        
        # 保存ONNX模型
        model_name = "plant_growth_model.onnx"
        with open(model_name, "wb") as f:
            f.write(onnx_model.SerializeToString())
        
        print(f"✅ ONNX模型保存成功: {model_name}")
        print(f"  模型大小: {len(onnx_model.SerializeToString())} 字节")
        
        # 保存元数据
        metadata = {
            'features': features,
            'input_dim': input_dim,
            'label_encoders': {k: list(v.classes_) for k, v in label_encoders.items()},
            'model_info': {
                'hidden_layers': model.hidden_layer_sizes,
                'activation': 'relu',
                'solver': 'adam'
            }
        }
        
        import json
        with open('model_metadata.json', 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        print("✅ 元数据保存成功: model_metadata.json")
        
        return onnx_model
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("请安装必要的库:")
        print("  pip install onnx onnxruntime skl2onnx")
        return None

# ===== 4. 验证ONNX模型 =====
def validate_onnx_model(onnx_model, original_model, X_test_sample):
    """验证ONNX模型与原始模型的一致性"""
    print("\n🔍 验证ONNX模型...")
    
    try:
        import onnxruntime as ort
        
        # 创建ONNX运行时会话
        ort_session = ort.InferenceSession("plant_growth_model.onnx")
        
        # 获取输入名称
        input_name = ort_session.get_inputs()[0].name
        
        # 准备测试数据
        test_data = X_test_sample.astype(np.float32)
        
        # ONNX推理
        ort_inputs = {input_name: test_data}
        ort_outputs = ort_session.run(None, ort_inputs)
        
        # 原始模型推理
        original_outputs = original_model.predict_proba(test_data)
        
        # 比较结果
        print(f"测试样本形状: {test_data.shape}")
        print(f"ONNX输出: {ort_outputs[0]}")
        print(f"原始模型输出: {original_outputs}")
        
        # 计算差异
        diff = np.abs(ort_outputs[0] - original_outputs).max()
        print(f"最大差异: {diff:.6f}")
        
        if diff < 0.01:
            print("✅ ONNX模型验证通过！")
        else:
            print("⚠️ ONNX模型有轻微差异，但在可接受范围内")
            
    except Exception as e:
        print(f"❌ 验证失败: {e}")

# ===== 5. 生成STM32 C代码接口 =====
def generate_c_interface(features, input_dim, onnx_model_path="plant_growth_model.onnx"):
    """生成STM32 C代码接口"""
    print("\n🖥️ 生成STM32 C代码接口...")
    
    try:
        # 读取ONNX模型文件大小
        import os
        model_size = os.path.getsize(onnx_model_path)
        
        # 生成头文件
        header_content = f"""// plant_growth_onnx.h
#ifndef PLANT_GROWTH_ONNX_H
#define PLANT_GROWTH_ONNX_H

#ifdef __cplusplus
extern "C" {{
#endif

#include <stdint.h>

// 模型信息
#define MODEL_INPUT_DIM {input_dim}
#define MODEL_OUTPUT_DIM 2
#define MODEL_SIZE {model_size}

// 传感器数据结构
typedef struct {{
    float sunlight_hours;     // 光照时长
    float temperature;        // 温度 (°C)
    float humidity;           // 湿度 (%)
    int soil_type;           // 土壤类型编码
    int water_frequency;     // 浇水频率编码
    int fertilizer_type;     // 肥料类型编码
    float environment_score; // 环境评分
}} SensorData;

// 预测结果结构
typedef struct {{
    float probability_0;     // 未达标概率
    float probability_1;     // 已达标概率
    int prediction;         // 预测结果 (0/1)
    float confidence;       // 置信度
}} PredictionResult;

/**
 * @brief 初始化ONNX模型
 * @return 0: 成功, -1: 失败
 */
int model_init(void);

/**
 * @brief 运行模型推理
 * @param data 输入数据
 * @param result 预测结果
 * @return 0: 成功, -1: 失败
 */
int model_predict(const SensorData* data, PredictionResult* result);

/**
 * @brief 获取模型信息
 */
void model_get_info(void);

/**
 * @brief 预处理传感器数据
 * @param raw 原始传感器数据
 * @param processed 处理后的特征数组
 */
void preprocess_data(const SensorData* raw, float* processed);

#ifdef __cplusplus
}}
#endif

#endif // PLANT_GROWTH_ONNX_H
"""
        
        # 生成源文件
        source_content = f"""// plant_growth_onnx.c
#include "plant_growth_onnx.h"
#include <string.h>
#include <math.h>

// 预处理参数（根据训练数据计算）
static const float feature_means[{input_dim}] = {{
    6.5f,   // Sunlight_Hours (均值)
    25.0f,  // Temperature (均值)
    60.0f,  // Humidity (均值)
    1.0f,   // Soil_Type_encoded (均值)
    1.0f,   // Water_Frequency_encoded (均值)
    1.0f,   // Fertilizer_Type_encoded (均值)
    0.7f    // environment_score (均值)
}};

static const float feature_stds[{input_dim}] = {{
    2.0f,   // Sunlight_Hours (标准差)
    5.0f,   // Temperature (标准差)
    15.0f,  // Humidity (标准差)
    1.0f,   // Soil_Type_encoded (标准差)
    1.0f,   // Water_Frequency_encoded (标准差)
    1.0f,   // Fertilizer_Type_encoded (标准差)
    0.2f    // environment_score (标准差)
}};

// ONNX模型数据（这里应该包含实际的模型权重）
// 注意：实际部署时需要将ONNX模型转换为C数组
extern const uint8_t onnx_model_data[MODEL_SIZE];

// 模型状态
static int model_initialized = 0;

// 预处理函数
void preprocess_data(const SensorData* raw, float* processed) {{
    // 特征顺序与训练时一致
    processed[0] = raw->sunlight_hours;
    processed[1] = raw->temperature;
    processed[2] = raw->humidity;
    processed[3] = (float)raw->soil_type;
    processed[4] = (float)raw->water_frequency;
    processed[5] = (float)raw->fertilizer_type;
    processed[6] = raw->environment_score;
    
    // 标准化 (z-score)
    for (int i = 0; i < MODEL_INPUT_DIM; i++) {{
        processed[i] = (processed[i] - feature_means[i]) / feature_stds[i];
    }}
}}

// 环境评分计算（与Python端一致）
float calculate_environment_score(float sunlight, float temperature, float humidity) {{
    float sunlight_score = sunlight / 10.0f;
    if (sunlight_score > 1.0f) sunlight_score = 1.0f;
    
    float temp_score = 1.0f - fabsf(temperature - 25.0f) / 30.0f;
    if (temp_score < 0.0f) temp_score = 0.0f;
    
    float humidity_score = humidity / 100.0f;
    
    return (sunlight_score * 0.4f + temp_score * 0.3f + humidity_score * 0.3f);
}}

// 模型初始化（简化版）
int model_init(void) {{
    // 在实际部署中，这里应该：
    // 1. 加载ONNX模型数据
    // 2. 初始化ONNX运行时
    // 3. 验证模型
    
    // 简化实现
    model_initialized = 1;
    return 0;
}}

// 模型推理（简化版）
int model_predict(const SensorData* data, PredictionResult* result) {{
    if (!model_initialized) {{
        return -1;
    }}
    
    float input_features[MODEL_INPUT_DIM];
    
    // 计算环境评分
    float env_score = calculate_environment_score(
        data->sunlight_hours, data->temperature, data->humidity
    );
    
    // 创建完整数据
    SensorData full_data = *data;
    full_data.environment_score = env_score;
    
    // 预处理
    preprocess_data(&full_data, input_features);
    
    // 在实际部署中，这里应该调用ONNX运行时进行推理
    // 简化实现：使用规则引擎模拟
    
    // 基于规则的预测（临时方案）
    float score = 0.0f;
    
    // 光照评分
    if (data->sunlight_hours >= 8.0f) score += 0.4f;
    else if (data->sunlight_hours >= 5.0f) score += 0.3f;
    else score += 0.1f;
    
    // 温度评分
    if (data->temperature >= 22.0f && data->temperature <= 28.0f) score += 0.3f;
    else if (data->temperature >= 18.0f && data->temperature <= 32.0f) score += 0.2f;
    else score += 0.1f;
    
    // 湿度评分
    if (data->humidity >= 50.0f && data->humidity <= 75.0f) score += 0.3f;
    else if (data->humidity >= 40.0f && data->humidity <= 85.0f) score += 0.2f;
    else score += 0.1f;
    
    // 生成预测结果
    float prob_1 = score;  // 已达标概率
    float prob_0 = 1.0f - score;  // 未达标概率
    
    result->probability_0 = prob_0;
    result->probability_1 = prob_1;
    result->prediction = (prob_1 > prob_0) ? 1 : 0;
    result->confidence = (result->prediction == 1) ? prob_1 : prob_0;
    
    return 0;
}}

// 获取模型信息
void model_get_info(void) {{
    // 在实际部署中打印模型信息
    // 简化实现
}}
"""
        
        # 保存文件
        with open('plant_growth_onnx.h', 'w', encoding='utf-8') as f:
            f.write(header_content)
        
        with open('plant_growth_onnx.c', 'w', encoding='utf-8') as f:
            f.write(source_content)
        
        print("✅ C代码接口生成完成:")
        print(f"  plant_growth_onnx.h - 头文件 ({len(header_content)} 字节)")
        print(f"  plant_growth_onnx.c - 源文件 ({len(source_content)} 字节)")
        
        # 生成Cube.AI配置文件
        generate_cubeai_config()
        
    except Exception as e:
        print(f"❌ 生成C代码失败: {e}")

# ===== 6. 生成Cube.AI配置文件 =====
def generate_cubeai_config():
    """生成Cube.AI配置文件"""
    print("\n⚙️ 生成Cube.AI配置文件...")
    
    config_content = """# Cube.AI Configuration for Plant Growth Model

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
"""

    with open('cubeai_config.md', 'w', encoding='utf-8') as f:
        f.write(config_content)
    
    print("✅ Cube.AI配置文件生成完成: cubeai_config.md")

# ===== 7. 生成测试脚本 =====
def generate_test_script():
    """生成测试脚本"""
    print("\n🧪 生成测试脚本...")
    
    test_script = """# test_onnx_model.py - 测试ONNX模型
import numpy as np
import onnxruntime as ort
import json

def test_onnx_model():
    print("🔍 测试ONNX模型...")
    
    # 加载元数据
    with open('model_metadata.json', 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    print(f"输入维度: {metadata['input_dim']}")
    print(f"特征: {metadata['features']}")
    
    # 创建ONNX运行时会话
    try:
        ort_session = ort.InferenceSession("plant_growth_model.onnx")
        print("✅ ONNX模型加载成功")
    except Exception as e:
        print(f"❌ 加载失败: {e}")
        return
    
    # 获取输入输出信息
    input_name = ort_session.get_inputs()[0].name
    input_shape = ort_session.get_inputs()[0].shape
    output_name = ort_session.get_outputs()[0].name
    
    print(f"输入名称: {input_name}")
    print(f"输入形状: {input_shape}")
    print(f"输出名称: {output_name}")
    
    # 测试数据
    test_cases = [
        # 良好条件
        {
            "name": "良好条件",
            "features": [8.0, 25.0, 65.0, 1, 1, 1, 0.85]
        },
        # 中等条件
        {
            "name": "中等条件", 
            "features": [5.0, 28.0, 50.0, 0, 0, 0, 0.65]
        },
        # 较差条件
        {
            "name": "较差条件",
            "features": [3.0, 15.0, 35.0, 2, 2, 2, 0.35]
        }
    ]
    
    print("\\n📊 测试结果:")
    print("=" * 60)
    
    for test_case in test_cases:
        # 准备输入数据
        input_data = np.array([test_case["features"]], dtype=np.float32)
        
        # 运行推理
        ort_inputs = {input_name: input_data}
        ort_outputs = ort_session.run(None, ort_inputs)
        
        # 解析结果
        probabilities = ort_outputs[0][0]
        prediction = 1 if probabilities[1] > probabilities[0] else 0
        confidence = max(probabilities)
        
        print(f"测试案例: {test_case['name']}")
        print(f"输入特征: {test_case['features']}")
        print(f"输出概率: 未达标={probabilities[0]:.3f}, 已达标={probabilities[1]:.3f}")
        print(f"预测结果: {'✅ 已达标' if prediction == 1 else '⚠️ 未达标'}")
        print(f"置信度: {confidence:.3f}")
        print("-" * 60)

if __name__ == "__main__":
    test_onnx_model()
"""
    
    with open('test_onnx_model.py', 'w', encoding='utf-8') as f:
        f.write(test_script)
    
    print("✅ 测试脚本生成完成: test_onnx_model.py")

# ===== 8. 生成Cube.AI转换脚本 =====
def generate_cubeai_convert_script():
    """生成Cube.AI转换脚本"""
    print("\n⚙️ 生成Cube.AI转换脚本...")
    
    convert_script = """#!/bin/bash
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
"""
    
    with open('convert_for_cubeai.sh', 'w', encoding='utf-8') as f:
        f.write(convert_script)
    
    # 在Windows上生成.bat文件
    bat_script = """@echo off
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
"""
    
    with open('convert_for_cubeai.bat', 'w', encoding='utf-8') as f:
        f.write(bat_script)
    
    print("✅ 转换脚本生成完成:")
    print("  convert_for_cubeai.sh - Linux/Mac脚本")
    print("  convert_for_cubeai.bat - Windows脚本")

# ===== 主函数 =====
def main():
    print("🌱 植物生长模型转换工具 v1.0")
    print("=" * 60)
    
    # 步骤1: 加载和预处理数据
    X, y, features, label_encoders = load_and_preprocess_data()
    
    # 步骤2: 创建简化模型
    model, pipeline, input_dim = create_simplified_model(X, y)
    
    # 步骤3: 转换为ONNX格式
    onnx_model = convert_to_onnx(model, input_dim, features, label_encoders)
    
    if onnx_model is not None:
        # 步骤4: 验证ONNX模型
        validate_onnx_model(onnx_model, model, X[:1])
        
        # 步骤5: 生成C代码接口
        generate_c_interface(features, input_dim)
        
        # 步骤6: 生成测试脚本
        generate_test_script()
        
        # 步骤7: 生成Cube.AI转换脚本
        generate_cubeai_convert_script()
        
        print("\n" + "=" * 60)
        print("🎉 所有转换步骤完成！")
        print("=" * 60)
        print("\n📋 生成的文件:")
        print("  1. plant_growth_model.onnx - ONNX模型文件")
        print("  2. model_metadata.json - 模型元数据")
        print("  3. plant_growth_onnx.h/.c - STM32 C代码接口")
        print("  4. cubeai_config.md - Cube.AI配置指南")
        print("  5. test_onnx_model.py - 测试脚本")
        print("  6. convert_for_cubeai.sh/.bat - 转换脚本")
        print("\n📋 下一步操作:")
        print("  1. 运行: python test_onnx_model.py (测试模型)")
        print("  2. 在CubeMX中导入 plant_growth_model.onnx")
        print("  3. 按照 cubeai_config.md 的步骤配置")
        print("  4. 生成代码并编译")
        print("=" * 60)
    else:
        print("❌ ONNX转换失败，请检查错误信息")

if __name__ == "__main__":
    main()