/*
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
    
    printf("\n🌱 植物生长预测结果:\n");
    printf("========================================\n");
    printf("传感器数据:\n");
    printf("  光照时长: %.1f 小时\n", input->sunlight_hours);
    printf("  温度: %.1f °C\n", input->temperature);
    printf("  湿度: %.1f %%\n", input->humidity);
    printf("  土壤类型: %s\n", soil_names[input->soil_type]);
    printf("  浇水频率: %s\n", water_names[input->water_frequency]);
    printf("  施肥类型: %s\n", fert_names[input->fertilizer_type]);
    
    printf("\n预测结果:\n");
    printf("  生长状态: %s\n", 
           result->prediction == 1 ? "✅ 已达标" : "⚠️ 未达标");
    printf("  置信度: %.1f%%\n", result->confidence * 100.0f);
    printf("  健康评分: %.1f/100\n", result->health_score);
    printf("  概率分布: 未达标=%.1f%%, 已达标=%.1f%%\n",
           result->prob_not_achieved * 100, result->prob_achieved * 100);
    
    printf("\n建议:\n");
    if (result->prediction == 0) {
        if (input->sunlight_hours < 5.0f) {
            printf("  - 增加光照时间到5小时以上\n");
        }
        if (input->temperature < 18.0f || input->temperature > 30.0f) {
            printf("  - 调整温度到20-28°C之间\n");
        }
        if (input->humidity < 50.0f) {
            printf("  - 提高湿度到50%%以上\n");
        }
    } else {
        printf("  - 保持当前良好的生长条件\n");
        printf("  - 继续定期监测\n");
    }
    printf("========================================\n");
}

int main(void) {
    PlantInputData test_cases[3];
    PlantOutputData results[3];
    
    printf("🎯 植物生长模型测试程序\n");
    printf("========================\n\n");
    
    // 初始化模型
    if (plant_model_init() != 0) {
        printf("❌ 模型初始化失败!\n");
        return -1;
    }
    
    printf("✅ 模型初始化成功\n");
    printf("%s\n\n", plant_model_get_info());
    
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
        printf("\n测试案例 %d: %s\n", i + 1, case_names[i]);
        printf("------------------------\n");
        
        if (plant_model_predict(&test_cases[i], &results[i]) == 0) {
            print_result(&test_cases[i], &results[i]);
        } else {
            printf("❌ 预测失败!\n");
        }
    }
    
    printf("\n🎉 所有测试完成!\n");
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
    printf("🌱 植物生长监测系统启动\r\n");
    
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
                "Pred: %d, Conf: %.2f, Health: %.1f\r\n",
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
