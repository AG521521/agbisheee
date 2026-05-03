```markdown
# 多传感器环境数据采集与上传终端

## 📖 项目简介
基于STM32+ESP8266双核架构的智能植物工厂环境监测系统。STM32端负责多传感器数据采集和轻量级AI生长预测，ESP8266端提供Web服务器，支持手机浏览器远程查看环境数据和设备控制。

## ✨ 功能特性
- 多传感器数据采集：温湿度（DHT11）、光照（光敏电阻）、空气质量（MQ-135）
- 边缘AI推理：7-8-4-1全连接神经网络，STM32本地运行，134次MAC运算
- JSON串口通信：STM32与ESP8266通过UART交换传感器数据和控制指令
- Web远程监控：手机浏览器访问，支持传感器看板、健康评分、趋势分析
- 三种控制模式：自动（AI驱动）/ 手动（Web控制）/ 混合模式

## 🛠 技术栈
- 主控：STM32G071RB（Cortex-M0+, 64MHz）
- WiFi：ESP8266-12F（Arduino框架）
- AI部署：STM32Cube.AI（ONNX模型转换）
- 传感器：DHT11、光敏电阻、MQ-135
- 通信：UART 115200bps，JSON数据格式
- 前端：HTML/CSS/JavaScript，Ajax轮询，响应式布局

## 🚀 快速开始

### 硬件要求
- STM32G071RB开发板
- ESP8266-12F模块
- DHT11温湿度传感器
- 光敏电阻模块
- MQ-135空气质量传感器
- 4路继电器模块

### STM32端（CubeIDE工程）
1. 用STM32CubeIDE打开 `stm32_project/` 目录
2. CubeMX中导入 `plant_growth_model_prob.onnx` 到X-CUBE-AI
3. 编译烧录到STM32G071RB

### ESP8266端（Arduino工程）
1. 用Arduino IDE打开 `esp8266/` 目录下的 `.ino` 文件
2. 安装依赖库：ArduinoJson、ESP8266WiFi、ESP8266WebServer
3. 修改WiFi名称和密码
4. 编译烧录到ESP8266-12F

### 使用
1. STM32和ESP8266的UART交叉连接（TX→RX, RX→TX）
2. 上电后ESP8266创建WiFi热点或连入路由器
3. 手机连同一WiFi，浏览器访问ESP8266的IP地址
4. 页面每2秒自动刷新，可查看传感器数据、AI预测结果、切换控制模式

## 📁 项目结构
```
├── stm32_project/         # STM32 CubeIDE工程
│   ├── Core/              # 主程序、传感器驱动、AI模型代码
│   └── plant_growth_model_prob.onnx  # 神经网络模型
├── esp8266/               # ESP8266 Arduino工程
│   └── main.ino           # Web服务器、数据处理、前端页面
├── model/                 # 模型训练（Python/TensorFlow）
└── docs/                  # 论文相关文档
```

## 📝 许可证
本项目采用 MIT 许可证
```

---
