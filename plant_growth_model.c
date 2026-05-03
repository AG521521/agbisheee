// plant_growth_model.c
#include "plant_growth_model.h"
#include <math.h>
#include <string.h>

float calculate_environment_score(const SensorData* data) {
    float score = 0.0f;
    
    // 光照评分 (0-40分)
    if (data->sunlight_hours >= 8.0f) {
        score += 40.0f;
    } else if (data->sunlight_hours >= 6.0f) {
        score += 30.0f;
    } else if (data->sunlight_hours >= 4.0f) {
        score += 20.0f;
    } else {
        score += 10.0f;
    }
    
    // 温度评分 (0-30分)
    if (data->temperature >= 22.0f && data->temperature <= 28.0f) {
        score += 30.0f;
    } else if (data->temperature >= 18.0f && data->temperature <= 32.0f) {
        score += 20.0f;
    } else {
        score += 10.0f;
    }
    
    // 湿度评分 (0-30分)
    if (data->humidity >= 55.0f && data->humidity <= 75.0f) {
        score += 30.0f;
    } else if (data->humidity >= 45.0f && data->humidity <= 85.0f) {
        score += 20.0f;
    } else {
        score += 10.0f;
    }
    
    return score;
}

int predict_growth(const SensorData* data) {
    float env_score = calculate_environment_score(data);
    
    // 基础阈值
    int base_prediction = (env_score >= 60.0f) ? 1 : 0;
    
    // 考虑土壤类型
    if (data->soil_type == 1) {  // loam (壤土) 最好
        if (env_score >= 50.0f) base_prediction = 1;
    } else if (data->soil_type == 2) {  // clay (黏土) 较差
        if (env_score < 70.0f) base_prediction = 0;
    }
    
    // 考虑浇水频率
    if (data->water_frequency == 2) {  // daily (每天浇水) 可能过多
        if (env_score < 65.0f) base_prediction = 0;
    }
    
    // 考虑肥料类型
    if (data->fertilizer_type == 1) {  // organic (有机肥) 最好
        if (env_score >= 55.0f) base_prediction = 1;
    } else if (data->fertilizer_type == 0) {  // none (无肥料)
        if (env_score < 65.0f) base_prediction = 0;
    }
    
    return base_prediction;
}

const char* get_growth_suggestion(int prediction, float env_score) {
    if (prediction == 1) {
        if (env_score >= 80.0f) {
            return "生长状态优秀！保持当前条件。";
        } else if (env_score >= 60.0f) {
            return "生长状态良好。可适当增加光照。";
        } else {
            return "勉强达标。建议改善环境条件。";
        }
    } else {
        if (env_score >= 50.0f) {
            return "接近达标。请检查土壤和浇水。";
        } else if (env_score >= 30.0f) {
            return "需要改善。增加光照，调整温湿度。";
        } else {
            return "生长条件差。需要全面改善环境。";
        }
    }
}
