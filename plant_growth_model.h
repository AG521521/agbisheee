// plant_growth_model.h
#ifndef PLANT_GROWTH_MODEL_H
#define PLANT_GROWTH_MODEL_H

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    float sunlight_hours;    // 光照时长
    float temperature;       // 温度(°C)
    float humidity;          // 湿度(%)
    int soil_type;          // 土壤类型 (0:sandy, 1:loam, 2:clay)
    int water_frequency;    // 浇水频率 (0:weekly, 1:bi-weekly, 2:daily)
    int fertilizer_type;    // 肥料类型 (0:none, 1:organic, 2:chemical)
} SensorData;

/**
 * @brief 基于规则的植物生长预测
 * @param data 传感器数据
 * @return 预测结果 (0:未达标, 1:已达标)
 */
int predict_growth(const SensorData* data);

/**
 * @brief 计算环境评分 (0-100)
 * @param data 传感器数据
 * @return 环境评分
 */
float calculate_environment_score(const SensorData* data);

/**
 * @brief 获取生长建议
 * @param prediction 预测结果
 * @param env_score 环境评分
 * @return 建议字符串
 */
const char* get_growth_suggestion(int prediction, float env_score);

#ifdef __cplusplus
}
#endif

#endif // PLANT_GROWTH_MODEL_H

