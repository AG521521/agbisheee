/* ESP8266_WebServer_AI_Enhanced_Complete.ino - 完整修复版 */
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ArduinoJson.h>
#include <time.h>
#include <ESP8266mDNS.h>  // 添加这行
/* WiFi配置 - 添加静态IP */
const char* ssid = "iPhone";
const char* password = "xnn1314279@WIFI";

// 设置静态IP地址
 // 设置固定的IPIPAddress local_IP(10, 184, 199, 100); 
   // 网关地址（通常是.1）IPAddress gateway(10, 184, 199, 1);  
   // 子网掩码IPAddress subnet(255, 255, 255, 0);  

/* NTP时间服务器配置 */
const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = 8 * 3600;  // 东八区
const int daylightOffset_sec = 0;

/* Web服务器 */
ESP8266WebServer server(80);

/* 生产级数据结构 */
struct GrowthHistory {
  float health_scores[24];         // 24小时历史数据
  float temperature_history[24];   // 24小时温度历史
  float humidity_history[24];      // 24小时湿度历史
  float light_history[24];         // 24小时光照历史
  int hour_index;                  // 当前小时索引
  float trend_direction;           // -1.0到1.0趋势方向
  float trend_strength;            // 趋势强度 0-1
  int estimated_days_to_issue;     // 预估出现问题天数
  float growth_rate;               // 生长速率 (%/天)
  String trend_description;        // 趋势描述
};

struct ProductionMetrics {
  float daily_avg_health;          // 日均健康分
  float weekly_growth_score;       // 周生长得分
  int optimal_hours_count;         // 最适环境小时数
  int stress_hours_count;          // 环境胁迫小时数
  float resource_efficiency;       // 资源利用效率
  float predicted_yield;           // 预测产量 (kg/m²)
  float productivity_score;        // 生产力评分 (0-100)
};

struct AlertSystem {
  bool has_alert;                  // 是否有警报
  String alert_level;              // 警报级别: info, warning, critical
  String alert_message;            // 警报信息
  unsigned long alert_time;        // 警报时间
  bool is_acknowledged;            // 是否已确认
};

/* 系统主数据结构 */
struct SystemData {
   // 传感器数据
  int temperature = 25;
  int humidity = 50;
  int light = 50;
  int air_quality = 50;
  
  // AI预测状态 - 现在从STM32获取
  int ai_enabled = 0;           // AI是否启用
  int ai_prediction = 0;        // AI预测结果 (0=BAD, 1=GOOD)
  float ai_confidence = 0.57;   // AI置信度
  float bad_growth_prob = 0.0;  // 不良生长概率
  float good_growth_prob = 0.0; // 良好生长概率
  
  // 生长状态
  int growth_status = 0;           // 0:正常, 1:注意, 2:危险
  float health_score = 0.0;        // 健康分数 0-100
  String plant_advice = "等待AI预测...";
  
  // 环境单项评价
  String temp_eval = "待评估";
  String humi_eval = "待评估";
  String light_eval = "待评估";
  String air_eval = "待评估";
  
  // 新增：生产指标
  GrowthHistory history;
  ProductionMetrics metrics;
  AlertSystem alert;
  
  // 控制状态
  String control_mode = "auto";
  int relay1 = 0;
  int relay2 = 0;
  int relay3 = 0;
  int relay4 = 0;
  
  // 继电器状态字符串
  String relay1_status = "OFF";
  String relay2_status = "OFF";
  String relay3_status = "OFF";
  String relay4_status = "OFF";
  
  // 手动控制缓存
  int manual_relay1 = 0;
  int manual_relay2 = 0;
  int manual_relay3 = 0;
  int manual_relay4 = 0;
  
  // 系统状态
  String system_time = "00:00";
  int day_count = 0;
  float total_energy_usage = 0.0;  // 总能耗 (kWh)
  
  // 新增：系统运行时间
  unsigned long system_start_time = 0;
} system_data;

/* 函数声明 - 添加这些 */
void updateFromAIPrediction();
void updateEnvironmentEvaluation();
void updateRelayStatusStrings();
void calculateGrowthTrend();
void calculateProductionMetrics();
void generatePlantAdvice();
void checkAlertConditions();
void makeAutoControlDecision();

/* 统一的串口发送函数 */
void sendToSTM32(StaticJsonDocument<256> &doc) {
  String jsonStr;
  serializeJson(doc, jsonStr);
  Serial.println(jsonStr);
  Serial.flush();
  
  Serial.print("📤 发送到STM32: ");
  Serial.println(jsonStr);
}

/* 时间相关函数 */
void initNTP() {
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
  
  Serial.print("🕐 等待NTP时间同步...");
  struct tm timeinfo;
  for (int i = 0; i < 10; i++) {
    if (getLocalTime(&timeinfo)) {
      char timeStr[64];
      strftime(timeStr, sizeof(timeStr), "%Y-%m-%d %H:%M:%S", &timeinfo);
      Serial.print("\n✅ 时间同步成功: ");
      Serial.println(timeStr);
      return;
    }
    delay(1000);
    Serial.print(".");
  }
  Serial.println("\n⚠️ 时间同步失败，使用本地时间");
}

void updateSystemTime() {
  struct tm timeinfo;
  if (getLocalTime(&timeinfo)) {
    char timeStr[16];
    strftime(timeStr, sizeof(timeStr), "%H:%M", &timeinfo);
    system_data.system_time = String(timeStr);
  }
}

/* 更新继电器状态字符串 */
void updateRelayStatusStrings() {
  system_data.relay1_status = system_data.relay1 ? "ON" : "OFF";
  system_data.relay2_status = system_data.relay2 ? "ON" : "OFF";
  system_data.relay3_status = system_data.relay3 ? "ON" : "OFF";
  system_data.relay4_status = system_data.relay4 ? "ON" : "OFF";
}

/* 自定义max函数，处理float类型 */
float myMax(float a, float b) {
  return (a > b) ? a : b;
}

/* 自定义min函数，处理float类型 */
float myMin(float a, float b) {
  return (a < b) ? a : b;
}

/* 初始化历史数据 - 填充合理的模拟数据 */
void initHistoryData() {
  Serial.println("📊 初始化历史数据...");
  
  for (int i = 0; i < 24; i++) {
    // 模拟一天的变化曲线
    float hour_factor = i / 24.0;
    
    // 模拟温度变化 (20-28°C)
    float temp_variation = 4.0 * sin(hour_factor * 2 * PI - PI/2) + 24.0;
    system_data.history.temperature_history[i] = temp_variation;
    
    // 模拟湿度变化 (40-70%)
    float humi_variation = 15.0 * sin(hour_factor * 2 * PI) + 55.0;
    system_data.history.humidity_history[i] = humi_variation;
    
    // 模拟光照变化 (20-70%)
    float light_variation = 25.0 * sin(hour_factor * PI) + 45.0;
    system_data.history.light_history[i] = light_variation;
    
    // 计算健康分
    float temp_score = constrain(1.0 - abs(temp_variation - 24.0) / 10.0, 0, 1);
    float humi_score = constrain(1.0 - abs(humi_variation - 55.0) / 30.0, 0, 1);
    
    // 光照评分 (30-50%为理想)
    float light_score = 0;
    if (light_variation >= 30 && light_variation <= 50) {
      light_score = 0.25f;
    } else if (light_variation >= 20 && light_variation < 30) {
      light_score = 0.20f - (30 - light_variation) * 0.05f;
    } else if (light_variation > 50 && light_variation <= 70) {
      light_score = 0.20f - (light_variation - 50) * 0.05f;
    } else if (light_variation < 20) {
      light_score = 0.05f;
    } else {
      light_score = 0.05f;
    }
    
    float air_score = constrain(1.0 - system_data.air_quality / 200.0, 0, 1);
    
    float simulated_score = (temp_score + humi_score + light_score + air_score) * 25.0;
    system_data.history.health_scores[i] = simulated_score;
    
    if (i % 6 == 0) { // 每6小时输出一次
      Serial.print("  小时 ");
      Serial.print(i);
      Serial.print(": 温度=");
      Serial.print(temp_variation, 1);
      Serial.print("°C, 湿度=");
      Serial.print(humi_variation, 1);
      Serial.print("%, 光照=");
      Serial.print(light_variation, 1);
      Serial.print("%, 健康分=");
      Serial.println(simulated_score, 1);
    }
  }
  
  system_data.history.hour_index = 12; // 从中午开始
  Serial.println("✅ 历史数据初始化完成");
}

/* HTML页面内容 */
const char MAIN_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>智能植物工厂 - 生产管理系统</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
        }
        
        :root {
            --primary: #2ecc71;
            --secondary: #3498db;
            --danger: #e74c3c;
            --warning: #f39c12;
            --dark: #2c3e50;
            --light: #ecf0f1;
            --gray: #95a5a6;
        }
        
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: 300px 1fr 350px;
            gap: 20px;
            height: calc(100vh - 40px);
        }
        
        /* 左侧面板 */
        .left-panel {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            display: flex;
            flex-direction: column;
            backdrop-filter: blur(10px);
        }
        
        .status-header {
            text-align: center;
            margin-bottom: 25px;
            padding-bottom: 20px;
            border-bottom: 2px solid var(--light);
        }
        
        .status-header h1 {
            color: var(--dark);
            font-size: 22px;
            margin-bottom: 8px;
        }
        
        .status-header .subtitle {
            color: var(--gray);
            font-size: 14px;
        }
        
        .sensor-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-bottom: 25px;
        }
        
        .sensor-card {
            background: white;
            padding: 15px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            text-align: center;
            transition: transform 0.3s ease;
        }
        
        .sensor-card:hover {
            transform: translateY(-3px);
        }
        
        .sensor-icon {
            font-size: 24px;
            margin-bottom: 8px;
        }
        
        .sensor-value {
            font-size: 22px;
            font-weight: bold;
            color: var(--dark);
            margin-bottom: 5px;
        }
        
        .sensor-label {
            font-size: 12px;
            color: var(--gray);
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .sensor-eval {
            font-size: 12px;
            margin-top: 5px;
            padding: 2px 8px;
            border-radius: 10px;
            display: inline-block;
        }
        
        /* 主面板 */
        .main-panel {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            overflow-y: auto;
            backdrop-filter: blur(10px);
        }
        
        .main-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 25px;
        }
        
        .health-section {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 15px;
            padding: 25px;
            color: white;
            margin-bottom: 25px;
        }
        
        .health-score {
            text-align: center;
            margin-bottom: 20px;
        }
        
        .score-circle {
            width: 120px;
            height: 120px;
            margin: 0 auto 15px;
            position: relative;
        }
        
        .score-circle svg {
            width: 100%;
            height: 100%;
            transform: rotate(-90deg);
        }
        
        .score-circle circle {
            fill: none;
            stroke-width: 8;
            stroke-linecap: round;
        }
        
        .score-bg {
            stroke: rgba(255, 255, 255, 0.2);
        }
        
        .score-progress {
            stroke: var(--primary);
            stroke-dasharray: 314;
            stroke-dashoffset: 314;
            transition: stroke-dashoffset 1s ease;
        }
        
        .score-number {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 36px;
            font-weight: bold;
        }
        
        .score-label {
            font-size: 14px;
            opacity: 0.9;
        }
        
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 25px;
        }
        
        .metric-card {
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        }
        
        .metric-title {
            font-size: 14px;
            color: var(--gray);
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .metric-value {
            font-size: 28px;
            font-weight: bold;
            color: var(--dark);
        }
        
        .trend-indicator {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            font-size: 12px;
            margin-left: 10px;
            padding: 2px 8px;
            border-radius: 10px;
            background: rgba(0,0,0,0.1);
        }
        
        /* 右侧面板 */
        .right-panel {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            display: flex;
            flex-direction: column;
            backdrop-filter: blur(10px);
        }
        
        .control-section {
            margin-bottom: 25px;
        }
        
        .control-section h3 {
            color: var(--dark);
            margin-bottom: 15px;
            font-size: 18px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .mode-selector {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        
        .mode-btn {
            flex: 1;
            padding: 12px;
            border: 2px solid var(--light);
            background: white;
            border-radius: 10px;
            cursor: pointer;
            text-align: center;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        
        .mode-btn.active {
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }
        
        .relay-controls {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        
        .relay-card {
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            text-align: center;
        }
        
        .relay-name {
            font-size: 14px;
            color: var(--gray);
            margin-bottom: 10px;
        }
        
        .relay-toggle {
            width: 60px;
            height: 30px;
            background: var(--gray);
            border-radius: 15px;
            position: relative;
            cursor: pointer;
            margin: 0 auto;
            transition: background 0.3s ease;
        }
        
        .relay-toggle.active {
            background: var(--primary);
        }
        
        .toggle-slider {
            width: 26px;
            height: 26px;
            background: white;
            border-radius: 50%;
            position: absolute;
            top: 2px;
            left: 2px;
            transition: transform 0.3s ease;
        }
        
        .relay-toggle.active .toggle-slider {
            transform: translateX(30px);
        }
        
        .alert-section {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            border-radius: 15px;
            padding: 20px;
            color: white;
            margin-top: auto;
        }
        
        .alert-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .alert-content {
            font-size: 14px;
            line-height: 1.5;
        }
        
        .ack-btn {
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 12px;
            transition: background 0.3s ease;
        }
        
        .ack-btn:hover {
            background: rgba(255, 255, 255, 0.3);
        }
        
        /* 响应式设计 */
        @media (max-width: 1200px) {
            .container {
                grid-template-columns: 1fr;
                height: auto;
            }
            
            .left-panel, .right-panel {
                height: auto;
            }
        }
        
        /* 动画 */
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
        }
        
        .pulse {
            animation: pulse 2s infinite;
        }
        
        /* 工具提示 */
        .tooltip {
            position: relative;
            display: inline-block;
        }
        
        .tooltip .tooltiptext {
            visibility: hidden;
            width: 200px;
            background-color: var(--dark);
            color: white;
            text-align: center;
            border-radius: 6px;
            padding: 8px;
            position: absolute;
            z-index: 1;
            bottom: 125%;
            left: 50%;
            transform: translateX(-50%);
            font-size: 12px;
            opacity: 0;
            transition: opacity 0.3s;
        }
        
        .tooltip:hover .tooltiptext {
            visibility: visible;
            opacity: 1;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- 左侧面板：传感器数据 -->
        <div class="left-panel">
            <div class="status-header">
                <h1>🌿 植物工厂</h1>
                <div class="subtitle">生产管理系统 v2.0</div>
                <div id="systemTime" class="subtitle">--:--</div>
            </div>
            
            <div class="sensor-grid">
                <div class="sensor-card">
                    <div class="sensor-icon">🌡️</div>
                    <div id="tempValue" class="sensor-value">--°C</div>
                    <div class="sensor-label">温度</div>
                    <div id="tempEval" class="sensor-eval">--</div>
                </div>
                
                <div class="sensor-card">
                    <div class="sensor-icon">💧</div>
                    <div id="humiValue" class="sensor-value">--%</div>
                    <div class="sensor-label">湿度</div>
                    <div id="humiEval" class="sensor-eval">--</div>
                </div>
                
                <div class="sensor-card">
                    <div class="sensor-icon">☀️</div>
                    <div id="lightValue" class="sensor-value">--%</div>
                    <div class="sensor-label">光照</div>
                    <div id="lightEval" class="sensor-eval">--</div>
                </div>
                
                <div class="sensor-card">
                    <div class="sensor-icon">🍃</div>
                    <div id="airValue" class="sensor-value">--%</div>
                    <div class="sensor-label">空气质量</div>
                    <div id="airEval" class="sensor-eval">--</div>
                </div>
            </div>
            
            <div class="ai-status">
                <div class="metric-card">
                    <div class="metric-title">🤖 AI预测状态</div>
                    <div class="metric-value">
                        <span id="aiPrediction">--</span>
                        <span id="aiConfidence" class="trend-indicator">--%</span>
                    </div>
                    <div id="growthStatus" class="sensor-eval" style="margin-top: 10px;">--</div>
                </div>
            </div>
        </div>
        
        <!-- 主面板：健康评分和生产指标 -->
        <div class="main-panel">
            <div class="main-header">
                <h2>📊 生产指标总览</h2>
                <div class="mode-selector">
                    <div class="mode-btn" data-mode="auto">🤖 自动</div>
                    <div class="mode-btn" data-mode="manual">👋 手动</div>
                    <div class="mode-btn" data-mode="hybrid">🔄 混合</div>
                </div>
            </div>
            
            <div class="health-section">
                <div class="health-score">
                    <div class="score-circle">
                        <svg>
                            <circle class="score-bg" cx="60" cy="60" r="50"></circle>
                            <circle id="scoreCircle" class="score-progress" cx="60" cy="60" r="50"></circle>
                        </svg>
                        <div class="score-number" id="healthScore">--</div>
                    </div>
                    <div class="score-label">植物健康评分</div>
                </div>
                
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-title">📈 生长趋势</div>
                        <div class="metric-value">
                            <span id="trendDirection">--</span>
                            <span id="trendStrength" class="trend-indicator">--</span>
                        </div>
                        <div id="trendDescription" style="font-size: 12px; margin-top: 5px;">--</div>
                    </div>
                    
                    <div class="metric-card">
                        <div class="metric-title">🌱 生长速率</div>
                        <div class="metric-value" id="growthRate">--%/天</div>
                        <div style="font-size: 12px; margin-top: 5px; color: var(--gray)">
                            最近24小时
                        </div>
                    </div>
                    
                    <div class="metric-card">
                        <div class="metric-title">🎯 预测产量</div>
                        <div class="metric-value">
                            <span id="predictedYield">--</span>
                            <span style="font-size: 16px; margin-left: 2px;">kg/m²</span>
                        </div>
                        <div style="font-size: 12px; margin-top: 5px; color: var(--gray)">
                            基于当前环境
                        </div>
                    </div>
                    
                    <div class="metric-card">
                        <div class="metric-title">⚡ 资源效率</div>
                        <div class="metric-value" id="resourceEfficiency">--分/kWh</div>
                        <div style="font-size: 12px; margin-top: 5px; color: var(--gray)">
                            健康分/能耗
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="control-advice">
                <div class="metric-card">
                    <div class="metric-title">💡 生长建议</div>
                    <div id="plantAdvice" style="font-size: 14px; line-height: 1.6; padding: 10px 0;">
                        正在获取建议...
                    </div>
                </div>
            </div>
            
            <div class="metrics-grid" style="margin-top: 20px;">
                <div class="metric-card">
                    <div class="metric-title">⏱️ 最适环境</div>
                    <div class="metric-value" id="optimalHours">--/24h</div>
                    <div style="font-size: 12px; margin-top: 5px; color: var(--gray)">
                        今日累计
                    </div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-title">📊 生产力评分</div>
                    <div class="metric-value" id="productivityScore">--/100</div>
                    <div style="font-size: 12px; margin-top: 5px; color: var(--gray)">
                        综合指标
                    </div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-title">📅 日均健康</div>
                    <div class="metric-value" id="dailyAvgHealth">--</div>
                    <div style="font-size: 12px; margin-top: 5px; color: var(--gray)">
                        24小时平均
                    </div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-title">⚠️ 预计问题</div>
                    <div class="metric-value" id="estimatedDays">--天</div>
                    <div style="font-size: 12px; margin-top: 5px; color: var(--gray)">
                        风险预测
                    </div>
                </div>
            </div>
        </div>
        
        <!-- 右侧面板：控制和警报 -->
        <div class="right-panel">
            <div class="control-section">
                <h3>🔧 设备控制</h3>
                <div id="currentMode" class="subtitle">当前模式: 自动</div>
                
                <div class="relay-controls">
                    <div class="relay-card">
                        <div class="relay-name">💧 加湿器</div>
                        <div class="relay-status" id="relay1Status">OFF</div>
                        <div class="relay-toggle" data-relay="1">
                            <div class="toggle-slider"></div>
                        </div>
                    </div>
                    
                    <div class="relay-card">
                        <div class="relay-name">🔥 加热器</div>
                        <div class="relay-status" id="relay2Status">OFF</div>
                        <div class="relay-toggle" data-relay="2">
                            <div class="toggle-slider"></div>
                        </div>
                    </div>
                    
                    <div class="relay-card">
                        <div class="relay-name">💡 补光灯</div>
                        <div class="relay-status" id="relay3Status">OFF</div>
                        <div class="relay-toggle" data-relay="3">
                            <div class="toggle-slider"></div>
                        </div>
                    </div>
                    
                    <div class="relay-card">
                        <div class="relay-name">💨 通风扇</div>
                        <div class="relay-status" id="relay4Status">OFF</div>
                        <div class="relay-toggle" data-relay="4">
                            <div class="toggle-slider"></div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="alert-section" id="alertSection" style="display: none;">
                <div class="alert-header">
                    <h3>🚨 系统警报</h3>
                    <button class="ack-btn" id="ackBtn">确认</button>
                </div>
                <div class="alert-content">
                    <div id="alertLevel"></div>
                    <div id="alertMessage"></div>
                    <div id="alertTime" style="font-size: 12px; opacity: 0.8; margin-top: 5px;"></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // 全局变量
        let currentMode = 'auto';
        
        // DOM加载完成后执行
        document.addEventListener('DOMContentLoaded', function() {
            // 初始化模式选择
            const modeBtns = document.querySelectorAll('.mode-btn');
            modeBtns.forEach(btn => {
                btn.addEventListener('click', function() {
                    const mode = this.getAttribute('data-mode');
                    setControlMode(mode);
                });
            });
            
            // 初始化继电器控制
            const relayToggles = document.querySelectorAll('.relay-toggle');
            relayToggles.forEach(toggle => {
                toggle.addEventListener('click', function() {
                    const relay = this.getAttribute('data-relay');
                    toggleRelay(relay);
                });
            });
            
            // 警报确认按钮
            document.getElementById('ackBtn').addEventListener('click', acknowledgeAlert);
            
            // 开始轮询数据
            updateData();
            setInterval(updateData, 2000);
        });
        
        // 更新数据
        async function updateData() {
            try {
                const response = await fetch('/data');
                const data = await response.json();
                
                // 更新传感器数据
                document.getElementById('tempValue').textContent = data.temperature + '°C';
                document.getElementById('humiValue').textContent = data.humidity + '%';
                document.getElementById('lightValue').textContent = data.light + '%';
                document.getElementById('airValue').textContent = data.air_quality + '%';
                
                // 更新环境评价
                document.getElementById('tempEval').textContent = data.temp_eval;
                document.getElementById('humiEval').textContent = data.humi_eval;
                document.getElementById('lightEval').textContent = data.light_eval;
                document.getElementById('airEval').textContent = data.air_eval;
                
                // 更新AI状态
                document.getElementById('aiPrediction').textContent = 
                    data.ai_prediction === 1 ? '良好' : '需注意';
                document.getElementById('aiConfidence').textContent = 
                    Math.round(data.ai_confidence * 100) + '%';
                
                // 更新生长状态
                const statusElem = document.getElementById('growthStatus');
                let statusText = '';
                let statusColor = '';
                if (data.growth_status === 0) {
                    statusText = '正常';
                    statusColor = '#2ecc71';
                } else if (data.growth_status === 1) {
                    statusText = '注意';
                    statusColor = '#f39c12';
                } else {
                    statusText = '危险';
                    statusColor = '#e74c3c';
                }
                statusElem.textContent = statusText;
                statusElem.style.background = statusColor;
                statusElem.style.color = 'white';
                
                // 更新健康评分
                const healthScore = data.health_score;
                document.getElementById('healthScore').textContent = Math.round(healthScore);
                
                // 更新评分圆环
                const circle = document.getElementById('scoreCircle');
                const circumference = 314; // 2 * π * 50
                const offset = circumference - (healthScore / 100) * circumference;
                circle.style.strokeDashoffset = offset;
                
                // 根据分数设置颜色
                if (healthScore >= 70) {
                    circle.style.stroke = '#2ecc71';
                } else if (healthScore >= 50) {
                    circle.style.stroke = '#f39c12';
                } else {
                    circle.style.stroke = '#e74c3c';
                }
                
                // 更新趋势数据
                document.getElementById('trendDirection').textContent = 
                    data.trend_direction > 0 ? '+' + data.trend_direction.toFixed(2) : 
                    data.trend_direction.toFixed(2);
                document.getElementById('trendStrength').textContent = 
                    '强度: ' + (data.trend_strength * 100).toFixed(0) + '%';
                document.getElementById('trendDescription').textContent = data.trend_description;
                
                // 更新生产指标
                document.getElementById('growthRate').textContent = 
                    data.growth_rate.toFixed(2) + '%/天';
                
                // 更新预测产量（数值+单位）
                const yieldValue = data.predicted_yield || 0;
                document.getElementById('predictedYield').textContent = yieldValue.toFixed(1);
                
                document.getElementById('resourceEfficiency').textContent = 
                    data.resource_efficiency.toFixed(1) + '分/kWh';
                document.getElementById('optimalHours').textContent = 
                    data.optimal_hours_count + '/24h';
                document.getElementById('productivityScore').textContent = 
                    data.productivity_score.toFixed(1) + '/100';
                document.getElementById('dailyAvgHealth').textContent = 
                    data.daily_avg_health.toFixed(1);
                
                // 更新预计问题天数
                const daysElem = document.getElementById('estimatedDays');
                if (data.estimated_days_to_issue > 0) {
                    daysElem.textContent = data.estimated_days_to_issue + '天';
                    daysElem.style.color = data.estimated_days_to_issue <= 3 ? '#e74c3c' : '#f39c12';
                } else {
                    daysElem.textContent = '无风险';
                    daysElem.style.color = '#2ecc71';
                }
                
                // 更新生长建议
                document.getElementById('plantAdvice').textContent = data.plant_advice;
                
                // 更新继电器状态
                updateRelayStatus(1, data.relay1, data.relay1_status);
                updateRelayStatus(2, data.relay2, data.relay2_status);
                updateRelayStatus(3, data.relay3, data.relay3_status);
                updateRelayStatus(4, data.relay4, data.relay4_status);
                
                // 更新控制模式
                currentMode = data.control_mode;
                document.getElementById('currentMode').textContent = 
                    '当前模式: ' + (currentMode === 'auto' ? '自动' : 
                                  currentMode === 'manual' ? '手动' : '混合');
                
                // 更新模式按钮状态
                document.querySelectorAll('.mode-btn').forEach(btn => {
                    if (btn.getAttribute('data-mode') === currentMode) {
                        btn.classList.add('active');
                    } else {
                        btn.classList.remove('active');
                    }
                });
                
                // 更新系统时间
                document.getElementById('systemTime').textContent = data.system_time;
                
                // 更新警报
                if (data.has_alert && !data.alert_acknowledged) {
                    const alertSection = document.getElementById('alertSection');
                    alertSection.style.display = 'block';
                    document.getElementById('alertLevel').textContent = 
                        '级别: ' + (data.alert_level === 'critical' ? '严重' : 
                                   data.alert_level === 'warning' ? '警告' : '信息');
                    document.getElementById('alertMessage').textContent = data.alert_message;
                    
                    // 设置警报颜色
                    if (data.alert_level === 'critical') {
                        alertSection.style.background = 'linear-gradient(135deg, #f5576c 0%, #f093fb 100%)';
                    } else if (data.alert_level === 'warning') {
                        alertSection.style.background = 'linear-gradient(135deg, #f6d365 0%, #fda085 100%)';
                    }
                } else {
                    document.getElementById('alertSection').style.display = 'none';
                }
                
            } catch (error) {
                console.error('获取数据失败:', error);
            }
        }
        
        // 更新继电器状态显示
        function updateRelayStatus(relay, state, statusText) {
            const toggle = document.querySelector(`.relay-toggle[data-relay="${relay}"]`);
            const statusElem = document.getElementById(`relay${relay}Status`);
            
            if (toggle) {
                if (state === 1) {
                    toggle.classList.add('active');
                } else {
                    toggle.classList.remove('active');
                }
            }
            
            if (statusElem) {
                statusElem.textContent = statusText;
                statusElem.style.color = state === 1 ? '#2ecc71' : '#e74c3c';
            }
        }
        
        // 切换继电器状态
        async function toggleRelay(relay) {
            if (currentMode !== 'manual') {
                alert('请在手动模式下操作继电器');
                return;
            }
            
            const currentState = document.querySelector(`.relay-toggle[data-relay="${relay}"]`).classList.contains('active') ? 0 : 1;
            
            try {
                const response = await fetch('/control', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        relay: parseInt(relay),
                        state: currentState
                    })
                });
                
                const result = await response.json();
                if (result.success) {
                    // 更新本地状态
                    updateRelayStatus(relay, currentState, currentState ? 'ON' : 'OFF');
                } else {
                    alert('控制失败: ' + result.error);
                }
            } catch (error) {
                console.error('控制请求失败:', error);
            }
        }
        
        // 设置控制模式
        async function setControlMode(mode) {
            try {
                const response = await fetch('/mode', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ mode: mode })
                });
                
                const result = await response.json();
                if (result.success) {
                    currentMode = mode;
                    document.getElementById('currentMode').textContent = 
                        '当前模式: ' + (mode === 'auto' ? '自动' : 
                                      mode === 'manual' ? '手动' : '混合');
                    
                    // 更新按钮状态
                    document.querySelectorAll('.mode-btn').forEach(btn => {
                        if (btn.getAttribute('data-mode') === mode) {
                            btn.classList.add('active');
                        } else {
                            btn.classList.remove('active');
                        }
                    });
                    
                    // 如果是自动模式，更新一次数据
                    if (mode === 'auto') {
                        setTimeout(updateData, 1000);
                    }
                }
            } catch (error) {
                console.error('切换模式失败:', error);
            }
        }
        
        // 确认警报
        async function acknowledgeAlert() {
            try {
                await fetch('/acknowledge', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                });
                
                document.getElementById('alertSection').style.display = 'none';
            } catch (error) {
                console.error('确认警报失败:', error);
            }
        }
    </script>
</body>
</html>
)rawliteral";


/* 生产指标计算函数 - 完整版 */
void calculateProductionMetrics() {
  // 计算日均健康分
  float sum = 0;
  int valid_count = 0;
  for (int i = 0; i < 24; i++) {
    if (system_data.history.health_scores[i] > 0) {
      sum += system_data.history.health_scores[i];
      valid_count++;
    }
  }
  
  if (valid_count > 0) {
    system_data.metrics.daily_avg_health = sum / valid_count;
  } else {
    system_data.metrics.daily_avg_health = system_data.health_score > 0 ? system_data.health_score : 75.0;
  }
  
  // 计算最适环境小时数（光照范围改为30-50）
  system_data.metrics.optimal_hours_count = 0;
  for (int i = 0; i < 24; i++) {
    float temp = system_data.history.temperature_history[i];
    float humi = system_data.history.humidity_history[i];
    float light_val = system_data.history.light_history[i];
    
    if (temp >= 20 && temp <= 28 && 
        humi >= 40 && humi <= 70 && 
        light_val >= 30 && light_val <= 50) {  // 修改这里
      system_data.metrics.optimal_hours_count++;
    }
  }
  
  // 确保至少有1小时的最适环境
  if (system_data.metrics.optimal_hours_count == 0) {
    system_data.metrics.optimal_hours_count = 8; // 默认值
  }
  
  // 计算环境胁迫小时数
  system_data.metrics.stress_hours_count = 0;
  for (int i = 0; i < 24; i++) {
    float temp = system_data.history.temperature_history[i];
    float humi = system_data.history.humidity_history[i];
    
    if (temp < 15 || temp > 35 || humi < 30 || humi > 80) {
      system_data.metrics.stress_hours_count++;
    }
  }
  
  // 计算生长速率 (基于最近6小时变化)
  float recent_sum = 0;
  int recent_count = 0;
  for (int i = 0; i < 6; i++) {
    int idx = (system_data.history.hour_index - i - 1 + 24) % 24;
    if (system_data.history.health_scores[idx] > 0) {
      recent_sum += system_data.history.health_scores[idx];
      recent_count++;
    }
  }
  
  float older_sum = 0;
  int older_count = 0;
  for (int i = 6; i < 12; i++) {
    int idx = (system_data.history.hour_index - i - 1 + 24) % 24;
    if (system_data.history.health_scores[idx] > 0) {
      older_sum += system_data.history.health_scores[idx];
      older_count++;
    }
  }
  
  if (older_count > 0 && recent_count > 0) {
    float avg_recent = recent_sum / recent_count;
    float avg_older = older_sum / older_count;
    
    // 避免除零和无效值
    if (avg_older > 0.1) {
      system_data.history.growth_rate = ((avg_recent - avg_older) / avg_older) * 100.0 * 4.0;
    } else {
      system_data.history.growth_rate = 0.0;
    }
    
    // 限制范围
    system_data.history.growth_rate = constrain(system_data.history.growth_rate, -10.0, 10.0);
  } else {
    // 使用基于当前环境的模拟生长速率
    float temp_factor = constrain(1.0 - abs(system_data.temperature - 24.0) / 20.0, 0, 1);
    float humi_factor = constrain(1.0 - abs(system_data.humidity - 55.0) / 50.0, 0, 1);
    float light_factor = 0;
    if (system_data.light >= 30 && system_data.light <= 50) {
      light_factor = 1.0;
    } else if (system_data.light >= 20 && system_data.light < 30) {
      light_factor = 0.5 + (system_data.light - 20) * 0.05;
    } else if (system_data.light > 50 && system_data.light <= 70) {
      light_factor = 1.0 - (system_data.light - 50) * 0.05;
    } else {
      light_factor = 0.2;
    }
    
    system_data.history.growth_rate = (temp_factor + humi_factor + light_factor) / 3.0 * 2.0;
  }
  
  // 计算预测产量 (kg/m²) - 更符合实际的产量单位
  float health_factor = system_data.health_score / 100.0;
  
  // 趋势影响因子
  float trend_factor = 1.0;
  if (system_data.history.trend_direction > 0.1) {
    trend_factor = 1.0 + system_data.history.trend_direction * 0.3;
  } else if (system_data.history.trend_direction < -0.1) {
    trend_factor = 1.0 + system_data.history.trend_direction * 0.5;
  }
  trend_factor = constrain(trend_factor, 0.7, 1.3);
  
  // 环境适宜度因子
  float optimal_factor = system_data.metrics.optimal_hours_count / 24.0;
  optimal_factor = myMax(optimal_factor, 0.3f);
  
  // 基准产量：假设在理想条件下每平方米产量为15kg
  float base_yield = 15.0;  // kg/m²
  
  // 计算预测产量 (kg/m²)
  system_data.metrics.predicted_yield = base_yield * health_factor * trend_factor * optimal_factor;
  system_data.metrics.predicted_yield = constrain(system_data.metrics.predicted_yield, 0, 20.0);
  
  // 计算生产力评分 (综合评分)
  float health_weight = 0.4;
  float trend_weight = 0.3;
  float optimal_weight = 0.3;
  
  system_data.metrics.productivity_score = 
    (system_data.health_score * health_weight + 
     (system_data.history.trend_direction + 1.0) * 50.0 * trend_weight +
     optimal_factor * 100.0 * optimal_weight);
  system_data.metrics.productivity_score = constrain(system_data.metrics.productivity_score, 0, 100);
  
  // 计算资源利用效率
  float active_relays = system_data.relay1 + system_data.relay2 + 
                       system_data.relay3 + system_data.relay4;
  float energy_per_hour = active_relays * 0.1;  // 假设每个继电器0.1kW
  
  // 模拟能耗累加
  static unsigned long last_energy_update = 0;
  if (last_energy_update == 0) last_energy_update = millis();
  
  float hours_passed = (millis() - last_energy_update) / 3600000.0;
  if (hours_passed > 0.01) {  // 至少0.01小时(36秒)才更新
    system_data.total_energy_usage += energy_per_hour * hours_passed;
    last_energy_update = millis();
  }
  
  if (system_data.total_energy_usage > 0.01) {
    system_data.metrics.resource_efficiency = system_data.health_score / system_data.total_energy_usage;
  } else {
    system_data.metrics.resource_efficiency = 100.0;  // 初始值
  }
  
  // 限制资源效率范围
  system_data.metrics.resource_efficiency = constrain(system_data.metrics.resource_efficiency, 0, 500);
  
  // 调试输出
  Serial.println("📊 生产指标计算完成:");
  Serial.print("  日均健康分: ");
  Serial.println(system_data.metrics.daily_avg_health, 1);
  Serial.print("  最适环境小时: ");
  Serial.print(system_data.metrics.optimal_hours_count);
  Serial.println("/24");
  Serial.print("  生长速率: ");
  Serial.print(system_data.history.growth_rate, 2);
  Serial.println("%/天");
  Serial.print("  预测产量: ");
  Serial.print(system_data.metrics.predicted_yield, 1);
  Serial.println("kg/m²");
  Serial.print("  生产力评分: ");
  Serial.print(system_data.metrics.productivity_score, 1);
  Serial.println("/100");
  Serial.print("  资源效率: ");
  Serial.print(system_data.metrics.resource_efficiency, 1);
  Serial.println("分/kWh");
}

/* 生长趋势分析 - 增强版 */
void calculateGrowthTrend() {
  int window_size = 8;  // 分析最近8小时
  
  // 收集最近数据
  float recent_values[8];
  for (int i = 0; i < window_size; i++) {
    int idx = (system_data.history.hour_index - i - 1 + 24) % 24;
    recent_values[i] = system_data.history.health_scores[idx];
  }
  
  // 计算线性回归趋势
  float sum_x = 0, sum_y = 0, sum_xy = 0, sum_x2 = 0;
  int valid_points = 0;
  
  for (int i = 0; i < window_size; i++) {
    if (recent_values[i] > 0) {
      sum_x += i;
      sum_y += recent_values[i];
      sum_xy += i * recent_values[i];
      sum_x2 += i * i;
      valid_points++;
    }
  }
  
  if (valid_points >= 3) {
    float n = valid_points;
    float slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x);
    
    // 归一化趋势方向 (-1到1)
    system_data.history.trend_direction = constrain(slope * 5, -1.0, 1.0);
    
    // 计算趋势强度
    float mean = sum_y / n;
    float variance = 0;
    for (int i = 0; i < window_size; i++) {
      if (recent_values[i] > 0) {
        variance += pow(recent_values[i] - mean, 2);
      }
    }
    variance /= n;
    
    system_data.history.trend_strength = myMin(variance / 500.0, 1.0);
  } else {
    // 数据不足，使用环境变化趋势
    float temp_change = system_data.temperature - 24.0;
    float humi_change = system_data.humidity - 55.0;
    float light_change = system_data.light - 40.0; // 以40为中心
    
    float env_trend = -(abs(temp_change) + abs(humi_change) + abs(light_change)) / 100.0;
    system_data.history.trend_direction = constrain(env_trend, -1.0, 1.0);
    system_data.history.trend_strength = 0.5;
  }
  
  // 生成趋势描述
  if (system_data.history.trend_direction > 0.3) {
    system_data.history.trend_description = "快速改善";
  } else if (system_data.history.trend_direction > 0.1) {
    system_data.history.trend_description = "缓慢改善";
  } else if (system_data.history.trend_direction > 0.02) {
    system_data.history.trend_description = "微幅改善";
  } else if (system_data.history.trend_direction < -0.3) {
    system_data.history.trend_description = "快速恶化";
  } else if (system_data.history.trend_direction < -0.1) {
    system_data.history.trend_description = "缓慢恶化";
  } else if (system_data.history.trend_direction < -0.02) {
    system_data.history.trend_description = "微幅下降";
  } else {
    system_data.history.trend_description = "保持平稳";
  }
  
  // 预估出现问题天数
  if (system_data.history.trend_direction < -0.1 && system_data.health_score > 0) {
    // 线性外推法预测
    float days_to_60 = (60.0 - system_data.health_score) / 
                      (abs(system_data.history.trend_direction) * system_data.health_score * 24.0);
    system_data.history.estimated_days_to_issue = max(1, (int)ceil(days_to_60));
  } else {
    system_data.history.estimated_days_to_issue = -1;  // 无风险
  }
  
  Serial.print("📈 趋势分析: 方向=");
  Serial.print(system_data.history.trend_direction, 3);
  Serial.print(", 强度=");
  Serial.print(system_data.history.trend_strength, 3);
  Serial.print(", 描述=");
  Serial.print(system_data.history.trend_description);
  Serial.print(", 预计问题天数=");
  Serial.println(system_data.history.estimated_days_to_issue);
}

/* 智能警报系统 */
void checkAlertConditions() {
  // 清除已确认的警报
  if (system_data.alert.is_acknowledged) {
    system_data.alert.has_alert = false;
    system_data.alert.is_acknowledged = false;
  }
  
  // 检查各项警报条件
  String new_alert = "";
  String level = "info";
  
  // 1. 温度警报
  if (system_data.temperature < 10) {
    new_alert = "❄️ 温度过低 (" + String(system_data.temperature) + "°C)，可能冻伤";
    level = "critical";
  } else if (system_data.temperature > 35) {
    new_alert = "🔥 温度过高 (" + String(system_data.temperature) + "°C)，可能热害";
    level = "critical";
  }
  
  // 2. 湿度警报
  if (system_data.humidity < 20) {
    new_alert = "🏜️ 湿度过低 (" + String(system_data.humidity) + "%)，植物脱水风险";
    level = "warning";
  } else if (system_data.humidity > 90) {
    new_alert = "💦 湿度过高 (" + String(system_data.humidity) + "%)，易发霉菌病害";
    level = "warning";
  }
  
  // 3. 光照警报（新增）
  if (system_data.light < 20) {
    new_alert = "🌑 光照严重不足 (" + String(system_data.light) + "%)，生长受阻";
    level = "warning";
  } else if (system_data.light > 80) {
    new_alert = "☀️ 光照过强 (" + String(system_data.light) + "%)，可能灼伤叶片";
    level = "warning";
  }
  
  // 4. 产量警报
  if (system_data.metrics.predicted_yield < 5.0) {
    new_alert = "📊 预测产量较低 (" + String(system_data.metrics.predicted_yield, 1) + 
                "kg/m²)，请检查环境条件";
    level = "info";
  }
  
  // 5. 生长趋势警报
  if (system_data.history.estimated_days_to_issue > 0 && 
      system_data.history.estimated_days_to_issue <= 3) {
    new_alert = "📉 生长趋势不佳，预计" + 
                String(system_data.history.estimated_days_to_issue) + 
                "天内健康分降至危险水平";
    level = "warning";
  }
  
  // 6. 资源效率警报
  if (system_data.metrics.resource_efficiency < 30 && 
      system_data.total_energy_usage > 1.0) {
    new_alert = "⚡ 资源利用效率低 (" + 
                String(system_data.metrics.resource_efficiency, 1) + 
                "分/kWh)，建议优化控制策略";
    level = "info";
  }
  
  // 更新警报状态
  if (new_alert.length() > 0) {
    system_data.alert.has_alert = true;
    system_data.alert.alert_level = level;
    system_data.alert.alert_message = new_alert;
    system_data.alert.alert_time = millis();
    
    Serial.print("🚨 生成警报[");
    Serial.print(level);
    Serial.print("]: ");
    Serial.println(new_alert);
  }
}

/* 优化版植物生长建议生成 */
void generatePlantAdvice() {
  String advice = "";
  int issues = 0;
  
  // 基于趋势的建议
  if (system_data.history.trend_direction < -0.2) {
    advice += "📉 生长趋势下降，请检查环境参数；";
    issues++;
  }
  
  // 环境参数建议
  if (system_data.temperature < 18) {
    advice += "🔥 温度偏低(" + String(system_data.temperature) + "°C)，建议加热至22-26°C；";
    issues++;
  } else if (system_data.temperature > 28) {
    advice += "🌬️ 温度偏高(" + String(system_data.temperature) + "°C)，建议通风降温；";
    issues++;
  }
  
  if (system_data.humidity < 40) {
    advice += "💧 湿度不足(" + String(system_data.humidity) + "%)，建议加湿至50-65%；";
    issues++;
  } else if (system_data.humidity > 70) {
    advice += "💨 湿度过高(" + String(system_data.humidity) + "%)，建议通风除湿；";
    issues++;
  }
  
  // 光照建议（按照新标准）
  if (system_data.light < 30) {
    advice += "💡 光照太暗(" + String(system_data.light) + "%)，建议补光8-10小时；";
    issues++;
  } else if (system_data.light > 70) {
    advice += "🌥️ 光照太亮(" + String(system_data.light) + "%)，建议遮荫保护；";
    issues++;
  } else if (system_data.light < 40) {
    advice += "💡 光照偏暗(" + String(system_data.light) + "%)，建议适当补光；";
    issues++;
  } else if (system_data.light > 60) {
    advice += "🌥️ 光照偏亮(" + String(system_data.light) + "%)，可考虑适当遮荫；";
    issues++;
  }
  
  if (system_data.air_quality > 60) {
    advice += "🍃 空气质量较差(" + String(system_data.air_quality) + "%)，建议通风换气；";
    issues++;
  }
  
  // 生产优化建议
  if (system_data.metrics.optimal_hours_count < 12) {
    advice += "🕐 今日最适环境时长仅" + String(system_data.metrics.optimal_hours_count) + 
              "小时，建议优化控制；";
    issues++;
  }
  
  if (system_data.metrics.predicted_yield < 8.0) {
    advice += "📊 预测产量较低(" + String(system_data.metrics.predicted_yield, 1) + 
              "kg/m²)，请关注生长环境；";
    issues++;
  }
  
  // 生长速率建议
  if (system_data.history.growth_rate < 0.5) {
    advice += "📈 生长速率较慢(" + String(system_data.history.growth_rate, 1) + 
              "%/天)，建议优化养分供应；";
    issues++;
  }
  
  if (issues == 0) {
    if (system_data.history.trend_direction > 0.1) {
      advice = "✅ 环境条件理想，生长趋势良好，保持当前设置！";
    } else {
      advice = "✅ 环境条件理想，继续保持！";
    }
  }
  
  system_data.plant_advice = advice;
}

/* AI预测函数 - 现在由STM32处理，这里只更新相关指标 */
void runAIPrediction() {
  // 这个函数现在只是保持定时更新趋势和指标
  calculateGrowthTrend();
  calculateProductionMetrics();
  checkAlertConditions();
}

/* 自动控制决策 */
void makeAutoControlDecision() {
  if (system_data.control_mode != "auto") return;
  
  StaticJsonDocument<256> controlDoc;
  bool needs_action = false;
  
  // 基于AI预测的控制逻辑
  if (system_data.growth_status == 2) {  // 危险状态
    // 紧急控制逻辑
    if (system_data.temperature < 18) {
      controlDoc["relay"] = 2;  // 加热
      controlDoc["state"] = 1;
      needs_action = true;
      Serial.println("🔧 自动控制: 温度过低，开启加热");
    } else if (system_data.temperature > 30) {
      controlDoc["relay"] = 4;  // 通风
      controlDoc["state"] = 1;
      needs_action = true;
      Serial.println("🔧 自动控制: 温度过高，开启通风");
    }
    
    if (system_data.humidity < 35) {
      controlDoc["relay"] = 1;  // 加湿
      controlDoc["state"] = 1;
      needs_action = true;
      Serial.println("🔧 自动控制: 湿度过低，开启加湿");
    }
    
    // 光照控制（按照新标准）
    if (system_data.light < 25) {
      controlDoc["relay"] = 3;  // 补光
      controlDoc["state"] = 1;
      needs_action = true;
      Serial.println("🔧 自动控制: 光照太暗，开启补光");
    }
  } else if (system_data.growth_status == 1) {  // 注意状态
    // 优化控制逻辑
    if (system_data.temperature < 20 || system_data.temperature > 28) {
      if (system_data.temperature < 20) {
        controlDoc["relay"] = 2;  // 加热
        controlDoc["state"] = 1;
        Serial.println("🔧 自动控制: 温度偏低，开启加热");
      } else {
        controlDoc["relay"] = 4;  // 通风
        controlDoc["state"] = 1;
        Serial.println("🔧 自动控制: 温度偏高，开启通风");
      }
      needs_action = true;
    }
    
    if (system_data.humidity < 40 || system_data.humidity > 65) {
      controlDoc["relay"] = 1;  // 加湿或除湿
      controlDoc["state"] = system_data.humidity < 40 ? 1 : 0;
      needs_action = true;
      Serial.print("🔧 自动控制: 湿度");
      Serial.print(system_data.humidity < 40 ? "过低" : "过高");
      Serial.println("，调整湿度控制");
    }
    
    // 光照优化控制
    if (system_data.light < 30) {
      controlDoc["relay"] = 3;  // 补光
      controlDoc["state"] = 1;
      needs_action = true;
      Serial.println("🔧 自动控制: 光照偏暗，开启补光");
    } else if (system_data.light > 70 && system_data.relay3) {
      controlDoc["relay"] = 3;  // 关闭补光
      controlDoc["state"] = 0;
      needs_action = true;
      Serial.println("🔧 自动控制: 光照太亮，关闭补光");
    }
  }
  
  // 节能控制逻辑
  if (system_data.metrics.resource_efficiency < 30 && 
      system_data.total_energy_usage > 2.0) {
    // 资源效率低，减少不必要的控制
    if (system_data.relay3 && system_data.light > 50) {  // 光照足够时关闭补光
      controlDoc["relay"] = 3;
      controlDoc["state"] = 0;
      needs_action = true;
      Serial.println("🔧 自动控制: 光照充足，关闭补光以节能");
    }
  }
  
  if (needs_action) {
    controlDoc["cmd"] = "auto_control";
    controlDoc["reason"] = system_data.growth_status == 2 ? "紧急" : "优化";
    sendToSTM32(controlDoc);
  }
}

/* 根据STM32的AI预测更新本地状态 */
void updateFromAIPrediction() {
  if (!system_data.ai_enabled) {
    system_data.health_score = 0;
    system_data.plant_advice = "AI模型未启用，等待数据...";
    return;
  }
  
  // 使用AI预测结果更新健康分数
  if (system_data.ai_prediction == 1) { // GOOD
    // GOOD预测，健康分在70-100之间
    system_data.health_score = 70.0 + system_data.ai_confidence * 30.0;
    
    // 根据置信度调整生长状态
    if (system_data.ai_confidence > 0.8) {
      system_data.growth_status = 0; // 正常
    } else {
      system_data.growth_status = 1; // 注意
    }
  } else { // BAD
    // BAD预测，健康分在0-70之间
    system_data.health_score = 70.0 - system_data.ai_confidence * 70.0;
    // 确保健康分不低于0
    if (system_data.health_score < 0) {
      system_data.health_score = 0;
    }
    
    if (system_data.ai_confidence > 0.7) {
      system_data.growth_status = 2; // 危险
    } else {
      system_data.growth_status = 1; // 注意
    }
  }
  
  // 根据传感器数据更新环境评价
  updateEnvironmentEvaluation();
  
  // 生成植物建议
  generatePlantAdvice();
  
  // 记录到历史数据
  static unsigned long last_record = 0;
  if (millis() - last_record > 180000) {  // 每3分钟记录一次
    system_data.history.health_scores[system_data.history.hour_index] = system_data.health_score;
    system_data.history.temperature_history[system_data.history.hour_index] = system_data.temperature;
    system_data.history.humidity_history[system_data.history.hour_index] = system_data.humidity;
    system_data.history.light_history[system_data.history.hour_index] = system_data.light;
    system_data.history.hour_index = (system_data.history.hour_index + 1) % 24;
    last_record = millis();
  }
  
  // 更新趋势和生产指标
  calculateGrowthTrend();
  calculateProductionMetrics();
  
  // 检查警报
  checkAlertConditions();
  
  Serial.print("🤖 更新AI状态: ");
  Serial.print(system_data.ai_prediction ? "GOOD" : "BAD");
  Serial.print(", 置信度: ");
  Serial.print(system_data.ai_confidence * 100, 1);
  Serial.print("%, 健康分: ");
  Serial.println(system_data.health_score, 1);
}

/* 更新环境单项评价 */
void updateEnvironmentEvaluation() {
  // 温度评价
  if (system_data.temperature >= 22 && system_data.temperature <= 26) {
    system_data.temp_eval = "理想";
  } else if (system_data.temperature >= 20 && system_data.temperature < 22) {
    system_data.temp_eval = "偏低";
  } else if (system_data.temperature > 26 && system_data.temperature <= 28) {
    system_data.temp_eval = "偏高";
  } else if (system_data.temperature < 20) {
    system_data.temp_eval = "过低";
  } else {
    system_data.temp_eval = "过高";
  }
  
  // 湿度评价
  if (system_data.humidity >= 50 && system_data.humidity <= 65) {
    system_data.humi_eval = "理想";
  } else if (system_data.humidity >= 40 && system_data.humidity < 50) {
    system_data.humi_eval = "偏低";
  } else if (system_data.humidity > 65 && system_data.humidity <= 70) {
    system_data.humi_eval = "偏高";
  } else if (system_data.humidity < 40) {
    system_data.humi_eval = "过低";
  } else {
    system_data.humi_eval = "过高";
  }
  
  // 光照评价（按照你的新标准）
  if (system_data.light >= 30 && system_data.light <= 50) {
    system_data.light_eval = "理想";
  } else if (system_data.light >= 20 && system_data.light < 30) {
    system_data.light_eval = "偏暗";
  } else if (system_data.light > 50 && system_data.light <= 70) {
    system_data.light_eval = "偏亮";
  } else if (system_data.light < 20) {
    system_data.light_eval = "太暗";
  } else {
    system_data.light_eval = "太亮";
  }
  
  // 空气质量评价
  if (system_data.air_quality <= 30) {
    system_data.air_eval = "优秀";
  } else if (system_data.air_quality <= 50) {
    system_data.air_eval = "良好";
  } else if (system_data.air_quality <= 70) {
    system_data.air_eval = "中等";
  } else {
    system_data.air_eval = "较差";
  }
}


/* 处理STM32数据 */
void processSTM32Data(String data) {
  if (data.startsWith("{")) {
    StaticJsonDocument<512> doc;
    DeserializationError error = deserializeJson(doc, data);
    
    if (!error) {
      Serial.print("📡 收到STM32数据: ");
      
      // 传感器数据更新
      bool data_updated = false;
      
      if (doc.containsKey("temp")) {
        int temp_value = doc["temp"];
        if (temp_value >= 0 && temp_value <= 50) {
          system_data.temperature = temp_value;
          data_updated = true;
        }
      }
      
      if (doc.containsKey("humi")) {
        int humi_value = doc["humi"];
        if (humi_value >= 0 && humi_value <= 100) {
          system_data.humidity = humi_value;
          data_updated = true;
        }
      }
      
      if (doc.containsKey("light")) {
        int light_value = doc["light"];
        if (light_value >= 0 && light_value <= 100) {
          system_data.light = light_value;
          data_updated = true;
        }
      }
      
      if (doc.containsKey("air")) {
        int air_value = doc["air"];
        if (air_value >= 0 && air_value <= 100) {
          system_data.air_quality = air_value;
          data_updated = true;
        }
      }
      
      // AI预测数据
      if (doc.containsKey("ai_enabled")) {
        system_data.ai_enabled = doc["ai_enabled"];
      }
      
      if (doc.containsKey("ai_prediction")) {
        system_data.ai_prediction = doc["ai_prediction"];
        Serial.print("AI预测: ");
        Serial.println(system_data.ai_prediction ? "GOOD" : "BAD");
      }
      
      if (doc.containsKey("ai_confidence")) {
        system_data.ai_confidence = doc["ai_confidence"];
        Serial.print("AI置信度: ");
        Serial.println(system_data.ai_confidence);
      }
      
      // 继电器状态
      if (doc.containsKey("relay1")) {
        system_data.relay1 = doc["relay1"];
      }
      if (doc.containsKey("relay2")) {
        system_data.relay2 = doc["relay2"];
      }
      if (doc.containsKey("relay3")) {
        system_data.relay3 = doc["relay3"];
      }
      if (doc.containsKey("relay4")) {
        system_data.relay4 = doc["relay4"];
      }
      
      updateRelayStatusStrings();
      
      if (data_updated) {
        Serial.print("温度:");
        Serial.print(system_data.temperature);
        Serial.print("°C 湿度:");
        Serial.print(system_data.humidity);
        Serial.print("% 光照:");
        Serial.print(system_data.light);
        Serial.print("% 空气质量:");
        Serial.print(system_data.air_quality);
        Serial.println("%");
      }
      
      // 使用STM32的AI预测结果更新本地状态
      updateFromAIPrediction();
      
    } else {
      Serial.print("❌ JSON解析错误: ");
      Serial.println(error.c_str());
    }
  } else if (data.length() > 0) {
    if (data.length() < 50) {
      Serial.print("📡 收到串口数据: ");
      Serial.println(data);
    }
  }
}



/* Setup函数 */
void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n🏭 ESP8266 智能植物工厂 - 生产管理系统 v2.0");
  Serial.println("🤖 AI生长预测 + 趋势分析 + 生产指标监控");
  
  // 记录系统启动时间
  system_data.system_start_time = millis();
  
  // 连接WiFi
  WiFi.begin(ssid, password);
  Serial.print("连接WiFi...");
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✅ WiFi连接成功");
    Serial.print("📱 IP地址: ");
    Serial.println(WiFi.localIP());
    
    // 启动 mDNS 服务
    Serial.print("🔗 启动 mDNS 服务...");
    if (MDNS.begin("plant")) {  // 设置域名为 plant.local
      Serial.println("✅ 成功");
      Serial.println("🌐 请访问: http://plant.local");
      Serial.println("📌 或者访问IP: http://" + WiFi.localIP().toString());
      MDNS.addService("http", "tcp", 80);
    } else {
      Serial.println("❌ 失败");
    }
    
  } else {
    Serial.println("\n⚠️ WiFi连接失败，进入离线模式");
  }
  
  // 初始化NTP时间
  initNTP();
  
  // 初始化手动控制状态
  system_data.manual_relay1 = system_data.relay1;
  system_data.manual_relay2 = system_data.relay2;
  system_data.manual_relay3 = system_data.relay3;
  system_data.manual_relay4 = system_data.relay4;
  
  // 初始化历史数据
  initHistoryData();
  
  calculateProductionMetrics();  // 确保初始时计算一次
    // 设置初始值
  system_data.plant_advice = "等待STM32 AI模型初始化...";
  
  // 显示初始生产指标
  Serial.println("\n📊 初始生产指标:");
  Serial.print("  预测产量: ");
  Serial.print(system_data.metrics.predicted_yield, 1);
  Serial.println("kg/m²");
  Serial.print("  生长速率: ");
  Serial.print(system_data.history.growth_rate, 2);
  Serial.println("%/天");
  Serial.print("  最适环境小时: ");
  Serial.print(system_data.metrics.optimal_hours_count);
  Serial.println("/24");
  Serial.print("  生产力评分: ");
  Serial.print(system_data.metrics.productivity_score, 1);
  Serial.println("/100");
  Serial.print("  资源效率: ");
  Serial.print(system_data.metrics.resource_efficiency, 1);
  Serial.println("分/kWh");
  
  // 设置Web服务器路由
  server.on("/", []() {
    server.send_P(200, "text/html; charset=utf-8", MAIN_HTML);
  });
  
  server.on("/data", HTTP_GET, []() {
    StaticJsonDocument<1024> doc;
    
  // 基础数据
  doc["temperature"] = system_data.temperature;
  doc["humidity"] = system_data.humidity;
  doc["light"] = system_data.light;
  doc["air_quality"] = system_data.air_quality;
  
  // AI状态 - 现在从STM32获取
  doc["ai_enabled"] = system_data.ai_enabled;
  doc["ai_prediction"] = system_data.ai_prediction;
  doc["ai_confidence"] = system_data.ai_confidence;
  doc["health_score"] = system_data.health_score;
  doc["growth_status"] = system_data.growth_status;
  doc["plant_advice"] = system_data.plant_advice;
  
  // 环境评价
  doc["temp_eval"] = system_data.temp_eval;
  doc["humi_eval"] = system_data.humi_eval;
  doc["light_eval"] = system_data.light_eval;
  doc["air_eval"] = system_data.air_eval;
    
    // 生产指标
    doc["predicted_yield"] = system_data.metrics.predicted_yield;
    doc["growth_rate"] = system_data.history.growth_rate;
    doc["optimal_hours_count"] = system_data.metrics.optimal_hours_count;
    doc["resource_efficiency"] = system_data.metrics.resource_efficiency;
    doc["productivity_score"] = system_data.metrics.productivity_score;
    doc["daily_avg_health"] = system_data.metrics.daily_avg_health;
    
    // 趋势分析
    doc["trend_direction"] = system_data.history.trend_direction;
    doc["trend_strength"] = system_data.history.trend_strength;
    doc["trend_description"] = system_data.history.trend_description;
    doc["estimated_days_to_issue"] = system_data.history.estimated_days_to_issue;
    
    // 控制状态
    doc["control_mode"] = system_data.control_mode;
    doc["relay1"] = system_data.relay1;
    doc["relay2"] = system_data.relay2;
    doc["relay3"] = system_data.relay3;
    doc["relay4"] = system_data.relay4;
    doc["relay1_status"] = system_data.relay1_status;
    doc["relay2_status"] = system_data.relay2_status;
    doc["relay3_status"] = system_data.relay3_status;
    doc["relay4_status"] = system_data.relay4_status;
    
    // 系统状态
    doc["system_time"] = system_data.system_time;
    doc["uptime"] = (millis() - system_data.system_start_time) / 1000;
    
    // 警报信息
    doc["has_alert"] = system_data.alert.has_alert;
    doc["alert_level"] = system_data.alert.alert_level;
    doc["alert_message"] = system_data.alert.alert_message;
    doc["alert_acknowledged"] = system_data.alert.is_acknowledged;
    
    String json;
    serializeJson(doc, json);
    server.send(200, "application/json", json);
  });
  
  server.on("/control", HTTP_POST, []() {
    if (server.hasArg("plain")) {
      String body = server.arg("plain");
      StaticJsonDocument<256> doc;
      DeserializationError error = deserializeJson(doc, body);
      
      if (error) {
        server.send(400, "application/json", "{\"success\":false,\"error\":\"JSON错误\"}");
        return;
      }
      
      int relay = doc["relay"] | 0;
      int state = doc["state"] | 0;
      
      if (relay < 1 || relay > 4) {
        server.send(400, "application/json", "{\"success\":false,\"error\":\"继电器编号无效\"}");
        return;
      }
      
      if (system_data.control_mode == "manual") {
        switch(relay) {
          case 1:
            system_data.relay1 = state;
            system_data.manual_relay1 = state;
            break;
          case 2:
            system_data.relay2 = state;
            system_data.manual_relay2 = state;
            break;
          case 3:
            system_data.relay3 = state;
            system_data.manual_relay3 = state;
            break;
          case 4:
            system_data.relay4 = state;
            system_data.manual_relay4 = state;
            break;
        }
        
        updateRelayStatusStrings();
        
        StaticJsonDocument<256> cmdDoc;
        cmdDoc["cmd"] = "manual_control";
        cmdDoc["relay"] = relay;
        cmdDoc["state"] = state;
        sendToSTM32(cmdDoc);
        
        Serial.print("🔧 手动控制: 继电器");
        Serial.print(relay);
        Serial.print(" -> ");
        Serial.println(state ? "ON" : "OFF");
        
        server.send(200, "application/json", 
                    "{\"success\":true,\"message\":\"控制命令已发送\"}");
      } else {
        server.send(400, "application/json", 
                    "{\"success\":false,\"error\":\"当前不是手动模式\"}");
      }
    }
  });
  
  server.on("/mode", HTTP_POST, []() {
    if (server.hasArg("plain")) {
      String body = server.arg("plain");
      StaticJsonDocument<256> doc;
      DeserializationError error = deserializeJson(doc, body);
      
      if (error) {
        server.send(400, "application/json", "{\"success\":false,\"error\":\"JSON错误\"}");
        return;
      }
      
      String mode = doc["mode"] | "auto";
      
      if (mode != "auto" && mode != "manual" && mode != "hybrid") {
        server.send(400, "application/json", "{\"success\":false,\"error\":\"模式无效\"}");
        return;
      }
      
      system_data.control_mode = mode;
      
      if (mode == "manual") {
        system_data.relay1 = system_data.manual_relay1;
        system_data.relay2 = system_data.manual_relay2;
        system_data.relay3 = system_data.manual_relay3;
        system_data.relay4 = system_data.manual_relay4;
        Serial.println("🔄 切换到手动模式");
      } else if (mode == "auto") {
        Serial.println("🔄 切换到自动模式");
      } else if (mode == "hybrid") {
        Serial.println("🔄 切换到混合模式");
      }
      
      updateRelayStatusStrings();
      
      StaticJsonDocument<256> cmdDoc;
      cmdDoc["cmd"] = "mode";
      cmdDoc["mode"] = mode;
      sendToSTM32(cmdDoc);
      
      server.send(200, "application/json", 
                  "{\"success\":true,\"mode\":\"" + mode + "\"}");
    }
  });
  
  server.on("/acknowledge", HTTP_POST, []() {
    system_data.alert.is_acknowledged = true;
    server.send(200, "application/json", "{\"success\":true}");
  });
  
  server.begin();
  Serial.println("✅ Web服务器启动完成");
  Serial.println("🤖 生产级AI模型初始化完成");
  Serial.println("📡 等待STM32数据...");
}

/* Loop函数 */
void loop() {
  server.handleClient();
  MDNS.update();  // 添加这行，处理 mDNS 请求
  // 处理串口数据
  if (Serial.available()) {
    String data = Serial.readStringUntil('\n');
    data.trim();
    if (data.length() > 0) {
      processSTM32Data(data);
    }
  }
  
  // 更新系统时间
  static unsigned long last_time_update = 0;
  if (millis() - last_time_update > 60000) {
    updateSystemTime();
    last_time_update = millis();
  }
  
  // 每30秒自动更新趋势和指标（即使没有新数据）
  static unsigned long lastAIPrediction = 0;
  if (millis() - lastAIPrediction > 30000) {
    if (system_data.ai_enabled) {
      calculateGrowthTrend();
      calculateProductionMetrics();
      checkAlertConditions();
    }
    lastAIPrediction = millis();
  }
  
  // 每30秒检查自动控制
  static unsigned long lastAutoControl = 0;
  if (millis() - lastAutoControl > 30000) {
    if (system_data.control_mode == "auto" || system_data.control_mode == "hybrid") {
      makeAutoControlDecision();
    }
    lastAutoControl = millis();
  }
}
