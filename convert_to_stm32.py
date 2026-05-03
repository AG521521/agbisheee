# convert_to_stm32.py - 将scikit-learn模型转换为STM32可用的C代码
import joblib
import numpy as np
import json
import os

def load_model():
    """加载训练好的模型"""
    print("📂 加载模型文件...")
    try:
        model_data = joblib.load('plant_growth_model_v2.pkl')
        print("✅ 模型加载成功!")
        return model_data
    except FileNotFoundError:
        print("❌ 错误: 找不到模型文件 plant_growth_model_v2.pkl")
        print("请先运行训练脚本: python train_model_fixed.py")
        return None

def extract_model_info(model_data):
    """提取模型信息"""
    mlp = model_data['model']
    
    # 获取网络结构
    input_size = len(model_data['features'])
    output_size = len(mlp.classes_)
    
    # 获取隐藏层大小
    hidden_sizes = mlp.hidden_layer_sizes
    if isinstance(hidden_sizes, int):
        hidden_sizes = (hidden_sizes,)
    
    # 提取各层权重和偏置
    layers = []
    for i in range(len(mlp.coefs_)):
        layer = {
            'weights': mlp.coefs_[i].tolist(),
            'biases': mlp.intercepts_[i].tolist(),
            'input_size': mlp.coefs_[i].shape[0],
            'output_size': mlp.coefs_[i].shape[1]
        }
        layers.append(layer)
    
    model_info = {
        'input_size': input_size,
        'output_size': output_size,
        'hidden_sizes': hidden_sizes,
        'layers': layers,
        'total_params': sum([len(l['weights']) + len(l['biases']) for l in layers]),
        'features': model_data['features'],
        'accuracy': model_data.get('training_stats', {}).get('accuracy', 0)
    }
    
    return model_info

def create_c_header(model_info):
    """创建C头文件内容"""
    input_size = model_info['input_size']
    output_size = model_info['output_size']
    hidden1_size = model_info['hidden_sizes'][0] if model_info['hidden_sizes'] else 0
    hidden2_size = model_info['hidden_sizes'][1] if len(model_info['hidden_sizes']) > 1 else 0
    
    header = f"""#ifndef PLANT_GROWTH_MODEL_H
#define PLANT_GROWTH_MODEL_H

/* ===========================================================
 * 植物生长预测神经网络模型
 * 自动生成 - 请勿手动修改
 * 输入特征: {input_size}
 * 输出类别: {output_size}
 * 网络结构: {input_size}-{hidden1_size}{'-' + str(hidden2_size) if hidden2_size > 0 else ''}-{output_size}
 * =========================================================== */

#include <math.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {{
#endif

// 模型配置
#define MODEL_INPUT_SIZE      {input_size}
#define MODEL_OUTPUT_SIZE     {output_size}
#define MODEL_HIDDEN1_SIZE    {hidden1_size}
#define MODEL_HIDDEN2_SIZE    {hidden2_size}

// 输入数据结构
typedef struct {{
    float sunlight_hours;     // 光照时长 (小时)
    float temperature;        // 温度 (°C)
    float humidity;           // 湿度 (%%)
    uint8_t soil_type;        // 0:沙土, 1:壤土, 2:黏土
    uint8_t water_frequency;  // 0:每周, 1:每两周, 2:每天
    uint8_t fertilizer_type;  // 0:无, 1:有机, 2:化学
}} PlantInputData;

// 输出数据结构
typedef struct {{
    uint8_t prediction;       // 0:未达标, 1:已达标
    float confidence;         // 置信度 (0.0-1.0)
    float prob_not_achieved;  // 未达标概率
    float prob_achieved;      // 已达标概率
    float health_score;       // 健康评分 (0-100)
}} PlantOutputData;

// ===================== 公共API函数 =====================

/**
 * @brief 初始化模型
 * @return 0:成功, -1:失败
 */
int plant_model_init(void);

/**
 * @brief 执行生长预测
 * @param input 输入数据
 * @param output 预测结果
 * @return 0:成功, -1:失败
 */
int plant_model_predict(const PlantInputData* input, PlantOutputData* output);

/**
 * @brief 计算环境评分
 * @param sunlight 光照时长
 * @param temperature 温度
 * @param humidity 湿度
 * @return 环境评分 (0.0-1.0)
 */
float calculate_environment_score(float sunlight, float temperature, float humidity);

/**
 * @brief 获取模型信息
 * @return 模型信息字符串
 */
const char* plant_model_get_info(void);

#ifdef __cplusplus
}}
#endif

#endif /* PLANT_GROWTH_MODEL_H */
"""
    
    return header

def create_c_source(model_info):
    """创建C源文件内容"""
    layers = model_info['layers']
    
    # 生成权重和偏置数组
    weights_defs = []
    biases_defs = []
    
    for i, layer in enumerate(layers):
        # 生成权重数组
        weights = np.array(layer['weights']).flatten()
        weights_str = ',\n    '.join([', '.join([f'{w:.6f}f' for w in weights[j:j+8]]) 
                                      for j in range(0, len(weights), 8)])
        weights_defs.append(f"""// 层{i+1}权重矩阵: {layer['input_size']}x{layer['output_size']}
static const float WEIGHTS_{i}[] = {{
    {weights_str}
}};
""")
        
        # 生成偏置数组
        biases = np.array(layer['biases'])
        biases_str = ', '.join([f'{b:.6f}f' for b in biases])
        biases_defs.append(f"""// 层{i+1}偏置向量: {layer['output_size']}
static const float BIASES_{i}[] = {{
    {biases_str}
}};
""")
    
    # 网络参数
    input_size = model_info['input_size']
    hidden1_size = model_info['hidden_sizes'][0] if model_info['hidden_sizes'] else 0
    hidden2_size = model_info['hidden_sizes'][1] if len(model_info['hidden_sizes']) > 1 else 0
    output_size = model_info['output_size']
    
    # 生成前向传播代码
    forward_code = ""
    if hidden2_size > 0:
        forward_code = f"""
    // 第1层: 输入 -> 隐藏层1
    for (int j = 0; j < MODEL_HIDDEN1_SIZE; j++) {{
        hidden1[j] = BIASES_0[j];
        for (int i = 0; i < MODEL_INPUT_SIZE; i++) {{
            hidden1[j] += features[i] * WEIGHTS_0[i * MODEL_HIDDEN1_SIZE + j];
        }}
        hidden1[j] = relu(hidden1[j]);
    }}
    
    // 第2层: 隐藏层1 -> 隐藏层2
    for (int j = 0; j < MODEL_HIDDEN2_SIZE; j++) {{
        hidden2[j] = BIASES_1[j];
        for (int i = 0; i < MODEL_HIDDEN1_SIZE; i++) {{
            hidden2[j] += hidden1[i] * WEIGHTS_1[i * MODEL_HIDDEN2_SIZE + j];
        }}
        hidden2[j] = relu(hidden2[j]);
    }}
    
    // 输出层: 隐藏层2 -> 输出
    for (int j = 0; j < MODEL_OUTPUT_SIZE; j++) {{
        output[j] = BIASES_2[j];
        for (int i = 0; i < MODEL_HIDDEN2_SIZE; i++) {{
            output[j] += hidden2[i] * WEIGHTS_2[i * MODEL_OUTPUT_SIZE + j];
        }}
    }}
"""
    else:
        forward_code = f"""
    // 第1层: 输入 -> 隐藏层1
    for (int j = 0; j < MODEL_HIDDEN1_SIZE; j++) {{
        hidden1[j] = BIASES_0[j];
        for (int i = 0; i < MODEL_INPUT_SIZE; i++) {{
            hidden1[j] += features[i] * WEIGHTS_0[i * MODEL_HIDDEN1_SIZE + j];
        }}
        hidden1[j] = relu(hidden1[j]);
    }}
    
    // 输出层: 隐藏层1 -> 输出
    for (int j = 0; j < MODEL_OUTPUT_SIZE; j++) {{
        output[j] = BIASES_1[j];
        for (int i = 0; i < MODEL_HIDDEN1_SIZE; i++) {{
            output[j] += hidden1[i] * WEIGHTS_1[i * MODEL_OUTPUT_SIZE + j];
        }}
    }}
"""
    
    source = f"""#include "plant_growth_model.h"
#include <string.h>

/* ===========================================================
 * 模型参数定义
 * =========================================================== */

{''.join(weights_defs)}

{''.join(biases_defs)}

/* ===========================================================
 * 内部变量和函数
 * =========================================================== */

static int model_initialized = 0;
static const char* MODEL_INFO = 
"植物生长预测神经网络\\n"
"输入特征: {input_size}\\n"
"输出类别: {output_size}\\n"
"网络结构: {input_size}-{hidden1_size}{'-' + str(hidden2_size) if hidden2_size > 0 else ''}-{output_size}\\n"
"训练准确率: {model_info['accuracy']:.2%}";

/* ReLU激活函数 */
static inline float relu(float x) {{
    return x > 0.0f ? x : 0.0f;
}}

/* Softmax函数 */
static void softmax(float* x, int size) {{
    float max_val = x[0];
    float sum = 0.0f;
    
    // 找到最大值（提高数值稳定性）
    for (int i = 1; i < size; i++) {{
        if (x[i] > max_val) max_val = x[i];
    }}
    
    // 计算指数和
    for (int i = 0; i < size; i++) {{
        x[i] = expf(x[i] - max_val);
        sum += x[i];
    }}
    
    // 归一化
    if (sum > 0.0f) {{
        for (int i = 0; i < size; i++) {{
            x[i] /= sum;
        }}
    }}
}}

/* 准备输入特征 */
static void prepare_features(const PlantInputData* input, float* features) {{
    // 基本特征
    features[0] = input->sunlight_hours;
    features[1] = input->temperature;
    features[2] = input->humidity;
    features[3] = (float)input->soil_type;
    features[4] = (float)input->water_frequency;
    features[5] = (float)input->fertilizer_type;
    
    // 环境评分
    features[6] = calculate_environment_score(
        input->sunlight_hours,
        input->temperature,
        input->humidity
    );
}}

/* 标准化特征 */
static void normalize_features(float* features) {{
    // 简化的标准化（根据训练数据调整这些值）
    float means[] = {{6.0f, 25.0f, 65.0f, 1.0f, 1.0f, 1.0f, 0.7f}};
    float scales[] = {{2.0f, 5.0f, 15.0f, 0.5f, 0.5f, 0.5f, 0.2f}};
    
    for (int i = 0; i < MODEL_INPUT_SIZE; i++) {{
        features[i] = (features[i] - means[i]) / scales[i];
    }}
}}

/* 神经网络前向传播 */
static void neural_network(const float* features, float* output) {{
    float hidden1[MODEL_HIDDEN1_SIZE];
"""
    
    if hidden2_size > 0:
        source += """    float hidden2[MODEL_HIDDEN2_SIZE];
"""
    
    source += forward_code + """
    // 应用Softmax
    softmax(output, MODEL_OUTPUT_SIZE);
}

/* ===========================================================
 * 公共API实现
 * =========================================================== */

float calculate_environment_score(float sunlight, float temperature, float humidity) {{
    float light_score = sunlight / 10.0f;
    if (light_score > 1.0f) light_score = 1.0f;
    
    float temp_score = 1.0f - fabsf(temperature - 25.0f) / 30.0f;
    if (temp_score < 0.0f) temp_score = 0.0f;
    
    float humidity_score = humidity / 100.0f;
    
    // 加权平均
    return (light_score * 0.4f + 
            temp_score * 0.3f + 
            humidity_score * 0.3f);
}}

int plant_model_init(void) {{
    if (model_initialized) {{
        return 0;
    }}
    
    // 这里可以添加初始化代码
    model_initialized = 1;
    return 0;
}}

int plant_model_predict(const PlantInputData* input, PlantOutputData* output) {{
    float features[MODEL_INPUT_SIZE];
    float nn_output[MODEL_OUTPUT_SIZE];
    
    // 检查初始化
    if (!model_initialized) {{
        if (plant_model_init() != 0) {{
            return -1;
        }}
    }}
    
    // 1. 准备特征
    prepare_features(input, features);
    
    // 2. 标准化
    normalize_features(features);
    
    // 3. 神经网络推理
    neural_network(features, nn_output);
    
    // 4. 解析结果
    output->prob_not_achieved = nn_output[0];
    output->prob_achieved = nn_output[1];
    
    if (nn_output[1] > nn_output[0]) {{
        output->prediction = 1;      // 已达标
        output->confidence = nn_output[1];
    }} else {{
        output->prediction = 0;      // 未达标
        output->confidence = nn_output[0];
    }}
    
    // 5. 计算健康评分
    float env_score = calculate_environment_score(
        input->sunlight_hours,
        input->temperature,
        input->humidity
    );
    output->health_score = (env_score * 70.0f + output->confidence * 30.0f);
    
    return 0;
}}

const char* plant_model_get_info(void) {{
    return MODEL_INFO;
}}
"""
    
    return source

def create_example_file():
    """创建使用示例文件"""
    example = """/*
 * plant_growth_example.c
 * 植物生长模型使用示例
 * 适用于STM32G071RB
 */

#include <stdio.h>
#include "plant_growth_model.h"

void print_result(const PlantInputData* input, const PlantOutputData* result) {
    const char* soil_names[] = {"沙土", "壤土", "黏土"};
    const char* water_names[] = {"每周", "每两周", "每天"};
    const char* fert_names[] = {"无", "有机", "化学"};
    
    printf("\\n🌱 植物生长预测结果:\\n");
    printf("========================================\\n");
    printf("传感器数据:\\n");
    printf("  光照时长: %.1f 小时\\n", input->sunlight_hours);
    printf("  温度: %.1f °C\\n", input->temperature);
    printf("  湿度: %.1f %%\\n", input->humidity);
    printf("  土壤类型: %s\\n", soil_names[input->soil_type]);
    printf("  浇水频率: %s\\n", water_names[input->water_frequency]);
    printf("  施肥类型: %s\\n", fert_names[input->fertilizer_type]);
    
    printf("\\n预测结果:\\n");
    printf("  生长状态: %s\\n", 
           result->prediction == 1 ? "✅ 已达标" : "⚠️ 未达标");
    printf("  置信度: %.1f%%\\n", result->confidence * 100.0f);
    printf("  健康评分: %.1f/100\\n", result->health_score);
    printf("  概率分布: 未达标=%.1f%%, 已达标=%.1f%%\\n",
           result->prob_not_achieved * 100, result->prob_achieved * 100);
    
    printf("\\n建议:\\n");
    if (result->prediction == 0) {
        if (input->sunlight_hours < 5.0f) {
            printf("  - 增加光照时间到5小时以上\\n");
        }
        if (input->temperature < 18.0f || input->temperature > 30.0f) {
            printf("  - 调整温度到20-28°C之间\\n");
        }
        if (input->humidity < 50.0f) {
            printf("  - 提高湿度到50%%以上\\n");
        }
    } else {
        printf("  - 保持当前良好的生长条件\\n");
        printf("  - 继续定期监测\\n");
    }
    printf("========================================\\n");
}

int main(void) {
    PlantInputData test_cases[3];
    PlantOutputData results[3];
    
    printf("🎯 植物生长模型测试程序\\n");
    printf("========================\\n\\n");
    
    // 初始化模型
    if (plant_model_init() != 0) {
        printf("❌ 模型初始化失败!\\n");
        return -1;
    }
    
    printf("✅ 模型初始化成功\\n");
    printf("%s\\n\\n", plant_model_get_info());
    
    // 测试案例1: 良好条件
    test_cases[0].sunlight_hours = 8.0f;
    test_cases[0].temperature = 25.0f;
    test_cases[0].humidity = 65.0f;
    test_cases[0].soil_type = 1;      // 壤土
    test_cases[0].water_frequency = 1; // 每两周
    test_cases[0].fertilizer_type = 1; // 有机
    
    // 测试案例2: 中等条件
    test_cases[1].sunlight_hours = 5.0f;
    test_cases[1].temperature = 28.0f;
    test_cases[1].humidity = 50.0f;
    test_cases[1].soil_type = 0;      // 沙土
    test_cases[1].water_frequency = 0; // 每周
    test_cases[1].fertilizer_type = 0; // 无
    
    // 测试案例3: 较差条件
    test_cases[2].sunlight_hours = 3.0f;
    test_cases[2].temperature = 15.0f;
    test_cases[2].humidity = 35.0f;
    test_cases[2].soil_type = 2;      // 黏土
    test_cases[2].water_frequency = 2; // 每天
    test_cases[2].fertilizer_type = 2; // 化学
    
    const char* case_names[] = {"良好条件", "中等条件", "较差条件"};
    
    for (int i = 0; i < 3; i++) {
        printf("\\n测试案例 %d: %s\\n", i + 1, case_names[i]);
        printf("------------------------\\n");
        
        if (plant_model_predict(&test_cases[i], &results[i]) == 0) {
            print_result(&test_cases[i], &results[i]);
        } else {
            printf("❌ 预测失败!\\n");
        }
    }
    
    printf("\\n🎉 所有测试完成!\\n");
    return 0;
}

#ifdef STM32_PLATFORM
// STM32专用集成代码
#include "main.h"
#include "usart.h"

extern UART_HandleTypeDef huart2;

void stm32_plant_monitor(void) {
    PlantInputData sensor_data;
    PlantOutputData prediction;
    char buffer[128];
    
    // 初始化
    plant_model_init();
    printf("🌱 植物生长监测系统启动\\r\\n");
    
    while (1) {
        // TODO: 从传感器读取数据
        // read_sensors(&sensor_data);
        
        // 示例数据
        sensor_data.sunlight_hours = 8.0f;
        sensor_data.temperature = 25.0f;
        sensor_data.humidity = 65.0f;
        sensor_data.soil_type = 1;
        sensor_data.water_frequency = 1;
        sensor_data.fertilizer_type = 1;
        
        // 执行预测
        if (plant_model_predict(&sensor_data, &prediction) == 0) {
            // 格式化输出
            int len = snprintf(buffer, sizeof(buffer),
                "Pred: %d, Conf: %.2f, Health: %.1f\\r\\n",
                prediction.prediction,
                prediction.confidence,
                prediction.health_score);
            
            // 通过串口发送
            HAL_UART_Transmit(&huart2, (uint8_t*)buffer, len, HAL_MAX_DELAY);
        }
        
        // 等待5秒
        HAL_Delay(5000);
        HAL_GPIO_TogglePin(LED_GPIO_Port, LED_Pin);
    }
}
#endif
"""
    
    return example

def save_files(model_info, output_dir='stm32_output'):
    """保存所有生成的文件"""
    print("\n💾 保存生成的文件...")
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'inc'), exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'src'), exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'examples'), exist_ok=True)
    
    # 生成文件内容
    header_content = create_c_header(model_info)
    source_content = create_c_source(model_info)
    example_content = create_example_file()
    
    # 保存文件
    header_path = os.path.join(output_dir, 'inc', 'plant_growth_model.h')
    source_path = os.path.join(output_dir, 'src', 'plant_growth_model.c')
    example_path = os.path.join(output_dir, 'examples', 'plant_growth_example.c')
    
    with open(header_path, 'w', encoding='utf-8') as f:
        f.write(header_content)
    
    with open(source_path, 'w', encoding='utf-8') as f:
        f.write(source_content)
    
    with open(example_path, 'w', encoding='utf-8') as f:
        f.write(example_content)
    
    # 保存模型信息
    info_path = os.path.join(output_dir, 'model_info.json')
    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump({
            'input_size': model_info['input_size'],
            'output_size': model_info['output_size'],
            'hidden_sizes': model_info['hidden_sizes'],
            'total_params': model_info['total_params'],
            'memory_kb': model_info['total_params'] * 4 / 1024,
            'accuracy': model_info['accuracy']
        }, f, indent=2)
    
    print(f"✅ 头文件已保存: {header_path}")
    print(f"✅ 源文件已保存: {source_path}")
    print(f"✅ 示例文件已保存: {example_path}")
    print(f"✅ 模型信息已保存: {info_path}")
    
    return {
        'header': header_path,
        'source': source_path,
        'example': example_path
    }

def main():
    """主函数"""
    print("="*60)
    print("🌱 植物生长模型转换工具")
    print("将scikit-learn模型转换为STM32 C代码")
    print("="*60)
    
    # 1. 加载模型
    model_data = load_model()
    if model_data is None:
        return
    
    # 2. 提取模型信息
    print("\n🔍 提取模型信息...")
    model_info = extract_model_info(model_data)
    
    print(f"   输入特征数: {model_info['input_size']}")
    print(f"   输出类别数: {model_info['output_size']}")
    print(f"   隐藏层结构: {model_info['hidden_sizes']}")
    print(f"   总参数数量: {model_info['total_params']}")
    print(f"   内存占用: {model_info['total_params'] * 4 / 1024:.1f} KB")
    print(f"   训练准确率: {model_info['accuracy']:.2%}")
    
    # 3. 保存文件
    print("\n📁 生成C代码文件...")
    files = save_files(model_info)
    
    # 4. 显示总结
    print("\n" + "="*60)
    print("🎉 转换完成!")
    print("="*60)
    print("\n📋 生成的文件:")
    print(f"  {files['header']}")
    print(f"  {files['source']}")
    print(f"  {files['example']}")
    
    print("\n🚀 使用步骤:")
    print("  1. 将 inc/plant_growth_model.h 复制到STM32项目的Inc目录")
    print("  2. 将 src/plant_growth_model.c 复制到STM32项目的Src目录")
    print("  3. 参考 examples/plant_growth_example.c 编写主程序")
    print("  4. 编译并烧录到STM32G071RB")
    
    print("\n🔧 模型规格:")
    print(f"  • 输入: {model_info['input_size']}个特征")
    print(f"  • 输出: {model_info['output_size']}个类别")
    print(f"  • 参数: {model_info['total_params']}个")
    print(f"  • 内存: {model_info['total_params'] * 4 / 1024:.1f} KB")
    
    print("\n💡 提示:")
    print("  • 如果内存不足，可以考虑减小网络规模")
    print("  • 可以使用 -O2 优化编译减少代码大小")
    print("  • 确保STM32有足够的堆栈空间")
    
    print("="*60)

if __name__ == "__main__":
    main()