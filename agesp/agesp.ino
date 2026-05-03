#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <ArduinoJson.h>

// ===== WiFi配置 =====
const char* ssid = "iPhone";
const char* password = "xnn1314279@WIFI";
const char* serverUrl = "http://10.87.12.57:5000/upload";

// ===== 全局变量 =====
String apiKey = "default-api-key";
unsigned long lastSendTime = 0;
unsigned long sendInterval = 30000;  // 初始30秒
int retryCount = 0;
const int maxRetries = 3;

// ===== 传感器数据结构 =====
struct SensorData {
  // 基础传感器数据
  float temperature = 22.5;      // Temperature (°C)
  float rainfall = 700.0;        // Rainfall (mm)
  float pH = 6.5;                // pH
  float lightHours = 12.0;       // Light_Hours (小时)
  float lightIntensity = 45000.0; // Light_Intensity (lux)
  float humidity = 65.0;         // Rh (%)
  float nitrogen = 15.0;         // Nitrogen (mg/kg)
  float phosphorus = 10.0;       // Phosphorus (mg/kg)
  float potassium = 12.0;        // Potassium (mg/kg)
  
  // 衍生特征
  float K_Ratio = 0.0;           // 钾比例
  float P_Ratio = 0.0;           // 磷比例
  float N_Ratio = 0.0;           // 氮比例
  int Fertility = 2;             // 肥力等级 (1-5)
  int Soil_Type = 3;             // 土壤类型 (1-4)
  int Season = 1;                // 季节 (1=春, 2=夏, 3=秋, 4=冬)
  int Category_pH = 2;           // pH类别 (1=酸性, 2=中性, 3=碱性)
  
  bool dataValid = true;
  unsigned long timestamp = 0;
};

SensorData sensorData;

// ===== WiFi连接函数 =====
void connectWiFi() {
  Serial.print("\n[WiFi] 正在连接: ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] ✓ 连接成功");
    Serial.print("[WiFi] IP地址: ");
    Serial.println(WiFi.localIP());
    Serial.print("[WiFi] 信号强度: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    Serial.println("\n[WiFi] ✗ 连接失败");
  }
}

// ===== 计算衍生特征 =====
void calculateDerivedFeatures() {
  // 计算氮磷钾比例
  float totalNutrients = sensorData.nitrogen + sensorData.phosphorus + sensorData.potassium;
  
  if (totalNutrients > 0) {
    sensorData.N_Ratio = sensorData.nitrogen / totalNutrients;
    sensorData.P_Ratio = sensorData.phosphorus / totalNutrients;
    sensorData.K_Ratio = sensorData.potassium / totalNutrients;
  } else {
    sensorData.N_Ratio = 0.33;
    sensorData.P_Ratio = 0.33;
    sensorData.K_Ratio = 0.33;
  }
  
  // 根据pH值设置Category_pH
  if (sensorData.pH < 6.5) {
    sensorData.Category_pH = 1;  // 酸性
  } else if (sensorData.pH <= 7.5) {
    sensorData.Category_pH = 2;  // 中性
  } else {
    sensorData.Category_pH = 3;  // 碱性
  }
  
  // 根据氮磷钾含量设置肥力等级
  float avgNutrient = (sensorData.nitrogen + sensorData.phosphorus + sensorData.potassium) / 3.0;
  if (avgNutrient < 5) sensorData.Fertility = 1;
  else if (avgNutrient < 10) sensorData.Fertility = 2;
  else if (avgNutrient < 15) sensorData.Fertility = 3;
  else if (avgNutrient < 20) sensorData.Fertility = 4;
  else sensorData.Fertility = 5;
  
  // 模拟季节
  int month = ((millis() / 2592000000) % 12) + 1;
  if (month >= 3 && month <= 5) sensorData.Season = 1;      // 春季
  else if (month >= 6 && month <= 8) sensorData.Season = 2; // 夏季
  else if (month >= 9 && month <= 11) sensorData.Season = 3; // 秋季
  else sensorData.Season = 4;                               // 冬季
  
  // 固定土壤类型为壤土
  sensorData.Soil_Type = 3;  // 3=壤土
}

// ===== 模拟传感器数据 =====
void simulateSensorData() {
  int season = sensorData.Season;
  
  // 温度：季节变化
  switch(season) {
    case 1: // 春季 15-30°C
      sensorData.temperature = 15.0 + random(0, 151) * 0.1;
      break;
    case 2: // 夏季 25-40°C
      sensorData.temperature = 25.0 + random(0, 151) * 0.1;
      break;
    case 3: // 秋季 10-25°C
      sensorData.temperature = 10.0 + random(0, 151) * 0.1;
      break;
    default: // 冬季 0-15°C
      sensorData.temperature = 0.0 + random(0, 151) * 0.1;
  }
  
  // 光照：时间和季节
  unsigned long hours = (millis() / 3600000) % 24;
  
  if (hours > 6 && hours < 18) { // 白天
    sensorData.lightHours = 1.0; // 累积光照1小时
    
    switch(season) {
      case 2: // 夏季
        sensorData.lightIntensity = 50000.0 + random(0, 50000);
        break;
      case 1: case 3: // 春秋季
        sensorData.lightIntensity = 30000.0 + random(0, 40000);
        break;
      default: // 冬季
        sensorData.lightIntensity = 20000.0 + random(0, 30000);
    }
  } else { // 夜晚
    sensorData.lightHours = 0.0;
    sensorData.lightIntensity = 10.0 + random(0, 50);
  }
  
  // 降雨：随机变化
  static float baseRainfall = 500.0;
  if (random(0, 100) > 90) { // 10%概率下雨
    sensorData.rainfall = baseRainfall + random(0, 200);
  } else {
    sensorData.rainfall = baseRainfall - random(0, 100);
  }
  
  // 湿度：与温度负相关
  if (sensorData.temperature > 30) {
    sensorData.humidity = 40.0 + random(0, 400) * 0.1;
  } else {
    sensorData.humidity = 60.0 + random(0, 400) * 0.1;
  }
  
  // pH值：合理范围 6.0-8.0
  sensorData.pH = 6.0 + random(0, 41) * 0.05;
  
  // 氮磷钾：合理范围
  sensorData.nitrogen = 15.0 + random(0, 101) * 0.1;  // 15-25 mg/kg
  sensorData.phosphorus = 10.0 + random(0, 81) * 0.1; // 10-18 mg/kg
  sensorData.potassium = 12.0 + random(0, 91) * 0.1;  // 12-21 mg/kg
  
  // 计算衍生特征
  calculateDerivedFeatures();
  
  sensorData.dataValid = true;
  sensorData.timestamp = millis();
}

// ===== 创建JSON字符串 =====
String createJsonPayload() {
  // 使用ArduinoJson库创建JSON
  StaticJsonDocument<1024> doc;
  
  // 设置数值
  doc["Temperature"] = sensorData.temperature;
  doc["Rainfall"] = sensorData.rainfall;
  doc["pH"] = sensorData.pH;
  doc["Light_Hours"] = sensorData.lightHours;
  doc["Light_Intensity"] = sensorData.lightIntensity;
  doc["Rh"] = sensorData.humidity;
  doc["Nitrogen"] = sensorData.nitrogen;
  doc["Phosphorus"] = sensorData.phosphorus;
  doc["Potassium"] = sensorData.potassium;
  doc["N_Ratio"] = sensorData.N_Ratio;
  doc["P_Ratio"] = sensorData.P_Ratio;
  doc["K_Ratio"] = sensorData.K_Ratio;
  doc["Fertility"] = sensorData.Fertility;
  doc["Category_pH"] = sensorData.Category_pH;
  doc["Soil_Type"] = sensorData.Soil_Type;
  doc["Season"] = sensorData.Season;
  
  String json;
  serializeJson(doc, json);
  
  Serial.print("[JSON] 生成JSON数据: ");
  Serial.println(json);
  
  return json;
}

// ===== 发送数据到服务器 =====
bool sendDataToServer() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[HTTP] WiFi未连接");
    return false;
  }
  
  WiFiClient client;
  HTTPClient http;
  
  Serial.print("[HTTP] 连接到服务器: ");
  Serial.println(serverUrl);
  
  // 配置HTTP客户端
  http.setTimeout(15000); // 15秒超时
  http.setReuse(true);    // 重用连接
  
  // 开始连接
  if (!http.begin(client, serverUrl)) {
    Serial.println("[HTTP] 连接失败");
    return false;
  }
  
  // 设置HTTP头
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", apiKey);
  http.addHeader("Connection", "keep-alive");
  
  // 获取JSON数据
  String jsonPayload = createJsonPayload();
  
  Serial.print("[HTTP] 发送数据 (长度): ");
  Serial.println(jsonPayload.length());
  
  // 发送POST请求
  int httpCode = http.POST(jsonPayload);
  
  bool success = false;
  String responseStr = "";
  
  if (httpCode > 0) {
    Serial.printf("[HTTP] 响应代码: %d\n", httpCode);
    
    responseStr = http.getString();
    Serial.print("[HTTP] 服务器响应: ");
    Serial.println(responseStr);
    
    if (httpCode == 200) {
      // 解析响应
      StaticJsonDocument<512> responseDoc;
      DeserializationError error = deserializeJson(responseDoc, responseStr);
      
      if (!error) {
        String status = responseDoc["status"] | "unknown";
        if (status == "success") {
          success = true;
          Serial.println("[HTTP] ✓ 数据发送成功");
          
          // 显示建议数量
          int suggestionCount = responseDoc["suggestions"] | 0;
          if (suggestionCount > 0) {
            Serial.printf("[HTTP] 收到 %d 条生长建议\n", suggestionCount);
          }
        }
      }
    } else if (httpCode == 401) {
      Serial.println("[HTTP] ✗ API密钥错误");
    } else if (httpCode == 400) {
      Serial.println("[HTTP] ✗ 请求数据格式错误");
    }
  } else {
    Serial.print("[HTTP] ✗ 请求失败: ");
    Serial.println(http.errorToString(httpCode));
  }
  
  http.end();
  return success;
}

// ===== 显示传感器数据 =====
void displaySensorData() {
  Serial.println("\n======= 传感器数据 =======");
  Serial.println("【基础数据】");
  Serial.printf("温度: %.1f°C\n", sensorData.temperature);
  Serial.printf("湿度: %.1f%%\n", sensorData.humidity);
  Serial.printf("光照: %.0f lux (%.1f小时)\n", sensorData.lightIntensity, sensorData.lightHours);
  Serial.printf("pH: %.1f (类别:%d)\n", sensorData.pH, sensorData.Category_pH);
  Serial.printf("氮磷钾: %.1f/%.1f/%.1f mg/kg\n", sensorData.nitrogen, sensorData.phosphorus, sensorData.potassium);
  Serial.printf("降雨: %.1f mm\n", sensorData.rainfall);
  
  Serial.println("\n【衍生数据】");
  Serial.printf("氮磷钾比例: %.3f/%.3f/%.3f\n", sensorData.N_Ratio, sensorData.P_Ratio, sensorData.K_Ratio);
  Serial.printf("肥力等级: %d\n", sensorData.Fertility);
  Serial.printf("季节: %d (1=春,2=夏,3=秋,4=冬)\n", sensorData.Season);
  Serial.printf("土壤类型: %d (3=壤土)\n", sensorData.Soil_Type);
  Serial.println("==========================");
}

// ===== 显示系统状态 =====
void displaySystemStatus() {
  Serial.println("\n======= 系统状态 =======");
  Serial.printf("WiFi状态: %s\n", WiFi.status() == WL_CONNECTED ? "已连接" : "未连接");
  Serial.printf("IP地址: %s\n", WiFi.localIP().toString().c_str());
  Serial.printf("信号强度: %d dBm\n", WiFi.RSSI());
  Serial.printf("发送间隔: %lu 毫秒\n", sendInterval);
  Serial.printf("重试次数: %d/%d\n", retryCount, maxRetries);
  Serial.println("========================");
}

// ===== 设置函数 =====
void setup() {
  Serial.begin(115200);
  delay(2000);
  
  Serial.println("\n\n==================================");
  Serial.println("      植株监测系统 ESP8266");
  Serial.println("      版本: 4.0 - 优化版");
  Serial.println("==================================");
  
  // 初始化随机种子
  randomSeed(analogRead(A0));
  
  // 连接WiFi
  connectWiFi();
  
  Serial.println("\n[系统] 初始化完成");
  Serial.println("==================================\n");
  
  // 显示初始状态
  displaySystemStatus();
}

// ===== 主循环 =====
void loop() {
  unsigned long currentTime = millis();
  
  // 检查WiFi连接
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\n[WiFi] 连接断开，重新连接...");
    connectWiFi();
    delay(1000);
  }
  
  // 发送数据逻辑
  if (currentTime - lastSendTime >= sendInterval) {
    Serial.println("\n>>> 开始新一轮数据发送 <<<");
    
    // 生成数据
    simulateSensorData();
    displaySensorData();
    
    // 发送到服务器
    bool sendSuccess = sendDataToServer();
    
    if (sendSuccess) {
      retryCount = 0;
      sendInterval = 30000;  // 成功：30秒间隔
      Serial.println("[系统] 发送间隔改为30秒");
    } else {
      retryCount++;
      Serial.printf("[系统] 发送失败，重试次数: %d/%d\n", retryCount, maxRetries);
      
      if (retryCount >= maxRetries) {
        // 多次失败后重新连接WiFi
        Serial.println("[系统] 重连WiFi...");
        connectWiFi();
        retryCount = 0;
        sendInterval = 5000;  // 失败：5秒重试
        Serial.println("[系统] 发送间隔改为5秒");
      }
    }
    
    lastSendTime = currentTime;
    Serial.println(">>> 发送完成 <<<\n");
    
    // 显示系统状态
    displaySystemStatus();
  }
  
  // 短延迟减少CPU占用
  delay(100);
}
