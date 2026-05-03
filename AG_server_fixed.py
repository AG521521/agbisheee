# ===== 修复版本 - 移除重复的upload函数 =====

from flask import Flask, request, jsonify
import joblib
import pandas as pd
import traceback
from datetime import datetime
import numpy as np

app = Flask(__name__)

# ===== 加载模型 =====
model = joblib.load("growth_model.pkl")

# ===== 定义特征 =====
numeric_features = [
    "Temperature", "Rainfall", "pH", "Light_Hours", "Light_Intensity",
    "Rh", "Nitrogen", "Phosphorus", "Potassium", 
    "N_Ratio", "P_Ratio", "K_Ratio"
]

categorical_features = ["Fertility", "Photoperiod", "Category_pH", "Soil_Type", "Season"]

FEATURES = numeric_features + categorical_features

print("✅ 模型加载成功")
print(f"特征总数: {len(FEATURES)}")

# ===== 全局变量 =====
latest_result = None
history_data = []
MAX_HISTORY = 1000
API_KEY = "default-api-key"

# ===== 辅助函数 =====
def convert_photoperiod(light_hours):
    """根据光照小时数转换为 Photoperiod 字符串"""
    if light_hours < 10:
        return "Short Day Period"
    elif light_hours > 14:
        return "Long Day Period"
    else:
        return "Medium Day Period"

def predict_yield(growth_status, confidence):
    """根据生长状态预测产量范围"""
    yield_ranges = {
        "优秀": {"min": 22.0, "max": 30.0, "unit": "吨/公顷"},
        "良好": {"min": 18.0, "max": 22.0, "unit": "吨/公顷"},
        "较差": {"min": 10.0, "max": 18.0, "unit": "吨/公顷"}
    }
    
    if growth_status in yield_ranges:
        base_range = yield_ranges[growth_status]
        # 根据置信度调整范围
        range_size = base_range["max"] - base_range["min"]
        if confidence > 0.7:
            # 高置信度：范围较小
            adjusted_min = base_range["min"] + range_size * 0.3
            adjusted_max = base_range["max"] - range_size * 0.3
        elif confidence > 0.4:
            # 中等置信度：范围适中
            adjusted_min = base_range["min"] + range_size * 0.2
            adjusted_max = base_range["max"] - range_size * 0.2
        else:
            # 低置信度：范围较大
            adjusted_min = base_range["min"]
            adjusted_max = base_range["max"]
        
        return {
            "range": f"{adjusted_min:.1f} - {adjusted_max:.1f}",
            "min": round(adjusted_min, 1),
            "max": round(adjusted_max, 1),
            "unit": base_range["unit"],
            "confidence_impact": "高" if confidence > 0.7 else ("中" if confidence > 0.4 else "低")
        }
    else:
        return {
            "range": "15.0 - 25.0",
            "min": 15.0,
            "max": 25.0,
            "unit": "吨/公顷",
            "confidence_impact": "未知"
        }

def get_growth_suggestions(data, growth_status, confidence):
    """根据当前数据和预测结果提供针对性的生长建议"""
    suggestions = []
    
    # 如果是良好或优秀状态，不需要提建议
    if growth_status in ["良好", "优秀"]:
        suggestions.append({
            "category": "综合",
            "issue": "生长状态良好",
            "suggestion": "继续保持当前管理措施，定期监测即可",
            "priority": "低",
            "icon": "✅"
        })
        return suggestions
    
    # 如果是较差状态，分析具体原因并提供针对性建议
    if growth_status == "较差":
        # 分析各指标问题
        issues = []
        
        # 温度分析
        temp = float(data.get('Temperature', 0))
        if temp < 15:
            issues.append(("温度过低", temp, "建议升温至18-25°C"))
        elif temp > 30:
            issues.append(("温度过高", temp, "建议降温至25°C左右"))
        
        # 光照分析
        light_hours = float(data.get('Light_Hours', 0))
        light_intensity = float(data.get('Light_Intensity', 0))
        
        if light_hours < 8:
            issues.append(("光照时长不足", f"{light_hours}小时", "建议增加光照至8-12小时/天"))
        
        if light_intensity < 20000:
            issues.append(("光照强度不足", f"{light_intensity}lux", "建议增加光照强度至30000-50000lux"))
        
        # pH分析
        ph = float(data.get('pH', 7))
        if ph < 6.0:
            issues.append(("土壤偏酸", f"pH={ph}", "建议施用石灰调节pH至6.5-7.0"))
        elif ph > 7.5:
            issues.append(("土壤偏碱", f"pH={ph}", "建议施用硫磺或有机肥调节pH"))
        
        # 营养分析
        nitrogen = float(data.get('Nitrogen', 0))
        phosphorus = float(data.get('Phosphorus', 0))
        potassium = float(data.get('Potassium', 0))
        
        if nitrogen < 15:
            issues.append(("氮含量偏低", f"{nitrogen}mg/kg", "建议追施氮肥，如尿素"))
        
        if phosphorus < 10:
            issues.append(("磷含量偏低", f"{phosphorus}mg/kg", "建议施用磷肥，如过磷酸钙"))
        
        if potassium < 12:
            issues.append(("钾含量偏低", f"{potassium}mg/kg", "建议补充钾肥，如硫酸钾"))
        
        # 水分分析
        rainfall = float(data.get('Rainfall', 0))
        humidity = float(data.get('Rh', 0))
        
        if rainfall > 800:
            issues.append(("降雨量过大", f"{rainfall}mm", "注意排水防涝"))
        elif rainfall < 300:
            issues.append(("降雨量不足", f"{rainfall}mm", "需要适当灌溉"))
        
        if humidity < 40:
            issues.append(("湿度过低", f"{humidity}%", "建议增加空气湿度"))
        elif humidity > 90:
            issues.append(("湿度过高", f"{humidity}%", "注意通风除湿"))
        
        # 根据置信度调整建议优先级
        if confidence < 0.5:
            issues.append(("数据质量警告", f"置信度仅{confidence:.1%}", "建议检查传感器准确性"))
        
        # 将问题转化为建议
        for issue, value, suggestion in issues:
            # 根据问题严重性设置优先级
            if "严重" in issue or "警告" in issue:
                priority = "高"
                icon = "🔴"
            elif "不足" in issue or "过低" in issue or "过高" in issue:
                priority = "中"
                icon = "🟡"
            else:
                priority = "低"
                icon = "🟢"
            
            suggestions.append({
                "category": "生长改善",
                "issue": f"{issue}: {value}",
                "suggestion": suggestion,
                "priority": priority,
                "icon": icon
            })
    
    # 如果没有检测到具体问题，提供一般性建议
    if not suggestions and growth_status == "较差":
        suggestions.append({
            "category": "综合",
            "issue": "生长状态较差但原因不明",
            "suggestion": "建议全面检查环境因素和植株健康状况",
            "priority": "高",
            "icon": "🔴"
        })
    
    # 按优先级排序（高 > 中 > 低）
    priority_order = {"高": 1, "中": 2, "低": 3}
    suggestions.sort(key=lambda x: priority_order[x["priority"]])
    
    return suggestions

def get_risk_assessment(data, growth_status, confidence):
    """风险评估"""
    risks = []
    
    # 极端温度风险
    temp = float(data.get('Temperature', 0))
    if temp < 5 or temp > 35:
        risks.append({
            "type": "极端温度",
            "level": "高",
            "description": f"温度{temp}°C超出植物适宜范围",
            "impact": "可能导致生长停滞或死亡"
        })
    
    # 光照不足风险
    light_hours = float(data.get('Light_Hours', 0))
    if light_hours < 4:
        risks.append({
            "type": "光照严重不足",
            "level": "高",
            "description": f"每日光照仅{light_hours}小时",
            "impact": "光合作用严重不足，影响生长"
        })
    
    # pH极端风险
    ph = float(data.get('pH', 7))
    if ph < 5.0 or ph > 8.5:
        risks.append({
            "type": "土壤酸碱度异常",
            "level": "中",
            "description": f"pH值{ph}超出安全范围",
            "impact": "影响养分吸收"
        })
    
    # 低置信度风险
    if confidence < 0.4:
        risks.append({
            "type": "预测不确定性高",
            "level": "中",
            "description": f"模型置信度仅{confidence:.1%}",
            "impact": "预测结果可能不准确，建议检查传感器数据"
        })
    
    return risks

# ===== API密钥验证装饰器 =====
def require_api_key(f):
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if api_key and api_key == API_KEY:
            return f(*args, **kwargs)
        return jsonify({"error": "无效的API密钥"}), 401
    decorated.__name__ = f.__name__
    return decorated

# ===== 数据验证函数 =====
def validate_sensor_data(data):
    """验证传感器数据的有效性"""
    try:
        # ESP8266实际发送的特征（不包含Photoperiod）
        required_features = [
            "Temperature", "Rainfall", "pH", "Light_Hours", "Light_Intensity",
            "Rh", "Nitrogen", "Phosphorus", "Potassium",
            "N_Ratio", "P_Ratio", "K_Ratio",
            "Fertility", "Category_pH", "Soil_Type", "Season"
        ]
        
        # 检查缺失特征
        missing_features = []
        for feature in required_features:
            if feature not in data:
                missing_features.append(feature)
        
        if missing_features:
            return False, f"缺少特征: {missing_features}"
        
        # 验证数值范围
        for feature in required_features:
            try:
                if feature in ['Fertility', 'Category_pH', 'Soil_Type', 'Season']:
                    val = int(float(data[feature]))
                else:
                    val = float(data[feature])
            except (ValueError, TypeError):
                return False, f"{feature}值格式错误"
        
        return True, "数据有效"
        
    except Exception as e:
        return False, f"验证异常: {str(e)}"

# ===== ESP8266 上传接口 =====
@app.route("/upload", methods=["POST"])
@require_api_key
def upload():
    global latest_result, history_data
    
    try:
        print("\n" + "="*60)
        print("收到ESP8266上传请求")
        print("="*60)
        
        data = request.get_json()
        if not data:
            print("错误：无JSON数据")
            return jsonify({"error": "无JSON数据"}), 400
        
        print("收到的JSON数据:")
        for key, value in data.items():
            print(f"  {key}: {value}")
        
        # 数据验证
        is_valid, message = validate_sensor_data(data)
        print(f"数据验证结果: {is_valid} - {message}")
        
        if not is_valid:
            return jsonify({"error": message}), 400
        
        # 处理数据 - 修复特征数量问题
        print("\n处理数据...")
        
        # 方法1：使用字典创建DataFrame，避免特征数量不匹配
        feature_dict = {}
        
        # 处理数值特征
        for feature in numeric_features:
            if feature == "Photoperiod":
                # 计算Photoperiod
                light_hours = float(data.get('Light_Hours', 0))
                feature_dict[feature] = convert_photoperiod(light_hours)
            else:
                value = data.get(feature, 0)
                try:
                    feature_dict[feature] = float(value)
                except:
                    feature_dict[feature] = 0.0
        
        # 处理分类特征
        for feature in categorical_features:
            if feature != "Photoperiod":  # Photoperiod已经在数值特征中处理了
                value = data.get(feature, 1)
                try:
                    feature_dict[feature] = str(int(float(value)))
                except:
                    feature_dict[feature] = "1"
        
        # 创建DataFrame
        df = pd.DataFrame([feature_dict])
        
        # 确保所有特征都存在（按顺序）
        for feature in FEATURES:
            if feature not in df.columns:
                if feature in numeric_features:
                    df[feature] = 0.0
                else:
                    df[feature] = "1"
        
        # 按正确的顺序排列特征
        df = df[FEATURES]
        
        print(f"DataFrame形状: {df.shape}")
        print("DataFrame列顺序:")
        for i, col in enumerate(df.columns, 1):
            print(f"  {i:2d}. {col}: {df.iloc[0][col]}")
        
        # 进行预测
        print("\n开始预测...")
        result = model.predict(df)[0]
        
        # 获取概率
        if hasattr(model, 'predict_proba'):
            proba = model.predict_proba(df)
            confidence = round(float(proba.max()), 3)
        else:
            confidence = 1.0
        
        print(f"预测结果: {result}, 置信度: {confidence}")
        
        # 生成额外信息
        yield_prediction = predict_yield(result, confidence)
        suggestions = get_growth_suggestions(data, result, confidence)
        risks = get_risk_assessment(data, result, confidence)
        
        # 数据质量评估
        data_quality_score = min(1.0, confidence * 1.2)
        
        # 保存结果
        timestamp = datetime.now().isoformat()
        result_record = {
            "timestamp": timestamp,
            "growth_status": str(result),
            "confidence": confidence,
            "confidence_level": "高" if confidence > 0.7 else ("中" if confidence > 0.5 else "低"),
            "yield": yield_prediction,
            "suggestions": suggestions,
            "risks": risks,
            "data_quality": {
                "score": round(data_quality_score, 2),
                "assessment": "优秀" if data_quality_score > 0.8 else ("良好" if data_quality_score > 0.6 else "需要改善")
            },
            "sensor_data": data,
            "prediction_time": timestamp
        }
        
        latest_result = result_record
        history_data.append(result_record)
        if len(history_data) > MAX_HISTORY:
            history_data.pop(0)
        
        print(f"\n✅ 预测成功！")
        print(f"   生长状态: {result}")
        print(f"   置信度: {confidence:.1%}")
        print(f"   产量预测: {yield_prediction.get('range', '未知')}")
        print(f"   提供建议: {len(suggestions)}条")
        
        if suggestions:
            for i, suggestion in enumerate(suggestions, 1):
                print(f"   建议{i}: {suggestion.get('category', '未知')} - {suggestion.get('issue', '')}")
        
        print("="*60)
        
        return jsonify({
            "status": "success",
            "prediction": str(result),
            "confidence": confidence,
            "yield": yield_prediction,
            "suggestions": suggestions,
            "risks": risks,
            "data_quality": result_record["data_quality"],
            "timestamp": timestamp
        })
        
    except Exception as e:
        print(f"\n❌ 服务器发生错误:")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {str(e)}")
        print("错误堆栈:")
        traceback.print_exc()
        
        return jsonify({
            "error": "内部服务器错误",
            "details": str(e),
            "type": type(e).__name__
        }), 500

# ===== 移动端界面 =====
@app.route("/mobile")
def mobile():
    return '''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<meta name="theme-color" content="#2ecc71">
<title>植株监测系统</title>
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; }
    .app-container { max-width: 100%; padding: 15px; }
    .app-header { background: #2ecc71; color: white; border-radius: 15px; padding: 20px; margin-bottom: 15px; text-align: center; }
    .app-title { font-size: 1.8em; font-weight: bold; margin-bottom: 5px; }
    .app-subtitle { opacity: 0.9; font-size: 0.9em; }
    .status-card { background: white; border-radius: 15px; padding: 20px; margin-bottom: 15px; }
    .card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px; }
    .card-title { font-size: 1.1em; font-weight: 600; color: #2c3e50; }
    .status-badge { padding: 6px 15px; border-radius: 20px; font-size: 0.9em; font-weight: 600; }
    .badge-excellent { background: #2ecc71; color: white; }
    .badge-good { background: #f1c40f; color: white; }
    .badge-poor { background: #e74c3c; color: white; }
    .data-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 15px; }
    .data-item { background: #f8f9fa; padding: 15px; border-radius: 10px; text-align: center; }
    .data-label { font-size: 0.85em; color: #7f8c8d; margin-bottom: 8px; }
    .data-value { font-size: 1.3em; font-weight: bold; color: #2c3e50; }
    .confidence-meter { height: 8px; background: #ecf0f1; border-radius: 4px; margin: 10px 0; overflow: hidden; }
    .confidence-fill { height: 100%; border-radius: 4px; }
    .suggestion-list { margin-top: 15px; }
    .suggestion-item { background: #f8f9fa; padding: 15px; border-radius: 12px; margin-bottom: 12px; border-left: 4px solid #3498db; }
    .priority-tag { display: inline-block; padding: 4px 10px; border-radius: 15px; font-size: 0.8em; font-weight: 600; margin-right: 10px; }
    .priority-high { background: #f8d7da; color: #721c24; }
    .priority-medium { background: #fff3cd; color: #856404; }
    .priority-low { background: #d4edda; color: #155724; }
    .refresh-btn { position: fixed; bottom: 20px; right: 20px; width: 55px; height: 55px; background: #3498db; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.4em; border: none; cursor: pointer; }
    .loading { text-align: center; padding: 40px 20px; color: #7f8c8d; }
    .loading-spinner { width: 35px; height: 35px; border: 3px solid #f3f3f3; border-top: 3px solid #3498db; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 15px; }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="app-container">
    <div class="app-header">
        <div class="app-title">植株监测系统</div>
        <div class="app-subtitle" id="lastUpdate">正在连接设备...</div>
    </div>
    
    <div class="status-card" id="mainStatus">
        <div class="card-header">
            <div class="card-title">📊 生长状态</div>
            <div id="statusBadge" class="status-badge">连接中</div>
        </div>
        <div id="statusContent" class="loading">
            <div class="loading-spinner"></div>
            <div>正在获取数据...</div>
        </div>
    </div>
    
    <div class="status-card" id="suggestionsCard" style="display: none;">
        <div class="card-header">
            <div class="card-title">💡 生长建议</div>
        </div>
        <div id="suggestionsContent"></div>
    </div>
    
    <div class="status-card" id="environmentCard" style="display: none;">
        <div class="card-header">
            <div class="card-title">🌡️ 环境数据</div>
        </div>
        <div id="environmentContent"></div>
    </div>
</div>

<button class="refresh-btn" id="refreshBtn" onclick="updateData()">↻</button>

<script>
let currentData = null;

async function updateData() {
    try {
        const refreshBtn = document.getElementById('refreshBtn');
        refreshBtn.innerHTML = '⏳';
        
        const response = await fetch('/data');
        const data = await response.json();
        
        if (data.status === "waiting") {
            document.getElementById('lastUpdate').textContent = '等待设备连接...';
            document.getElementById('statusContent').innerHTML = '<div class="loading"><div class="loading-spinner"></div><div>等待设备连接</div></div>';
            document.getElementById('suggestionsCard').style.display = 'none';
            document.getElementById('environmentCard').style.display = 'none';
            refreshBtn.innerHTML = '↻';
            return;
        }
        
        currentData = data;
        const updateTime = new Date(data.timestamp || new Date()).toLocaleTimeString();
        document.getElementById('lastUpdate').textContent = '更新: ' + updateTime;
        
        // 更新主状态
        const statusBadge = document.getElementById('statusBadge');
        const statusContent = document.getElementById('statusContent');
        const growthStatus = data.growth_status || '未知';
        const confidence = data.confidence || 0;
        const confidencePercent = Math.round(confidence * 100);
        
        let badgeClass = 'badge-poor';
        if (growthStatus.includes('优秀')) badgeClass = 'badge-excellent';
        else if (growthStatus.includes('良好')) badgeClass = 'badge-good';
        
        statusBadge.className = 'status-badge ' + badgeClass;
        statusBadge.textContent = growthStatus;
        
        statusContent.innerHTML = '<div style="text-align: center; margin-bottom: 15px;">' +
            '<div style="font-size: 2.5em; margin-bottom: 10px;">' + (growthStatus.includes('优秀') ? '🌟' : (growthStatus.includes('良好') ? '✅' : '⚠️')) + '</div>' +
            '<div style="font-size: 1.2em; font-weight: 600; color: #2c3e50;">' + growthStatus + '</div>' +
            '</div>' +
            '<div class="data-grid">' +
            '<div class="data-item">' +
            '<div class="data-label">模型置信度</div>' +
            '<div class="data-value">' + confidencePercent + '<span style="font-size: 0.8em;">%</span></div>' +
            '<div class="confidence-meter">' +
            '<div class="confidence-fill" style="width: ' + confidencePercent + '%; background: ' + (confidence > 0.7 ? '#2ecc71' : (confidence > 0.5 ? '#f1c40f' : '#e74c3c')) + ';"></div>' +
            '</div>' +
            '</div>' +
            '<div class="data-item">' +
            '<div class="data-label">数据质量</div>' +
            '<div class="data-value">' + (data.data_quality?.score || 0) + '<span style="font-size: 0.8em;">/1.0</span></div>' +
            '<div style="font-size: 0.75em; color: #7f8c8d; margin-top: 5px;">' + (data.data_quality?.assessment || '未知') + '</div>' +
            '</div>' +
            '</div>';
        
        // 更新建议
        if (data.suggestions && data.suggestions.length > 0) {
            let suggestionsHTML = '<div class="suggestion-list">';
            data.suggestions.forEach(suggestion => {
                const priorityClass = 'priority-' + (suggestion.priority || 'medium');
                suggestionsHTML += '<div class="suggestion-item">' +
                    '<div><span class="priority-tag ' + priorityClass + '">' + 
                    (suggestion.priority === '高' ? '重要' : (suggestion.priority === '中' ? '中等' : '建议')) + 
                    '</span><strong>' + suggestion.category + ':</strong> ' + suggestion.issue + '</div>' +
                    '<div style="margin-top: 8px;">💡 ' + suggestion.suggestion + '</div>' +
                    '</div>';
            });
            suggestionsHTML += '</div>';
            document.getElementById('suggestionsContent').innerHTML = suggestionsHTML;
            document.getElementById('suggestionsCard').style.display = 'block';
        } else {
            document.getElementById('suggestionsCard').style.display = 'block';
            document.getElementById('suggestionsContent').innerHTML = '<div style="text-align: center; padding: 20px; color: #7f8c8d;">🎉 生长状态良好，无需特别调整！</div>';
        }
        
        // 更新环境数据
        if (data.sensor_data) {
            const sensorData = data.sensor_data;
            let envHTML = '<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">';
            const sensors = [
                { key: 'Temperature', label: '温度', unit: '°C' },
                { key: 'Rh', label: '湿度', unit: '%' },
                { key: 'Light_Hours', label: '光照时长', unit: 'h' },
                { key: 'Light_Intensity', label: '光照强度', unit: 'lux' },
                { key: 'pH', label: 'pH值', unit: '' },
                { key: 'Rainfall', label: '降雨量', unit: 'mm' }
            ];
            sensors.forEach(sensor => {
                if (sensorData[sensor.key] !== undefined) {
                    const value = parseFloat(sensorData[sensor.key]).toFixed(sensor.key === 'Light_Intensity' ? 0 : 1);
                    envHTML += '<div style="background: #f8f9fa; padding: 12px; border-radius: 10px; text-align: center;">' +
                        '<div style="font-size: 1.2em; font-weight: bold; color: #2c3e50;">' + value + '</div>' +
                        '<div style="font-size: 0.8em; color: #7f8c8d; margin-top: 5px;">' + sensor.label + (sensor.unit ? ' (' + sensor.unit + ')' : '') + '</div>' +
                        '</div>';
                }
            });
            envHTML += '</div>';
            document.getElementById('environmentContent').innerHTML = envHTML;
            document.getElementById('environmentCard').style.display = 'block';
        }
        
        refreshBtn.innerHTML = '↻';
        
    } catch (error) {
        console.error('获取数据失败:', error);
        document.getElementById('lastUpdate').textContent = '连接失败';
        document.getElementById('statusContent').innerHTML = '<div class="loading"><div style="font-size: 2em;">❌</div><div>无法连接到服务器</div></div>';
        document.getElementById('refreshBtn').innerHTML = '↻';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    updateData();
    setInterval(updateData, 5000);
});
</script>
</body>
</html>'''

# ===== 其他API端点 =====
@app.route("/data")
def data():
    if latest_result is None:
        return jsonify({"status": "waiting"})
    return jsonify(latest_result)

@app.route("/history")
def history():
    limit = min(int(request.args.get('limit', 10)), 100)
    recent = history_data[-limit:] if len(history_data) >= limit else history_data
    return jsonify({
        "count": len(recent),
        "data": recent
    })

@app.route("/stats")
def stats():
    if not history_data:
        return jsonify({"message": "暂无历史数据"})
    
    status_counts = {}
    total_confidence = 0
    
    for record in history_data:
        status = record['growth_status']
        status_counts[status] = status_counts.get(status, 0) + 1
        total_confidence += record.get('confidence', 0)
    
    avg_confidence = total_confidence / len(history_data) if history_data else 0
    
    return jsonify({
        "total_records": len(history_data),
        "average_confidence": round(avg_confidence, 3),
        "status_distribution": status_counts,
        "latest_timestamp": history_data[-1]['timestamp'] if history_data else None
    })

@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "model_loaded": model is not None,
        "features_count": len(FEATURES),
        "latest_data": latest_result is not None,
        "history_size": len(history_data),
        "server_time": datetime.now().isoformat()
    })

@app.route("/")
def index():
    return jsonify({
        "name": "植株监测系统API",
        "version": "1.0",
        "endpoints": {
            "/": "API信息",
            "/upload": "上传传感器数据(POST)",
            "/data": "获取最新数据",
            "/history": "获取历史数据",
            "/stats": "统计信息",
            "/health": "健康检查",
            "/mobile": "移动端界面"
        }
    })

# ===== 启动服务器 =====
if __name__ == "__main__":
    print("="*60)
    print("🌱 植株监测系统 Flask服务器")
    print(f"模型特征数量: {len(FEATURES)}")
    print("\n数值特征 (12个):")
    for i, feat in enumerate(numeric_features, 1):
        print(f"  {i:2d}. {feat}")
    
    print("\n分类特征 (5个):")
    for i, feat in enumerate(categorical_features, 1):
        print(f"  {i:2d}. {feat}")
    
    print("\n总特征列表 (按顺序):")
    for i, feat in enumerate(FEATURES, 1):
        print(f"  {i:2d}. {feat}")
    print("="*60)
    print("服务器启动中...")
    print("访问地址: http://localhost:5000")
    print("移动端界面: http://localhost:5000/mobile")
    print("="*60)
    
    app.run(host="0.0.0.0", port=5000, debug=True)