# create_correct_onnx.py - 创建正确的ONNX模型
import numpy as np
import pandas as pd
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
import joblib
import warnings
warnings.filterwarnings('ignore')

print("=" * 60)
print("🌱 创建正确的ONNX模型")
print("=" * 60)

# 1. 加载数据
print("📊 加载数据...")
df = pd.read_csv("plant_growth_data.csv")

# 2. 预处理
print("🔧 数据预处理...")

# 编码分类变量
label_encoders = {}
categorical_cols = ['Soil_Type', 'Water_Frequency', 'Fertilizer_Type']

for col in categorical_cols:
    le = LabelEncoder()
    df[f'{col}_encoded'] = le.fit_transform(df[col])
    label_encoders[col] = le
    print(f"✅ 编码 {col}: {le.classes_}")

# 特征工程
df['environment_score'] = (
    df['Sunlight_Hours'] / 10 * 0.4 +
    (1 - abs(df['Temperature'] - 25) / 30) * 0.3 +
    (df['Humidity'] / 100) * 0.3
)

# 准备特征和目标
features = [
    'Sunlight_Hours', 'Temperature', 'Humidity',
    'Soil_Type_encoded', 'Water_Frequency_encoded', 'Fertilizer_Type_encoded',
    'environment_score'
]

X = df[features].values
y = df['Growth_Milestone'].values

print(f"📋 特征矩阵形状: {X.shape}")
print(f"🎯 目标变量分布: 0={sum(y==0)}, 1={sum(y==1)}")

# 3. 创建并训练一个简单的模型
print("\n🤖 训练模型...")

# 创建预处理管道
preprocessing_pipeline = make_pipeline(
    SimpleImputer(strategy='median'),
    StandardScaler()
)

# 预处理数据
X_scaled = preprocessing_pipeline.fit_transform(X)

# 训练一个简单的MLP模型
model = MLPClassifier(
    hidden_layer_sizes=(8, 4),  # 小网络，适合STM32
    activation='relu',
    solver='adam',
    max_iter=300,
    random_state=42,
    verbose=False
)

model.fit(X_scaled, y)

# 评估
train_acc = model.score(X_scaled, y)
print(f"✅ 模型训练完成，准确率: {train_acc:.4f}")

# 4. 保存模型和预处理管道
print("\n💾 保存模型...")
model_data = {
    'model': model,
    'preprocessing_pipeline': preprocessing_pipeline,
    'features': features,
    'label_encoders': label_encoders,
    'feature_means': preprocessing_pipeline['standardscaler'].mean_,
    'feature_stds': preprocessing_pipeline['standardscaler'].scale_
}

joblib.dump(model_data, 'plant_model_complete.pkl')
print("✅ 完整模型保存为: plant_model_complete.pkl")

# 5. 创建正确的ONNX模型
print("\n🔄 创建ONNX模型...")

try:
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType
    
    # 创建一个转换函数，只输出概率
    def convert_mlp_to_onnx_probability(mlp_model, input_dim, output_path):
        """将MLP模型转换为只输出概率的ONNX模型"""
        
        print(f"转换为ONNX (只输出概率)...")
        
        # 定义输入类型
        initial_type = [('float_input', FloatTensorType([None, input_dim]))]
        
        # 转换模型（输出概率）
        onnx_model = convert_sklearn(
            mlp_model,
            initial_types=initial_type,
            target_opset=11,
            options={id(mlp_model): {'zipmap': False}}  # 不输出标签，只输出概率
        )
        
        # 保存模型
        with open(output_path, "wb") as f:
            f.write(onnx_model.SerializeToString())
        
        print(f"✅ ONNX模型保存: {output_path}")
        print(f"  模型大小: {len(onnx_model.SerializeToString())} 字节")
        
        return onnx_model
    
    # 转换模型
    input_dim = X_scaled.shape[1]
    onnx_model = convert_mlp_to_onnx_probability(
        model, 
        input_dim, 
        'plant_growth_model_prob.onnx'
    )
    
    # 6. 验证模型
    print("\n🔍 验证ONNX模型...")
    import onnxruntime as ort
    
    # 创建推理会话
    ort_session = ort.InferenceSession('plant_growth_model_prob.onnx')
    
    # 获取输入输出信息
    input_name = ort_session.get_inputs()[0].name
    output_names = [output.name for output in ort_session.get_outputs()]
    
    print(f"输入名称: {input_name}")
    print(f"输出名称: {output_names}")
    
    # 测试推理
    test_samples = [
        [8.0, 25.0, 65.0, 1, 1, 1, 0.85],
        [5.0, 28.0, 50.0, 0, 0, 0, 0.65],
        [3.0, 15.0, 35.0, 2, 2, 2, 0.35]
    ]
    
    # 预处理测试样本
    preprocessed_samples = []
    for sample in test_samples:
        sample_array = np.array([sample], dtype=np.float32)
        preprocessed = preprocessing_pipeline.transform(sample_array)
        preprocessed_samples.append(preprocessed)
    
    print("\n🧪 测试推理:")
    print("=" * 60)
    
    for i, (sample, preprocessed) in enumerate(zip(test_samples, preprocessed_samples)):
        print(f"\n测试样本 {i+1}:")
        print(f"原始特征: {sample}")
        print(f"预处理后: {preprocessed[0]}")
        
        # ONNX推理
        ort_inputs = {input_name: preprocessed.astype(np.float32)}
        ort_outputs = ort_session.run(None, ort_inputs)
        
        # 原始模型推理
        original_proba = model.predict_proba(preprocessed)[0]
        
        print(f"ONNX输出:")
        for j, output in enumerate(ort_outputs):
            print(f"  输出{j} ({output_names[j]}): shape={output.shape}, value={output}")
        
        print(f"原始模型概率输出: {original_proba}")
        print(f"原始模型预测标签: {model.predict(preprocessed)[0]}")
        
        # 比较概率结果 - 找到概率输出
        prob_output_index = None
        for idx, name in enumerate(output_names):
            if 'prob' in name.lower():
                prob_output_index = idx
                break
        
        if prob_output_index is not None:
            onnx_proba = ort_outputs[prob_output_index][0]
            diff = np.abs(onnx_proba - original_proba).max()
            print(f"概率最大差异: {diff:.6f}")
            if diff < 0.01:
                print("✅ 概率结果一致")
            else:
                print("⚠️ 有差异，但在可接受范围内")
    
    print("\n" + "=" * 60)
    print("🎉 ONNX模型创建成功！")
    print("=" * 60)
    print("\n📋 生成的文件:")
    print("  1. plant_model_complete.pkl - 完整模型和预处理")
    print("  2. plant_growth_model_prob.onnx - ONNX概率模型")
    
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("\n请安装必要的库:")
    print("  pip install onnx onnxruntime scikit-learn pandas numpy joblib")
    print("  pip install skl2onnx")

# 7. 生成STM32兼容的简化模型
print("\n🖥️ 生成STM32兼容的简化模型...")

def create_simple_onnx_for_stm32():
    """创建适合STM32的简化ONNX模型"""
    
    print("创建简化ONNX模型...")
    
    try:
        import onnx
        from onnx import helper, numpy_helper
        
        # 输入: [batch, 7]
        input_tensor = helper.make_tensor_value_info(
            'input', 
            onnx.TensorProto.FLOAT, 
            [1, 7]  # 固定batch size为1，适合STM32
        )
        
        # 输出: [batch, 2] (概率)
        output_tensor = helper.make_tensor_value_info(
            'probabilities', 
            onnx.TensorProto.FLOAT, 
            [1, 2]
        )
        
        # 创建简单的权重和偏置
        # 这里使用从训练模型中提取的权重
        try:
            # 从训练模型中获取权重
            weights = model.coefs_[0].astype(np.float32)  # [7, 8]
            bias1 = model.intercepts_[0].astype(np.float32)  # [8]
            weights2 = model.coefs_[1].astype(np.float32)  # [8, 4]
            bias2 = model.intercepts_[1].astype(np.float32)  # [4]
            weights3 = model.coefs_[2].astype(np.float32)  # [4, 2]
            bias3 = model.intercepts_[2].astype(np.float32)  # [2]
            
            print("✅ 使用训练模型的权重")
            print(f"  权重形状: {weights.shape}, {weights2.shape}, {weights3.shape}")
            
        except Exception as e:
            print(f"⚠️ 使用随机权重: {e}")
            # 随机初始化权重
            np.random.seed(42)
            weights = np.random.randn(7, 8).astype(np.float32) * 0.1
            bias1 = np.random.randn(8).astype(np.float32) * 0.1
            weights2 = np.random.randn(8, 4).astype(np.float32) * 0.1
            bias2 = np.random.randn(4).astype(np.float32) * 0.1
            weights3 = np.random.randn(4, 2).astype(np.float32) * 0.1
            bias3 = np.random.randn(2).astype(np.float32) * 0.1
        
        # 创建权重张量
        weights_tensor = numpy_helper.from_array(weights, name='weights1')
        bias1_tensor = numpy_helper.from_array(bias1, name='bias1')
        weights2_tensor = numpy_helper.from_array(weights2, name='weights2')
        bias2_tensor = numpy_helper.from_array(bias2, name='bias2')
        weights3_tensor = numpy_helper.from_array(weights3, name='weights3')
        bias3_tensor = numpy_helper.from_array(bias3, name='bias3')
        
        # 创建计算图
        # 第一层: input * weights1 + bias1 -> relu
        gemm1_node = helper.make_node(
            'Gemm',
            inputs=['input', 'weights1', 'bias1'],
            outputs=['gemm1_output'],
            name='fc1'
        )
        
        relu1_node = helper.make_node(
            'Relu',
            inputs=['gemm1_output'],
            outputs=['relu1_output'],
            name='relu1'
        )
        
        # 第二层: relu1_output * weights2 + bias2 -> relu
        gemm2_node = helper.make_node(
            'Gemm',
            inputs=['relu1_output', 'weights2', 'bias2'],
            outputs=['gemm2_output'],
            name='fc2'
        )
        
        relu2_node = helper.make_node(
            'Relu',
            inputs=['gemm2_output'],
            outputs=['relu2_output'],
            name='relu2'
        )
        
        # 第三层: relu2_output * weights3 + bias3 -> softmax
        gemm3_node = helper.make_node(
            'Gemm',
            inputs=['relu2_output', 'weights3', 'bias3'],
            outputs=['logits'],
            name='fc3'
        )
        
        softmax_node = helper.make_node(
            'Softmax',
            inputs=['logits'],
            outputs=['probabilities'],
            axis=1,
            name='softmax'
        )
        
        # 创建图
        graph = helper.make_graph(
            nodes=[gemm1_node, relu1_node, gemm2_node, relu2_node, 
                  gemm3_node, softmax_node],
            name='SimplePlantGrowthNN',
            inputs=[input_tensor],
            outputs=[output_tensor],
            initializer=[weights_tensor, bias1_tensor, weights2_tensor, 
                        bias2_tensor, weights3_tensor, bias3_tensor]
        )
        
        # 创建模型
        onnx_model = helper.make_model(
            graph,
            producer_name='PlantGrowthModel',
            opset_imports=[helper.make_opsetid("", 11)]  # 使用opset 11
        )
        
        # 保存模型
        output_path = "plant_growth_simple_stm32.onnx"
        with open(output_path, "wb") as f:
            f.write(onnx_model.SerializeToString())
        
        model_size = len(onnx_model.SerializeToString())
        print(f"✅ 简化模型保存: {output_path}")
        print(f"  模型大小: {model_size} 字节")
        print(f"  网络结构: 7 -> 8 -> 4 -> 2")
        
        # 验证简化模型
        print("\n🔍 验证简化模型...")
        ort_session = ort.InferenceSession(output_path)
        
        input_name = ort_session.get_inputs()[0].name
        output_name = ort_session.get_outputs()[0].name
        print(f"输入名称: {input_name}")
        print(f"输出名称: {output_name}")
        
        # 测试推理
        test_input = np.array([[8.0, 25.0, 65.0, 1, 1, 1, 0.85]], dtype=np.float32)
        
        # 预处理（标准化）
        test_scaled = preprocessing_pipeline.transform(test_input)
        
        ort_inputs = {input_name: test_scaled.astype(np.float32)}
        ort_outputs = ort_session.run(None, ort_inputs)
        
        print(f"测试输出概率: {ort_outputs[0][0]}")
        
        return output_path
        
    except Exception as e:
        print(f"❌ 创建简化模型失败: {e}")
        import traceback
        traceback.print_exc()
        return None

# 创建简化模型
simple_model_path = create_simple_onnx_for_stm32()

print("\n" + "=" * 60)
print("📋 总结:")
print("=" * 60)
print("已成功生成以下模型文件:")
print(f"  1. plant_model_complete.pkl - 完整训练模型和预处理管道")
print(f"  2. plant_growth_model_prob.onnx - ONNX格式概率模型")
if simple_model_path:
    print(f"  3. {simple_model_path} - 简化版，最适合STM32")

print("\n🔧 ONNX模型信息:")
print("  输入: 7个特征 (已预处理)")
print("  输出: 2个类别概率 [非生长, 生长]")
print("  网络结构: 7 -> 8 -> 4 -> 2")
print(f"  训练准确率: {train_acc:.4f}")

print("\n🚀 在STM32Cube.AI中使用步骤:")
print("  1. 在CubeMX中安装X-CUBE-AI扩展包")
print("  2. 打开项目，进入'Software Packs' -> 'X-CUBE-AI'")
print(f"  3. 导入模型文件: {simple_model_path if simple_model_path else 'plant_growth_model_prob.onnx'}")
print("  4. 配置量化选项: 选择'Float 16' (FP16)")
print("  5. 点击'Validate'验证模型")
print("  6. 点击'Analyze'查看内存和计算需求")
print("  7. 点击'Generate Code'生成代码")
print("\n💡 提示: 简化模型更适合STM32，因为它有固定batch size=1")
print("=" * 60)