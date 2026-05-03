// plant_growth_onnx.h
#ifndef PLANT_GROWTH_ONNX_H
#define PLANT_GROWTH_ONNX_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

// 模型信息
#define MODEL_INPUT_DIM 7
#define MODEL_OUTPUT_DIM 2
#define MODEL_SIZE 1988

// 传感器数据结构
typedef struct {
    float sunlight_hours;     // 光照时长
    float temperature;        // 温度 (°C)
    float humidity;           // 湿度 (%)
    int soil_type;           // 土壤类型编码
    int water_frequency;     // 浇水频率编码
    int fertilizer_type;     // 肥料类型编码
    float environment_score; // 环境评分
} SensorData;

// 预测结果结构
typedef struct {
    float probability_0;     // 未达标概率
    float probability_1;     // 已达标概率
    int prediction;         // 预测结果 (0/1)
    float confidence;       // 置信度
} PredictionResult;

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
}
#endif

#endif // PLANT_GROWTH_ONNX_H
