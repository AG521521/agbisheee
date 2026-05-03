// plant_growth_onnx.c
#include "plant_growth_onnx.h"
#include <string.h>
#include <math.h>

// 预处理参数（根据训练数据计算）
static const float feature_means[7] = {
    6.5f,   // Sunlight_Hours (均值)
    25.0f,  // Temperature (均值)
    60.0f,  // Humidity (均值)
    1.0f,   // Soil_Type_encoded (均值)
    1.0f,   // Water_Frequency_encoded (均值)
    1.0f,   // Fertilizer_Type_encoded (均值)
    0.7f    // environment_score (均值)
};

static const float feature_stds[7] = {
    2.0f,   // Sunlight_Hours (标准差)
    5.0f,   // Temperature (标准差)
    15.0f,  // Humidity (标准差)
    1.0f,   // Soil_Type_encoded (标准差)
    1.0f,   // Water_Frequency_encoded (标准差)
    1.0f,   // Fertilizer_Type_encoded (标准差)
    0.2f    // environment_score (标准差)
};

// ONNX模型数据（这里应该包含实际的模型权重）
// 注意：实际部署时需要将ONNX模型转换为C数组
extern const uint8_t onnx_model_data[MODEL_SIZE];

// 模型状态
static int model_initialized = 0;

// 预处理函数
void preprocess_data(const SensorData* raw, float* processed) {
    // 特征顺序与训练时一致
    processed[0] = raw->sunlight_hours;
    processed[1] = raw->temperature;
    processed[2] = raw->humidity;
    processed[3] = (float)raw->soil_type;
    processed[4] = (float)raw->water_frequency;
    processed[5] = (float)raw->fertilizer_type;
    processed[6] = raw->environment_score;
    
    // 标准化 (z-score)
    for (int i = 0; i < MODEL_INPUT_DIM; i++) {
        processed[i] = (processed[i] - feature_means[i]) / feature_stds[i];
    }
}

// 环境评分计算（与Python端一致）
float calculate_environment_score(float sunlight, float temperature, float humidity) {
    float sunlight_score = sunlight / 10.0f;
    if (sunlight_score > 1.0f) sunlight_score = 1.0f;
    
    float temp_score = 1.0f - fabsf(temperature - 25.0f) / 30.0f;
    if (temp_score < 0.0f) temp_score = 0.0f;
    
    float humidity_score = humidity / 100.0f;
    
    return (sunlight_score * 0.4f + temp_score * 0.3f + humidity_score * 0.3f);
}

// 模型初始化（简化版）
int model_init(void) {
    // 在实际部署中，这里应该：
    // 1. 加载ONNX模型数据
    // 2. 初始化ONNX运行时
    // 3. 验证模型
    
    // 简化实现
    model_initialized = 1;
    return 0;
}

// 模型推理（简化版）
int model_predict(const SensorData* data, PredictionResult* result) {
    if (!model_initialized) {
        return -1;
    }
    
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
}

// 获取模型信息
void model_get_info(void) {
    // 在实际部署中打印模型信息
    // 简化实现
}
