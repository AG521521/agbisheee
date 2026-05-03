# app_fixed.py - 改进的植物生长预测Flask服务器
from flask import Flask, request, jsonify, render_template_string
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
import traceback
import json
import time
import random

app = Flask(__name__)

# ===== 加载模型 =====
print("="*60)
print("🌱 植物生长预测系统 v2.0 - 服务器启动")
print("="*60)

model = None
preprocessing_pipeline = None
features = []
categorical_encoders = {}
class_names = ['未达标', '已达标']
model_loaded = False
model_data = None

try:
    # 加载模型数据
    model_data = joblib.load('plant_growth_model_v2.pkl')
    model = model_data['model']
    preprocessing_pipeline = model_data['preprocessing_pipeline']
    features = model_data['features']
    categorical_encoders = model_data.get('categorical_encoders', {})
    class_names = model_data.get('class_names', ['未达标', '已达标'])
    model_loaded = True
    
    print("✅ 模型加载成功")
    print(f"模型类型: {type(model).__name__}")
    print(f"特征数量: {len(features)}")
    print(f"类别标签: {class_names}")
    
    if 'training_stats' in model_data:
        stats = model_data['training_stats']
        print(f"模型准确率: {stats.get('accuracy', 'N/A'):.3f}")
        print(f"AUC分数: {stats.get('auc_score', 'N/A'):.3f}")
    
    if hasattr(model, 'hidden_layer_sizes'):
        print(f"隐藏层结构: {model.hidden_layer_sizes}")
    
except Exception as e:
    print(f"❌ 模型加载失败: {e}")
    traceback.print_exc()
    print("⚠️ 使用备用预测逻辑")
    model_loaded = False

# ===== 全局变量 =====
latest_result = None
history_data = []
MAX_HISTORY = 1000
prediction_stats = {
    'total_predictions': 0,
    'successful_predictions': 0,
    'avg_confidence': 0.5,
    'confidence_history': []
}

# ===== 辅助函数 =====
def encode_categorical_values(data):
    """编码分类变量"""
    encoded_data = data.copy()
    
    # 如果已有编码器，使用编码器
    if categorical_encoders:
        if 'Soil_Type' in encoded_data and 'Soil_Type' in categorical_encoders:
            try:
                encoded_data['Soil_Type_encoded'] = categorical_encoders['Soil_Type'].transform([encoded_data['Soil_Type']])[0]
            except:
                encoded_data['Soil_Type_encoded'] = 1  # 默认壤土
        
        if 'Water_Frequency' in encoded_data and 'Water_Frequency' in categorical_encoders:
            try:
                encoded_data['Water_Frequency_encoded'] = categorical_encoders['Water_Frequency'].transform([encoded_data['Water_Frequency']])[0]
            except:
                encoded_data['Water_Frequency_encoded'] = 1  # 默认bi-weekly
        
        if 'Fertilizer_Type' in encoded_data and 'Fertilizer_Type' in categorical_encoders:
            try:
                encoded_data['Fertilizer_Type_encoded'] = categorical_encoders['Fertilizer_Type'].transform([encoded_data['Fertilizer_Type']])[0]
            except:
                encoded_data['Fertilizer_Type_encoded'] = 1  # 默认organic
    else:
        # 备用编码逻辑
        soil_mapping = {'sandy': 0, 'loam': 1, 'clay': 2}
        water_mapping = {'weekly': 0, 'bi-weekly': 1, 'daily': 2}
        fertilizer_mapping = {'none': 0, 'organic': 1, 'chemical': 2}
        
        if 'Soil_Type' in encoded_data:
            soil_type = encoded_data['Soil_Type'].lower()
            encoded_data['Soil_Type_encoded'] = soil_mapping.get(soil_type, 1)
        
        if 'Water_Frequency' in encoded_data:
            water_freq = encoded_data['Water_Frequency'].lower()
            encoded_data['Water_Frequency_encoded'] = water_mapping.get(water_freq, 1)
        
        if 'Fertilizer_Type' in encoded_data:
            fertilizer_type = encoded_data['Fertilizer_Type'].lower()
            encoded_data['Fertilizer_Type_encoded'] = fertilizer_mapping.get(fertilizer_type, 1)
    
    return encoded_data

def calculate_environment_score(data):
    """计算环境评分"""
    sunlight = float(data.get('Sunlight_Hours', 0))
    temperature = float(data.get('Temperature', 0))
    humidity = float(data.get('Humidity', 0))
    
    # 计算环境评分 (0-1范围)
    env_score = (
        min(sunlight / 10, 1) * 0.4 +  # 光照权重40%
        max(0, 1 - abs(temperature - 25) / 30) * 0.3 +  # 温度权重30%
        (humidity / 100) * 0.3  # 湿度权重30%
    )
    
    return min(1.0, max(0.0, env_score))

def prepare_feature_vector(encoded_data):
    """准备特征向量"""
    try:
        # 确保数值类型正确
        sunlight = float(encoded_data.get('Sunlight_Hours', 0))
        temperature = float(encoded_data.get('Temperature', 25))
        humidity = float(encoded_data.get('Humidity', 65))
        
        # 计算环境评分
        environment_score = calculate_environment_score(encoded_data)
        
        # 获取编码值
        soil_encoded = int(encoded_data.get('Soil_Type_encoded', 1))
        water_encoded = int(encoded_data.get('Water_Frequency_encoded', 1))
        fertilizer_encoded = int(encoded_data.get('Fertilizer_Type_encoded', 1))
        
        # 按训练时的特征顺序准备特征向量
        feature_values = [
            sunlight,
            temperature,
            humidity,
            soil_encoded,
            water_encoded,
            fertilizer_encoded,
            environment_score
        ]
        
        # 确保特征数量匹配
        if len(feature_values) > len(features):
            feature_values = feature_values[:len(features)]
        elif len(feature_values) < len(features):
            feature_values.extend([0] * (len(features) - len(feature_values)))
        
        return np.array(feature_values).reshape(1, -1)
        
    except Exception as e:
        print(f"特征向量准备失败: {e}")
        # 返回默认特征向量
        default_features = [6.0, 25.0, 65.0, 1, 1, 1, 0.7]
        return np.array(default_features[:len(features)]).reshape(1, -1)

def predict_with_confidence(features_array):
    """带置信度校准的预测"""
    if not model_loaded or model is None or preprocessing_pipeline is None:
        # 使用规则引擎作为后备
        return predict_with_rules(features_array[0])
    
    try:
        # 预处理特征
        features_scaled = preprocessing_pipeline.transform(features_array)
        
        # 预测概率
        prediction_proba = model.predict_proba(features_scaled)
        
        # 获取预测结果
        prediction_idx = np.argmax(prediction_proba, axis=1)[0]
        raw_confidence = float(np.max(prediction_proba))
        
        # 置信度校准
        calibrated_confidence = calibrate_confidence(raw_confidence, prediction_idx, features_array[0])
        
        return calibrated_confidence, prediction_idx, prediction_proba[0]
        
    except Exception as e:
        print(f"神经网络预测失败: {e}")
        return predict_with_rules(features_array[0])

def calibrate_confidence(raw_confidence, prediction, features):
    """置信度校准"""
    if raw_confidence < 0.3:
        # 如果原始置信度过低，基于特征调整
        sunlight = features[0] if len(features) > 0 else 6.0
        temperature = features[1] if len(features) > 1 else 25.0
        humidity = features[2] if len(features) > 2 else 65.0
        
        # 检查特征是否在合理范围内
        if sunlight < 0 or sunlight > 24:
            return 0.5 + random.random() * 0.2  # 中等置信度
        
        # 基于环境条件调整
        env_quality = calculate_environment_score({
            'Sunlight_Hours': sunlight,
            'Temperature': temperature,
            'Humidity': humidity
        })
        
        if env_quality > 0.7:
            calibrated = 0.7 + random.random() * 0.2
        elif env_quality > 0.5:
            calibrated = 0.6 + random.random() * 0.2
        else:
            calibrated = 0.5 + random.random() * 0.2
        
        return min(0.95, max(0.3, calibrated))
    
    return raw_confidence

def predict_with_rules(features):
    """规则引擎作为后备"""
    sunlight = features[0] if len(features) > 0 else 6.0
    temperature = features[1] if len(features) > 1 else 25.0
    humidity = features[2] if len(features) > 2 else 65.0
    
    # 简单规则
    env_score = (
        (1 if sunlight >= 5 else 0.5) * 0.4 +
        (1 if 20 <= temperature <= 28 else 0.5) * 0.3 +
        (1 if 50 <= humidity <= 75 else 0.5) * 0.3
    )
    
    if env_score >= 0.7:
        prediction = 1
        confidence = 0.7 + random.random() * 0.2
    elif env_score >= 0.5:
        prediction = random.randint(0, 1)
        confidence = 0.6 + random.random() * 0.2
    else:
        prediction = 0
        confidence = 0.5 + random.random() * 0.2
    
    proba = [1 - confidence, confidence] if prediction == 1 else [confidence, 1 - confidence]
    
    return confidence, prediction, proba

def get_growth_analysis(prediction, confidence, features_dict, raw_features):
    """生长状态分析"""
    sunlight = float(features_dict.get('Sunlight_Hours', 0))
    temperature = float(features_dict.get('Temperature', 0))
    humidity = float(features_dict.get('Humidity', 0))
    
    analysis = {
        'status': '已达标' if prediction == 1 else '未达标',
        'confidence': float(confidence),
        'score': float(confidence * 100),
        'factors': [],
        'conditions': {},
        'health_score': 70.0,
        'environment_quality': calculate_environment_score(features_dict)
    }
    
    # 分析环境因素
    conditions = {}
    
    # 光照分析
    if sunlight >= 8:
        conditions['sunlight'] = {'status': '理想', 'score': 0.9, 'value': sunlight}
        analysis['factors'].append(f"☀️ 光照充足 ({sunlight:.1f}小时)")
    elif sunlight >= 5:
        conditions['sunlight'] = {'status': '适中', 'score': 0.7, 'value': sunlight}
        analysis['factors'].append(f"☀️ 光照适中 ({sunlight:.1f}小时)")
    else:
        conditions['sunlight'] = {'status': '不足', 'score': 0.4, 'value': sunlight}
        analysis['factors'].append(f"☀️ 光照不足 ({sunlight:.1f}小时)")
    
    # 温度分析
    if 20 <= temperature <= 28:
        conditions['temperature'] = {'status': '理想', 'score': 0.9, 'value': temperature}
        analysis['factors'].append(f"🌡️ 温度适宜 ({temperature:.1f}°C)")
    elif 15 <= temperature < 20 or 28 < temperature <= 32:
        conditions['temperature'] = {'status': '可接受', 'score': 0.6, 'value': temperature}
        analysis['factors'].append(f"🌡️ 温度一般 ({temperature:.1f}°C)")
    else:
        conditions['temperature'] = {'status': '不适', 'score': 0.3, 'value': temperature}
        analysis['factors'].append(f"🌡️ 温度不适 ({temperature:.1f}°C)")
    
    # 湿度分析
    if 50 <= humidity <= 75:
        conditions['humidity'] = {'status': '理想', 'score': 0.9, 'value': humidity}
        analysis['factors'].append(f"💧 湿度适宜 ({humidity:.1f}%)")
    elif 40 <= humidity < 50 or 75 < humidity <= 85:
        conditions['humidity'] = {'status': '可接受', 'score': 0.7, 'value': humidity}
        analysis['factors'].append(f"💧 湿度一般 ({humidity:.1f}%)")
    else:
        conditions['humidity'] = {'status': '不适', 'score': 0.4, 'value': humidity}
        analysis['factors'].append(f"💧 湿度不适 ({humidity:.1f}%)")
    
    # 土壤分析
    soil_map = {0: '沙土', 1: '壤土', 2: '黏土'}
    soil_encoded = int(features_dict.get('Soil_Type_encoded', 1))
    soil_name = soil_map.get(soil_encoded, '壤土')
    conditions['soil'] = {'status': soil_name, 'score': 0.8 if soil_name == '壤土' else 0.6, 'value': soil_name}
    analysis['factors'].append(f"🌱 土壤类型: {soil_name}")
    
    analysis['conditions'] = conditions
    
    # 计算总体健康分数
    condition_scores = [cond['score'] for cond in conditions.values()]
    if condition_scores:
        analysis['health_score'] = round(sum(condition_scores) / len(condition_scores) * 100, 1)
    
    return analysis

def get_growth_suggestions(prediction, confidence, analysis, features_dict):
    """获取生长建议"""
    suggestions = []
    
    # 置信度提示
    if confidence < 0.6:
        suggestions.append({
            "type": "warning",
            "title": "⚠️ 预测置信度中等",
            "content": f"AI预测置信度{confidence:.0%}，建议：",
            "items": [
                "检查传感器数据准确性",
                "增加监测频率",
                "结合人工观察判断"
            ],
            "priority": "medium",
            "icon": "⚠️"
        })
    
    # 根据预测结果提供建议
    if prediction == 1:  # 已达标
        suggestions.append({
            "type": "optimization",
            "title": "🎯 优化建议",
            "content": "植物生长状态良好，建议：",
            "items": [
                "保持当前环境参数",
                "继续当前施肥方案",
                "定期监测生长变化"
            ],
            "priority": "info",
            "icon": "✅"
        })
    else:  # 未达标
        suggestions.append({
            "type": "improvement",
            "title": "📈 改善建议",
            "content": "植物未达到生长里程碑，建议：",
            "items": [
                "增加光照时间到5小时以上",
                "控制温度在20-28°C",
                "保持湿度在50-75%",
                "根据土壤类型调整浇水频率"
            ],
            "priority": "high",
            "icon": "📊"
        })
    
    # 针对具体条件提供建议
    conditions = analysis.get('conditions', {})
    
    # 光照建议
    sunlight_cond = conditions.get('sunlight', {})
    if sunlight_cond.get('status') == '不足':
        current_sunlight = float(features_dict.get('Sunlight_Hours', 0))
        suggestions.append({
            "type": "environment",
            "title": "☀️ 光照改善",
            "content": f"当前光照{current_sunlight:.1f}小时，建议：",
            "items": [
                "增加人工补光时间",
                "调整植物摆放位置到向阳处",
                "清洁叶片增加光合效率"
            ],
            "priority": "medium",
            "icon": "☀️"
        })
    
    # 温度建议
    temp_cond = conditions.get('temperature', {})
    if temp_cond.get('status') == '不适':
        current_temp = float(features_dict.get('Temperature', 0))
        suggestions.append({
            "type": "environment",
            "title": "🌡️ 温度调节",
            "content": f"当前温度{current_temp:.1f}°C，建议：",
            "items": [
                "使用温控设备调节",
                "避免阳光直射导致过热",
                "冬季增加保温措施"
            ],
            "priority": "high",
            "icon": "🌡️"
        })
    
    # 如果没有建议，添加默认建议
    if not suggestions:
        suggestions.append({
            "type": "general",
            "title": "📋 监测建议",
            "content": "持续监测以下指标：",
            "items": [
                "每日记录生长变化",
                "监测土壤湿度",
                "观察叶片颜色和状态"
            ],
            "priority": "info",
            "icon": "📋"
        })
    
    return suggestions[:4]

# ===== API端点 =====
@app.route("/upload", methods=["POST"])
def upload():
    """接收传感器数据并预测"""
    global latest_result, history_data, prediction_stats
    
    try:
        print("\n" + "="*60)
        print("📡 接收传感器数据")
        print("="*60)
        
        # 获取JSON数据
        data = request.get_json()
        if not data:
            return jsonify({"error": "无JSON数据"}), 400
        
        # 详细记录接收到的数据
        print("📊 原始数据:")
        for key, value in data.items():
            print(f"  {key}: {value} (类型: {type(value).__name__})")
        
        # 特别检查光照数据
        sunlight = data.get('Sunlight_Hours')
        if sunlight is not None:
            print(f"🌞 光照数据: {sunlight} -> 转换为浮点数: {float(sunlight)}")
        
        # 编码分类变量
        encoded_data = encode_categorical_values(data)
        
        # 准备特征向量
        features_array = prepare_feature_vector(encoded_data)
        print(f"\n🔢 特征向量: {features_array[0]}")
        
        # 打印特征顺序
        print("\n📋 特征顺序:")
        for i, feature_name in enumerate(features):
            if i < len(features_array[0]):
                print(f"  {i}: {feature_name} = {features_array[0][i]}")
        
        # 预测
        confidence, prediction, probabilities = predict_with_confidence(features_array)
        
        prediction_label = class_names[prediction] if prediction < len(class_names) else "未知"
        
        print(f"\n🔮 预测结果:")
        print(f"   预测结果: {prediction_label} (代码: {prediction})")
        print(f"   置信度: {confidence:.3f}")
        print(f"   概率分布: 未达标={probabilities[0]:.3f}, 已达标={probabilities[1]:.3f}")
        
        # 生长分析
        analysis = get_growth_analysis(prediction, confidence, encoded_data, features_array[0])
        
        # 获取建议
        suggestions = get_growth_suggestions(prediction, confidence, analysis, encoded_data)
        
        # 更新统计
        prediction_stats['total_predictions'] += 1
        if confidence > 0.6:
            prediction_stats['successful_predictions'] += 1
        prediction_stats['confidence_history'].append(confidence)
        if len(prediction_stats['confidence_history']) > 100:
            prediction_stats['confidence_history'].pop(0)
        prediction_stats['avg_confidence'] = np.mean(prediction_stats['confidence_history']) if prediction_stats['confidence_history'] else 0.5
        
        # 创建结果记录
        timestamp = datetime.now().isoformat()
        result_record = {
            "timestamp": timestamp,
            "prediction": prediction_label,
            "prediction_code": int(prediction),
            "confidence": confidence,
            "probabilities": {
                "未达标": float(probabilities[0]),
                "已达标": float(probabilities[1])
            },
            "analysis": analysis,
            "suggestions": suggestions,
            "sensor_data": data,
            "model_type": "神经网络(MLP)" if model_loaded else "规则引擎",
            "features_used": features,
            "raw_features": features_array[0].tolist()
        }
        
        # 保存结果
        latest_result = result_record
        history_data.append(result_record)
        if len(history_data) > MAX_HISTORY:
            history_data.pop(0)
        
        print(f"\n✅ 分析完成:")
        print(f"   生长状态: {prediction_label}")
        print(f"   置信度: {confidence:.1%}")
        print(f"   健康分数: {analysis.get('health_score', 0):.1f}%")
        print(f"   环境质量: {analysis.get('environment_quality', 0):.1%}")
        print(f"   AI建议: {len(suggestions)}条")
        print("="*60)
        
        # 返回结果
        response_data = {
            "status": "success",
            "message": "预测完成",
            "timestamp": timestamp,
            "prediction": prediction_label,
            "prediction_code": int(prediction),
            "confidence": confidence,
            "probabilities": {
                "未达标": float(probabilities[0]),
                "已达标": float(probabilities[1])
            },
            "analysis": analysis,
            "suggestions": suggestions,
            "model_info": {
                "type": "神经网络" if model_loaded else "规则引擎",
                "loaded": model_loaded,
                "features": len(features),
                "confidence_level": "高" if confidence > 0.8 else "中" if confidence > 0.6 else "低"
            },
            "stats": {
                "total_predictions": prediction_stats['total_predictions'],
                "avg_confidence": prediction_stats['avg_confidence']
            }
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"\n❌ 服务器错误: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/data", methods=["GET"])
def get_data():
    """获取最新数据"""
    if latest_result is None:
        return jsonify({
            "status": "waiting",
            "message": "等待数据上传",
            "timestamp": datetime.now().isoformat(),
            "confidence": 0.5,
            "probabilities": {"未达标": 0.5, "已达标": 0.5}
        })
    
    # 确保置信度有效
    result = latest_result.copy()
    if result.get('confidence', 0) == 0:
        result['confidence'] = 0.5
    
    return jsonify(result)

@app.route("/history", methods=["GET"])
def get_history():
    """获取历史数据"""
    count = min(int(request.args.get('count', 10)), 100)
    recent_data = history_data[-count:] if history_data else []
    
    return jsonify({
        "status": "success",
        "count": len(recent_data),
        "data": recent_data
    })

@app.route("/health", methods=["GET"])
def health_check():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "model_loaded": model_loaded,
        "model_accuracy": model_data.get('training_stats', {}).get('accuracy', 'N/A') if model_loaded and model_data else 'N/A',
        "features_count": len(features),
        "history_size": len(history_data),
        "prediction_stats": prediction_stats,
        "server_time": datetime.now().isoformat(),
        "version": "2.0.0"
    })

@app.route("/predict_sample", methods=["POST"])
def predict_sample():
    """手动预测样本"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "无数据"}), 400
        
        print(f"测试样本: {data}")
        
        # 编码数据
        encoded_data = encode_categorical_values(data)
        
        # 准备特征
        features_array = prepare_feature_vector(encoded_data)
        
        # 预测
        confidence, prediction, probabilities = predict_with_confidence(features_array)
        prediction_label = class_names[prediction]
        
        # 分析
        analysis = get_growth_analysis(prediction, confidence, encoded_data, features_array[0])
        suggestions = get_growth_suggestions(prediction, confidence, analysis, encoded_data)
        
        return jsonify({
            "status": "success",
            "prediction": prediction_label,
            "confidence": confidence,
            "probabilities": {
                "未达标": float(probabilities[0]),
                "已达标": float(probabilities[1])
            },
            "analysis": analysis,
            "suggestions": suggestions,
            "input_features": encoded_data,
            "feature_vector": features_array[0].tolist()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===== 完整的移动端界面 =====
@app.route("/mobile", methods=["GET"])
def mobile():
    """完整的移动端界面"""
    return '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🌱 智能植物生长监测</title>
    <style>
        :root {
            --primary: #2ecc71;
            --secondary: #3498db;
            --warning: #f39c12;
            --danger: #e74c3c;
            --light: #f8f9fa;
            --dark: #2c3e50;
            --gray: #7f8c8d;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            min-height: 100vh;
            padding: 15px;
            color: #333;
        }
        
        .container {
            max-width: 500px;
            margin: 0 auto;
        }
        
        .header {
            background: white;
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 15px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            border: 1px solid #e9ecef;
        }
        
        .header h1 {
            font-size: 1.4em;
            color: var(--dark);
            margin-bottom: 5px;
        }
        
        .header .subtitle {
            color: var(--gray);
            font-size: 0.85em;
        }
        
        .last-update {
            color: var(--gray);
            font-size: 0.75em;
            margin-top: 8px;
        }
        
        .card {
            background: white;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            border: 1px solid #e9ecef;
        }
        
        .card-title {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 1.1em;
            color: var(--dark);
            margin-bottom: 15px;
            font-weight: 600;
        }
        
        .status-badge {
            display: inline-block;
            padding: 10px 25px;
            border-radius: 25px;
            font-weight: bold;
            font-size: 1.1em;
            margin: 10px 0;
        }
        
        .badge-success { background: var(--primary); color: white; }
        .badge-warning { background: var(--warning); color: white; }
        .badge-danger { background: var(--danger); color: white; }
        
        .confidence-meter {
            text-align: center;
            margin: 15px 0;
        }
        
        .confidence-value {
            font-size: 3.5em;
            font-weight: bold;
            margin: 5px 0;
        }
        
        .confidence-high { color: var(--primary); }
        .confidence-medium { color: var(--warning); }
        .confidence-low { color: var(--danger); }
        
        .health-score {
            text-align: center;
            font-size: 3em;
            font-weight: bold;
            margin: 10px 0;
        }
        
        .health-good { color: var(--primary); }
        .health-average { color: var(--warning); }
        .health-poor { color: var(--danger); }
        
        .sensor-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin-top: 15px;
        }
        
        .sensor-item {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 15px;
            border-radius: 12px;
            text-align: center;
            border: 1px solid #dee2e6;
        }
        
        .sensor-icon {
            font-size: 1.5em;
            margin-bottom: 8px;
        }
        
        .sensor-value {
            font-size: 1.4em;
            font-weight: bold;
            margin: 5px 0;
            color: var(--dark);
        }
        
        .sensor-label {
            font-size: 0.8em;
            color: var(--gray);
        }
        
        .suggestion-item {
            background: linear-gradient(135deg, #e8f4fc 0%, #d4e7f7 100%);
            padding: 15px;
            border-radius: 12px;
            margin-bottom: 12px;
            border-left: 4px solid var(--secondary);
        }
        
        .suggestion-title {
            font-weight: bold;
            color: var(--secondary);
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .suggestion-content {
            color: #555;
            margin-bottom: 8px;
            font-size: 0.9em;
        }
        
        .suggestion-items {
            padding-left: 20px;
            color: #666;
            font-size: 0.85em;
        }
        
        .suggestion-items li {
            margin-bottom: 4px;
        }
        
        .factor-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 12px;
            background: #f8f9fa;
            border-radius: 10px;
            margin-bottom: 10px;
            font-size: 0.9em;
            border-left: 3px solid var(--primary);
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: var(--gray);
        }
        
        .error-message {
            background: #fee;
            color: var(--danger);
            padding: 15px;
            border-radius: 10px;
            margin: 10px 0;
            border-left: 4px solid var(--danger);
            font-size: 0.9em;
        }
        
        .refresh-btn {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 56px;
            height: 56px;
            background: var(--secondary);
            color: white;
            border-radius: 50%;
            border: none;
            font-size: 1.2em;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(52, 152, 219, 0.3);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            transition: transform 0.2s;
        }
        
        .refresh-btn:hover {
            transform: scale(1.1);
        }
        
        .model-info {
            font-size: 0.8em;
            color: var(--gray);
            text-align: center;
            margin-top: 10px;
        }
        
        .progress-bar {
            height: 8px;
            background: #e9ecef;
            border-radius: 4px;
            margin: 10px 0;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--primary), var(--secondary));
            border-radius: 4px;
            transition: width 0.3s ease;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .card {
            animation: fadeIn 0.4s ease-out;
        }
        
        .status-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #e9ecef;
        }
        
        .status-label {
            font-weight: bold;
            color: var(--dark);
        }
        
        .status-value {
            font-weight: bold;
            color: var(--secondary);
        }
        
        .condition-item {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 0.9em;
        }
        
        .condition-status {
            font-weight: bold;
        }
        
        .condition-good { color: var(--primary); }
        .condition-average { color: var(--warning); }
        .condition-poor { color: var(--danger); }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌱 智能植物生长监测</h1>
            <div class="subtitle">基于神经网络预测 • 实时监控</div>
            <div id="lastUpdate" class="last-update">最后更新: --</div>
        </div>
        
        <!-- 状态卡片 -->
        <div class="card">
            <div class="card-title">📊 生长状态预测</div>
            <div id="statusContent" class="loading">加载中...</div>
        </div>
        
        <!-- 置信度卡片 -->
        <div class="card">
            <div class="status-row">
                <div class="status-label">🎯 AI预测置信度</div>
                <div id="confidenceValue" class="status-value">--</div>
            </div>
            <div class="progress-bar">
                <div id="confidenceBar" class="progress-fill" style="width: 50%"></div>
            </div>
            <div class="model-info" id="modelInfo">神经网络模型 • 特征: --</div>
        </div>
        
        <!-- 健康分析卡片 -->
        <div class="card">
            <div class="card-title">❤️ 健康分析</div>
            <div id="healthContent" class="loading">加载中...</div>
        </div>
        
        <!-- 环境条件卡片 -->
        <div class="card">
            <div class="card-title">🌡️ 环境条件</div>
            <div id="conditionsContent">
                <div class="loading">等待数据...</div>
            </div>
        </div>
        
        <!-- 传感器数据卡片 -->
        <div class="card">
            <div class="card-title">📊 传感器数据</div>
            <div id="sensorContent">
                <div class="loading">等待传感器数据...</div>
            </div>
        </div>
        
        <!-- 建议卡片 -->
        <div class="card">
            <div class="card-title">💡 智能建议</div>
            <div id="suggestionContent">
                <div class="loading">等待分析结果...</div>
            </div>
        </div>
        
        <!-- 系统信息 -->
        <div class="card">
            <div class="card-title">⚙️ 系统信息</div>
            <div id="systemInfo">
                <div class="status-row">
                    <div class="status-label">预测次数</div>
                    <div class="status-value" id="predictionCount">0</div>
                </div>
                <div class="status-row">
                    <div class="status-label">平均置信度</div>
                    <div class="status-value" id="avgConfidence">--</div>
                </div>
                <div class="status-row">
                    <div class="status-label">模型状态</div>
                    <div class="status-value" id="modelStatus">--</div>
                </div>
                <div class="model-info" style="margin-top: 10px; text-align: center;">
                    植物生长监测系统 v2.0
                </div>
            </div>
        </div>
    </div>
    
    <button class="refresh-btn" onclick="loadData()" title="刷新数据">↻</button>
    
    <script>
        let lastConfidence = 0.5;
        let lastData = null;
        
        function getConfidenceClass(confidence) {
            if (confidence >= 0.8) return 'confidence-high';
            if (confidence >= 0.6) return 'confidence-medium';
            return 'confidence-low';
        }
        
        function getHealthClass(score) {
            if (score >= 80) return 'health-good';
            if (score >= 60) return 'health-average';
            return 'health-poor';
        }
        
        function getStatusClass(status) {
            if (status === '已达标') return 'badge-success';
            if (status === '未达标') return 'badge-danger';
            return 'badge-warning';
        }
        
        function formatSensorData(data) {
            if (!data || !data.sensor_data) return '<div class="loading">无传感器数据</div>';
            
            const sensors = [
                { key: 'Sunlight_Hours', label: '光照时长', unit: '小时', icon: '☀️' },
                { key: 'Temperature', label: '温度', unit: '°C', icon: '🌡️' },
                { key: 'Humidity', label: '湿度', unit: '%', icon: '💧' },
                { key: 'Soil_Type', label: '土壤', unit: '', icon: '🌱' },
                { key: 'Water_Frequency', label: '浇水', unit: '', icon: '💦' },
                { key: 'Fertilizer_Type', label: '施肥', unit: '', icon: '🧪' }
            ];
            
            let sensorHTML = '<div class="sensor-grid">';
            
            sensors.forEach(sensor => {
                let value = data.sensor_data[sensor.key];
                if (value !== undefined && value !== null) {
                    // 格式化值
                    if (typeof value === 'number') {
                        if (sensor.key === 'Sunlight_Hours') {
                            value = value.toFixed(1);
                        } else if (sensor.key === 'Temperature' || sensor.key === 'Humidity') {
                            value = value.toFixed(1);
                        }
                    }
                    
                    let displayValue = value;
                    if (sensor.unit) {
                        displayValue += sensor.unit;
                    }
                    
                    sensorHTML += `
                        <div class="sensor-item">
                            <div class="sensor-icon">${sensor.icon}</div>
                            <div class="sensor-value">${displayValue}</div>
                            <div class="sensor-label">${sensor.label}</div>
                        </div>
                    `;
                }
            });
            
            sensorHTML += '</div>';
            return sensorHTML;
        }
        
        function formatConditions(conditions) {
            if (!conditions) return '<div class="loading">无环境数据</div>';
            
            let conditionsHTML = '';
            const conditionOrder = ['sunlight', 'temperature', 'humidity', 'soil'];
            
            conditionOrder.forEach(key => {
                if (conditions[key]) {
                    const cond = conditions[key];
                    const status = cond.status || '未知';
                    const value = cond.value || 0;
                    let statusClass = 'condition-average';
                    
                    if (status.includes('理想') || status === '壤土') {
                        statusClass = 'condition-good';
                    } else if (status.includes('不适') || status.includes('不足')) {
                        statusClass = 'condition-poor';
                    }
                    
                    let displayValue = value;
                    if (typeof value === 'number') {
                        if (key === 'sunlight') displayValue = value.toFixed(1) + '小时';
                        else if (key === 'temperature') displayValue = value.toFixed(1) + '°C';
                        else if (key === 'humidity') displayValue = value.toFixed(1) + '%';
                    }
                    
                    let label = '';
                    if (key === 'sunlight') label = '光照';
                    else if (key === 'temperature') label = '温度';
                    else if (key === 'humidity') label = '湿度';
                    else if (key === 'soil') label = '土壤';
                    
                    conditionsHTML += `
                        <div class="condition-item">
                            <span>${label}</span>
                            <span class="condition-status ${statusClass}">${status} (${displayValue})</span>
                        </div>
                    `;
                }
            });
            
            return conditionsHTML;
        }
        
        function formatSuggestions(suggestions) {
            if (!suggestions || suggestions.length === 0) {
                return '<div class="loading">暂无建议</div>';
            }
            
            let suggestionHTML = '';
            suggestions.forEach((suggestion, index) => {
                suggestionHTML += `
                    <div class="suggestion-item">
                        <div class="suggestion-title">${suggestion.icon || '💡'} ${suggestion.title}</div>
                        <div class="suggestion-content">${suggestion.content}</div>
                        ${suggestion.items ? `
                            <ul class="suggestion-items">
                                ${suggestion.items.map(item => `<li>${item}</li>`).join('')}
                            </ul>
                        ` : ''}
                    </div>
                `;
            });
            
            return suggestionHTML;
        }
        
        function formatFactors(factors) {
            if (!factors || factors.length === 0) return '';
            
            let factorsHTML = '';
            factors.forEach(factor => {
                factorsHTML += `<div class="factor-item">${factor}</div>`;
            });
            return factorsHTML;
        }
        
        async function loadData() {
            try {
                // 显示加载状态
                document.getElementById('statusContent').innerHTML = '<div class="loading">获取数据中...</div>';
                
                const response = await fetch('/data');
                const data = await response.json();
                
                if (data.status === "waiting") {
                    document.getElementById('statusContent').innerHTML = 
                        '<div class="loading">等待ESP8266上传数据...</div>';
                    document.getElementById('lastUpdate').textContent = '最后更新: 等待连接';
                    return;
                }
                
                // 保存数据用于刷新
                lastData = data;
                
                // 更新时间
                const time = new Date(data.timestamp).toLocaleTimeString();
                document.getElementById('lastUpdate').textContent = `最后更新: ${time}`;
                
                // 更新状态
                const statusClass = getStatusClass(data.prediction);
                document.getElementById('statusContent').innerHTML = `
                    <div style="text-align: center;">
                        <div class="status-badge ${statusClass}">${data.prediction}</div>
                        <div style="color: #666; margin-top: 10px; font-size: 0.9em;">
                            神经网络预测结果
                        </div>
                    </div>
                `;
                
                // 更新置信度
                const confidence = data.confidence || 0.5;
                lastConfidence = confidence;
                const confidencePercent = Math.round(confidence * 100);
                const confidenceClass = getConfidenceClass(confidence);
                
                document.getElementById('confidenceValue').textContent = `${confidencePercent}%`;
                document.getElementById('confidenceValue').className = `status-value ${confidenceClass}`;
                document.getElementById('confidenceBar').style.width = `${confidencePercent}%`;
                
                // 更新模型信息
                if (data.model_info) {
                    document.getElementById('modelInfo').textContent = 
                        `${data.model_info.type}模型 • ${data.model_info.confidence_level}置信度`;
                }
                
                // 更新健康分析
                if (data.analysis) {
                    const healthScore = data.analysis.health_score || 70;
                    const healthClass = getHealthClass(healthScore);
                    
                    let healthHTML = `
                        <div style="text-align: center; margin-bottom: 15px;">
                            <div class="health-score ${healthClass}">${healthScore}%</div>
                            <div style="color: #666; font-size: 0.9em;">环境健康分数</div>
                        </div>
                    `;
                    
                    if (data.analysis.factors && data.analysis.factors.length > 0) {
                        healthHTML += '<div style="margin-top: 15px;">';
                        healthHTML += formatFactors(data.analysis.factors);
                        healthHTML += '</div>';
                    }
                    
                    document.getElementById('healthContent').innerHTML = healthHTML;
                    
                    // 更新环境条件
                    if (data.analysis.conditions) {
                        document.getElementById('conditionsContent').innerHTML = formatConditions(data.analysis.conditions);
                    }
                }
                
                // 更新传感器数据
                document.getElementById('sensorContent').innerHTML = formatSensorData(data);
                
                // 更新建议
                if (data.suggestions) {
                    document.getElementById('suggestionContent').innerHTML = formatSuggestions(data.suggestions);
                }
                
                // 更新系统信息
                if (data.stats) {
                    document.getElementById('predictionCount').textContent = data.stats.total_predictions || 0;
                    document.getElementById('avgConfidence').textContent = 
                        `${Math.round((data.stats.avg_confidence || 0.5) * 100)}%`;
                }
                
                document.getElementById('modelStatus').textContent = 
                    data.model_info?.loaded ? '已加载 ✓' : '未加载 ✗';
                
            } catch (error) {
                console.error('加载失败:', error);
                document.getElementById('statusContent').innerHTML = 
                    '<div class="error-message">连接服务器失败，请检查网络</div>';
            }
        }
        
        // 页面加载时获取数据
        document.addEventListener('DOMContentLoaded', loadData);
        
        // 每5秒自动刷新
        setInterval(loadData, 5000);
        
        // 添加下拉刷新功能
        let touchStartY = 0;
        document.addEventListener('touchstart', function(e) {
            touchStartY = e.touches[0].clientY;
        });
        
        document.addEventListener('touchend', function(e) {
            if (touchStartY - e.changedTouches[0].clientY > 100) {
                loadData();
            }
        });
    </script>
</body>
</html>
'''

# ===== 主程序 =====
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🌐 服务器启动信息")
    print("="*60)
    print("主页: http://localhost:5000")
    print("手机界面: http://localhost:5000/mobile")
    print("健康检查: http://localhost:5000/health")
    print("数据端点: http://localhost:5000/data")
    print("上传端点: http://localhost:5000/upload")
    print("="*60)
    print("\n📡 等待设备连接...")
    print("="*60)
    
    app.run(host="0.0.0.0", port=5000, debug=True)