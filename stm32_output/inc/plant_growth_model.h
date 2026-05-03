#ifndef PLANT_GROWTH_MODEL_H
#define PLANT_GROWTH_MODEL_H

/* ===========================================================
 * 植物生长预测神经网络模型
 * 自动生成 - 请勿手动修改
 * 输入特征: 7
 * 输出类别: 2
 * 网络结构: 7-32-16-2
 * =========================================================== */

#include <math.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// 模型配置
#define MODEL_INPUT_SIZE      7
#define MODEL_OUTPUT_SIZE     2
#define MODEL_HIDDEN1_SIZE    32
#define MODEL_HIDDEN2_SIZE    16

// 输入数据结构
typedef struct {
    float sunlight_hours;     // 光照时长 (小时)
    float temperature;        // 温度 (°C)
    float humidity;           // 湿度 (%%)
    uint8_t soil_type;        // 0:沙土, 1:壤土, 2:黏土
    uint8_t water_frequency;  // 0:每周, 1:每两周, 2:每天
    uint8_t fertilizer_type;  // 0:无, 1:有机, 2:化学
} PlantInputData;

// 输出数据结构
typedef struct {
    uint8_t prediction;       // 0:未达标, 1:已达标
    float confidence;         // 置信度 (0.0-1.0)
    float prob_not_achieved;  // 未达标概率
    float prob_achieved;      // 已达标概率
    float health_score;       // 健康评分 (0-100)
} PlantOutputData;

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
}
#endif

#endif /* PLANT_GROWTH_MODEL_H */
