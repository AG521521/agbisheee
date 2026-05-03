# fix_onnx_model.py - 修复ONNX模型输出格式
import onnx
from onnx import helper, numpy_helper
import numpy as np

def fix_model_output(model_path, output_path="plant_growth_model_fixed.onnx"):
    """修复模型输出格式，确保输出是概率"""
    
    print("🔧 修复ONNX模型输出格式...")
    
    # 加载模型
    model = onnx.load(model_path)
    
    # 获取原始输出节点
    original_output_name = model.graph.output[0].name
    
    print(f"原始输出名称: {original_output_name}")
    
    # 找到输出节点
    output_node = None
    for node in model.graph.node:
        if original_output_name in node.output:
            output_node = node
            break
    
    if output_node is None:
        print("❌ 找不到输出节点")
        return None
    
    print(f"输出节点: {output_node.op_type}")
    
    # 检查是否需要添加Softmax
    if output_node.op_type not in ['Softmax', 'Sigmoid']:
        print("⚠️ 输出节点没有概率激活函数，尝试修复...")
        
        # 创建新的输出节点名称
        new_output_name = "probabilities"
        
        # 添加Softmax节点
        softmax_node = helper.make_node(
            'Softmax',
            inputs=[original_output_name],
            outputs=[new_output_name],
            axis=1,
            name='softmax_output'
        )
        
        # 将新节点添加到图中
        model.graph.node.append(softmax_node)
        
        # 更新输出
        for i, output in enumerate(model.graph.output):
            if output.name == original_output_name:
                # 更新输出名称
                model.graph.output[i].name = new_output_name
                break
        
        print(f"✅ 已添加Softmax层，新输出名称: {new_output_name}")
    
    # 确保输出是二维的 [batch, 2]
    output_shape = None
    for output in model.graph.output:
        if output.type.HasField("tensor_type"):
            tensor_type = output.type.tensor_type
            if tensor_type.HasField("shape"):
                dims = tensor_type.shape.dim
                if len(dims) == 1:
                    print("⚠️ 输出是一维的，尝试调整为二维...")
                    # 添加一个维度
                    dims.add()
                    dims[1].dim_value = dims[0].dim_value
                    dims[0].dim_value = 1
                    print(f"  新形状: [1, {dims[1].dim_value}]")
                elif len(dims) == 2:
                    print(f"✅ 输出已经是二维的: {[d.dim_value for d in dims]}")
    
    # 保存修复后的模型
    onnx.save(model, output_path)
    print(f"✅ 修复后的模型已保存: {output_path}")
    
    return output_path

def convert_to_two_class_probability(model_path, output_path="plant_growth_model_two_class.onnx"):
    """将模型转换为二分类概率输出"""
    
    print("\n🔄 转换为二分类概率输出...")
    
    # 加载模型
    model = onnx.load(model_path)
    
    # 创建二分类输出
    original_output = model.graph.output[0]
    original_output_name = original_output.name
    
    print(f"原始输出: {original_output_name}")
    
    # 查找输出节点
    last_node = None
    for node in reversed(model.graph.node):
        if original_output_name in node.output:
            last_node = node
            break
    
    if last_node is None:
        print("❌ 找不到最后的节点")
        return None
    
    print(f"最后节点: {last_node.op_type}, 输出: {last_node.output}")
    
    # 如果输出已经是合适的格式，直接复制
    if last_node.op_type == 'Softmax' and len(last_node.output) == 1:
        print("✅ 模型已经有Softmax输出")
        return model_path
    
    # 添加一个全连接层将输出映射到2个类别
    # 假设原始输出维度为N，我们需要映射到2
    
    # 获取输出维度
    output_dim = None
    for output in model.graph.output:
        if output.type.HasField("tensor_type"):
            tensor_type = output.type.tensor_type
            if tensor_type.HasField("shape"):
                dims = tensor_type.shape.dim
                if len(dims) > 1:
                    output_dim = dims[-1].dim_value
    
    if output_dim is None:
        print("⚠️ 无法确定输出维度，使用默认转换")
        
        # 添加简单的Sigmoid转换为概率
        sigmoid_output_name = "sigmoid_output"
        sigmoid_node = helper.make_node(
            'Sigmoid',
            inputs=[original_output_name],
            outputs=[sigmoid_output_name],
            name='sigmoid_final'
        )
        
        model.graph.node.append(sigmoid_node)
        
        # 创建第二个输出（互补概率）
        prob_0_name = "prob_0"
        prob_1_name = "prob_1"
        
        # 计算 prob_0 = 1 - prob_1
        const_one = helper.make_tensor(
            name='const_one',
            data_type=onnx.TensorProto.FLOAT,
            dims=[1],
            vals=[1.0]
        )
        
        # 创建1 - prob_1的节点
        sub_node = helper.make_node(
            'Sub',
            inputs=['const_one', sigmoid_output_name],
            outputs=[prob_0_name],
            name='calculate_prob_0'
        )
        
        # 添加常量到图
        model.graph.initializer.append(const_one)
        
        # 添加节点
        model.graph.node.extend([sigmoid_node, sub_node])
        
        # 创建包含两个概率的输出
        concat_output_name = "probabilities"
        concat_node = helper.make_node(
            'Concat',
            inputs=[prob_0_name, prob_1_name],
            outputs=[concat_output_name],
            axis=1,
            name='concat_probabilities'
        )
        
        model.graph.node.append(concat_node)
        
        # 更新输出
        model.graph.output[0].name = concat_output_name
        # 需要更新输出类型
        for output in model.graph.output:
            if output.name == concat_output_name:
                output.type.tensor_type.shape.dim[1].dim_value = 2
        
        print("✅ 已添加Sigmoid和互补概率计算")
    
    # 保存模型
    onnx.save(model, output_path)
    print(f"✅ 二分类模型已保存: {output_path}")
    
    return output_path

def create_simple_classification_model():
    """创建一个简单的二分类模型（如果原始模型有问题）"""
    
    print("\n🛠️ 创建简单的二分类模型...")
    
    # 输入: [batch, 7]
    input_tensor = helper.make_tensor_value_info(
        'input', 
        onnx.TensorProto.FLOAT, 
        [1, 7]
    )
    
    # 输出: [batch, 2]
    output_tensor = helper.make_tensor_value_info(
        'output', 
        onnx.TensorProto.FLOAT, 
        [1, 2]
    )
    
    # 创建一个简单的线性层 + Softmax
    # 权重和偏置（随机初始化，实际应该从训练好的模型获取）
    weights = np.random.randn(7, 2).astype(np.float32)
    bias = np.random.randn(2).astype(np.float32)
    
    weights_tensor = numpy_helper.from_array(weights, name='weights')
    bias_tensor = numpy_helper.from_array(bias, name='bias')
    
    # 创建节点
    matmul_node = helper.make_node(
        'MatMul',
        inputs=['input', 'weights'],
        outputs=['matmul_output'],
        name='linear_layer'
    )
    
    add_node = helper.make_node(
        'Add',
        inputs=['matmul_output', 'bias'],
        outputs=['add_output'],
        name='add_bias'
    )
    
    softmax_node = helper.make_node(
        'Softmax',
        inputs=['add_output'],
        outputs=['output'],
        axis=1,
        name='softmax_output'
    )
    
    # 创建图
    graph = helper.make_graph(
        nodes=[matmul_node, add_node, softmax_node],
        name='SimplePlantGrowthModel',
        inputs=[input_tensor],
        outputs=[output_tensor],
        initializer=[weights_tensor, bias_tensor]
    )
    
    # 创建模型
    model = helper.make_model(
        graph,
        producer_name='PlantGrowthModelConverter',
        opset_imports=[helper.make_opsetid("", 11)]
    )
    
    # 保存模型
    output_path = "simple_plant_growth_model.onnx"
    onnx.save(model, output_path)
    
    print(f"✅ 简单模型已创建: {output_path}")
    print(f"  输入: [batch, 7]")
    print(f"  输出: [batch, 2] (概率)")
    
    return output_path

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        model_path = sys.argv[1]
    else:
        model_path = "plant_growth_model.onnx"
    
    print("=" * 80)
    print("🔧 ONNX模型修复工具")
    print("=" * 80)
    
    # 尝试修复现有模型
    try:
        fixed_model = fix_model_output(model_path)
        
        if fixed_model:
            print(f"\n✅ 模型修复完成: {fixed_model}")
        else:
            print("\n⚠️ 无法修复现有模型，创建新模型...")
            create_simple_classification_model()
            
    except Exception as e:
        print(f"❌ 修复失败: {e}")
        print("创建新的简单模型...")
        create_simple_classification_model()
    
    print("\n📋 下一步:")
    print("  1. 运行: python test_onnx_model_fixed.py")
    print("  2. 检查修复后的模型")
    print("  3. 在CubeMX中导入修复后的模型")