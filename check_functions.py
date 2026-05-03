# check_functions.py
import os

def check_header_file(filepath):
    """检查头文件中的函数定义"""
    print(f"🔍 检查文件: {filepath}")
    
    if not os.path.exists(filepath):
        print(f"❌ 文件不存在: {filepath}")
        return
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
        # 查找create函数
        if 'ai_plant_growth1_create' in content:
            print("\n📝 ai_plant_growth1_create 函数签名:")
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'ai_plant_growth1_create' in line:
                    # 打印这一行和接下来的几行
                    for j in range(max(0, i-2), min(len(lines), i+3)):
                        print(f"  {j+1}: {lines[j]}")
                    break
        
        # 查找run函数
        if 'ai_plant_growth1_run' in content:
            print("\n📝 ai_plant_growth1_run 函数签名:")
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'ai_plant_growth1_run' in line:
                    for j in range(max(0, i-2), min(len(lines), i+3)):
                        print(f"  {j+1}: {lines[j]}")
                    break
        
        # 查找AI_OK定义
        if 'AI_OK' in content:
            print("\n📝 AI_OK 定义:")
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'AI_OK' in line and '#define' in line:
                    print(f"  {i+1}: {line}")

# 检查文件
check_header_file("Core/Inc/plant_growth1.h")
check_header_file("Middlewares/ST/AI/Inc/ai_platform.h")