# test_onnx_model_fixed.py - 修复的ONNX模型测试
import numpy as np
import onnxruntime as ort
import json

def test_onnx_model():
    print("🔍 测试ONNX模型...")
    
    # 加载元数据
    with open('model_metadata.json', 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    print(f"输入维度: {metadata['input_dim']}")
    print(f"特征: {metadata['features']}")
    
    # 创建ONNX运行时会话
    try:
        ort_session = ort.InferenceSession("plant_growth_model.onnx")
        print("✅ ONNX模型加载成功")
    except Exception as e:
        print(f"❌ 加载失败: {e}")
        return
    
    # 获取输入输出信息
    input_name = ort_session.get_inputs()[0].name
    input_shape = ort_session.get_inputs()[0].shape
    output_name = ort_session.get_outputs()[0].name
    
    print(f"输入名称: {input_name}")
    print(f"输入形状: {input_shape}")
    print(f"输出名称: {output_name}")
    
    # 检查输出形状
    output_shape = ort_session.get_outputs()[0].shape
    print(f"输出形状: {output_shape}")
    
    # 测试数据
    test_cases = [
        # 良好条件
        {
            "name": "良好条件",
            "features": [8.0, 25.0, 65.0, 1, 1, 1, 0.85],
            "description": "光照充足，温度适宜，湿度适中，壤土，每两周浇水，有机肥"
        },
        # 中等条件
        {
            "name": "中等条件", 
            "features": [5.0, 28.0, 50.0, 0, 0, 0, 0.65],
            "description": "光照适中，温度偏高，湿度偏低，沙土，每周浇水，无施肥"
        },
        # 较差条件
        {
            "name": "较差条件",
            "features": [3.0, 15.0, 35.0, 2, 2, 2, 0.35],
            "description": "光照不足，温度过低，湿度过低，黏土，每天浇水，化肥"
        }
    ]
    
    print("\n📊 测试结果:")
    print("=" * 80)
    
    for test_case in test_cases:
        # 准备输入数据
        input_data = np.array([test_case["features"]], dtype=np.float32)
        
        print(f"\n测试案例: {test_case['name']}")
        print(f"描述: {test_case['description']}")
        print(f"输入特征:")
        for i, (feature, value) in enumerate(zip(metadata['features'], test_case['features'])):
            print(f"  {i+1}. {feature}: {value}")
        
        # 运行推理
        ort_inputs = {input_name: input_data}
        ort_outputs = ort_session.run(None, ort_inputs)
        
        print(f"\n推理输出:")
        
        # 处理不同类型的输出
        if len(ort_outputs) == 1:
            output = ort_outputs[0]
            
            # 检查输出形状
            print(f"输出形状: {output.shape}")
            print(f"输出类型: {type(output)}")
            print(f"输出内容: {output}")
            
            # 解析输出
            if output.ndim == 2:
                # 二维数组，如 [[0.3, 0.7]]
                probabilities = output[0]
                if len(probabilities) == 2:
                    prob_0, prob_1 = probabilities[0], probabilities[1]
                else:
                    # 如果是单个值，假设是概率或分类
                    prob_1 = output[0][0] if output[0][0] <= 1 else 1 / (1 + np.exp(-output[0][0]))
                    prob_0 = 1 - prob_1
                    
            elif output.ndim == 1:
                # 一维数组
                if len(output) == 2:
                    prob_0, prob_1 = output[0], output[1]
                else:
                    # 单个输出值
                    prob_1 = output[0] if output[0] <= 1 else 1 / (1 + np.exp(-output[0]))
                    prob_0 = 1 - prob_1
                    
            else:
                # 其他情况
                print(f"⚠️ 未知输出维度: {output.ndim}")
                prob_0, prob_1 = 0.5, 0.5
                
        else:
            # 多个输出
            print(f"⚠️ 多个输出: {len(ort_outputs)}")
            for i, out in enumerate(ort_outputs):
                print(f"  输出{i}: shape={out.shape}, value={out}")
            
            # 取第一个输出
            if ort_outputs[0].ndim == 2 and ort_outputs[0].shape[1] == 2:
                probabilities = ort_outputs[0][0]
                prob_0, prob_1 = probabilities[0], probabilities[1]
            else:
                prob_0, prob_1 = 0.5, 0.5
        
        # 确保概率有效
        prob_0 = max(0.0, min(1.0, float(prob_0)))
        prob_1 = max(0.0, min(1.0, float(prob_1)))
        
        # 归一化
        total = prob_0 + prob_1
        if total > 0:
            prob_0 /= total
            prob_1 /= total
        
        # 预测
        prediction = 1 if prob_1 > prob_0 else 0
        confidence = max(prob_0, prob_1)
        
        print(f"📊 分析结果:")
        print(f"  未达标概率: {prob_0:.3f}")
        print(f"  已达标概率: {prob_1:.3f}")
        print(f"  预测结果: {'✅ 已达标' if prediction == 1 else '⚠️ 未达标'}")
        print(f"  置信度: {confidence:.3f}")
        
        # 提供建议
        if prediction == 1:
            if confidence > 0.8:
                suggestion = "✅ 生长状态优秀！保持当前条件。"
            elif confidence > 0.6:
                suggestion = "✅ 生长状态良好。可适当优化环境条件。"
            else:
                suggestion = "⚠️ 勉强达标。建议继续改善环境条件。"
        else:
            if confidence > 0.8:
                suggestion = "❌ 生长条件差。需要全面改善环境。"
            elif confidence > 0.6:
                suggestion = "⚠️ 需要改善。重点关注光照和温湿度。"
            else:
                suggestion = "⚠️ 接近达标。微调环境条件即可改善。"
        
        print(f"  建议: {suggestion}")
        print("-" * 80)
    
    # 额外测试：批量推理
    print("\n🔬 批量推理测试...")
    batch_input = np.array([
        [8.0, 25.0, 65.0, 1, 1, 1, 0.85],
        [5.0, 28.0, 50.0, 0, 0, 0, 0.65],
        [3.0, 15.0, 35.0, 2, 2, 2, 0.35]
    ], dtype=np.float32)
    
    print(f"批量输入形状: {batch_input.shape}")
    
    ort_inputs = {input_name: batch_input}
    ort_outputs = ort_session.run(None, ort_inputs)
    
    print(f"批量输出:")
    if len(ort_outputs) == 1 and ort_outputs[0].ndim == 2:
        batch_output = ort_outputs[0]
        for i in range(batch_output.shape[0]):
            if batch_output.shape[1] == 2:
                prob_0, prob_1 = batch_output[i][0], batch_output[i][1]
            else:
                prob_1 = batch_output[i][0] if batch_output[i][0] <= 1 else 1 / (1 + np.exp(-batch_output[i][0]))
                prob_0 = 1 - prob_1
            
            prediction = 1 if prob_1 > prob_0 else 0
            print(f"  样本{i+1}: 未达标={prob_0:.3f}, 已达标={prob_1:.3f}, 预测={'✅' if prediction==1 else '⚠️'}")

def check_model_details():
    """检查模型详细信息"""
    print("\n🔍 检查模型详细信息...")
    
    import onnx
    
    # 加载模型
    model = onnx.load("plant_growth_model.onnx")
    
    # 检查基本信息
    print(f"模型IR版本: {model.ir_version}")
    print(f"生产者: {model.producer_name}")
    print(f"模型版本: {model.model_version}")
    
    # 检查opset版本
    for opset in model.opset_import:
        print(f"OpSet 域: {opset.domain}, 版本: {opset.version}")
    
    # 检查输入输出
    print(f"\n输入数量: {len(model.graph.input)}")
    for i, input in enumerate(model.graph.input):
        print(f"  输入{i}: {input.name}")
        if input.type.tensor_type.HasField("shape"):
            dims = input.type.tensor_type.shape.dim
            shape = []
            for dim in dims:
                if dim.HasField("dim_value"):
                    shape.append(dim.dim_value)
                else:
                    shape.append("?")
            print(f"      形状: {shape}")
    
    print(f"\n输出数量: {len(model.graph.output)}")
    for i, output in enumerate(model.graph.output):
        print(f"  输出{i}: {output.name}")
        if output.type.tensor_type.HasField("shape"):
            dims = output.type.tensor_type.shape.dim
            shape = []
            for dim in dims:
                if dim.HasField("dim_value"):
                    shape.append(dim.dim_value)
                else:
                    shape.append("?")
            print(f"      形状: {shape}")
    
    # 检查节点数量
    print(f"\n节点数量: {len(model.graph.node)}")
    
    # 检查模型是否包含概率输出
    print("\n🔍 检查输出类型...")
    
    # 获取最后几个节点
    last_nodes = model.graph.node[-5:] if len(model.graph.node) >= 5 else model.graph.node
    for node in last_nodes:
        print(f"节点: {node.op_type}, 输入: {node.input}, 输出: {node.output}")
        
        if node.op_type in ['Softmax', 'Sigmoid']:
            print("  ✅ 包含概率激活函数")
        elif node.op_type == 'Add':
            print("  ℹ️ 加法操作")
        elif node.op_type == 'MatMul':
            print("  ℹ️ 矩阵乘法")
        elif node.op_type == 'Relu':
            print("  ℹ️ ReLU激活")

if __name__ == "__main__":
    test_onnx_model()
    check_model_details()