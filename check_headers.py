# check_headers.py
import os
import sys

def find_header_files(project_dir):
    """查找项目中所有的头文件"""
    header_files = {}
    
    for root, dirs, files in os.walk(project_dir):
        for file in files:
            if file.endswith('.h'):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, project_dir)
                header_files[file] = rel_path
                
                # 打印找到的头文件
                print(f"找到: {file} -> {rel_path}")
                
                # 检查是否有AI相关函数
                if file.endswith('.h') and ('ai' in file.lower() or 'network' in file.lower()):
                    print(f"  可能是AI头文件")
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if 'create' in content and 'run' in content:
                                print(f"  包含create/run函数")
                    except:
                        pass
    
    return header_files

def check_ai_functions(project_dir):
    """检查AI相关函数"""
    print("\n🔍 检查AI函数...")
    
    # 搜索.c和.h文件中的AI函数
    ai_functions = []
    
    for root, dirs, files in os.walk(project_dir):
        for file in files:
            if file.endswith(('.c', '.h')):
                full_path = os.path.join(root, file)
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                        # 查找AI相关函数
                        if 'ai_' in content or 'AI_' in content:
                            lines = content.split('\n')
                            for i, line in enumerate(lines):
                                if 'ai_' in line and '(' in line:
                                    print(f"{file}:{i+1}: {line.strip()}")
                                    ai_functions.append((file, i+1, line.strip()))
                except Exception as e:
                    print(f"读取文件 {file} 失败: {e}")
    
    return ai_functions

def generate_correct_includes(project_dir):
    """生成正确的头文件包含"""
    print("\n📝 生成正确的包含语句...")
    
    includes = []
    
    # 检查X-CUBE-AI目录
    xcube_path = os.path.join(project_dir, "X-CUBE-AI")
    if os.path.exists(xcube_path):
        print("找到X-CUBE-AI目录")
        
        # 检查App目录
        app_path = os.path.join(xcube_path, "App")
        if os.path.exists(app_path):
            for file in os.listdir(app_path):
                if file.endswith('.h'):
                    print(f"  App/{file}")
                    includes.append(f'#include "app_x-cube-ai.h"')
    
    # 检查Middlewares目录
    middleware_path = os.path.join(project_dir, "Middlewares", "ST", "AI", "Inc")
    if os.path.exists(middleware_path):
        print("找到AI Middleware头文件")
        for file in os.listdir(middleware_path):
            if file.endswith('.h'):
                print(f"  Middlewares/ST/AI/Inc/{file}")
                includes.append(f'#include "{file}"')
    
    return includes

if __name__ == "__main__":
    project_dir = input("请输入项目目录路径: ").strip()
    if not project_dir:
        project_dir = "."
    
    print(f"检查项目目录: {project_dir}")
    print("=" * 60)
    
    headers = find_header_files(project_dir)
    functions = check_ai_functions(project_dir)
    includes = generate_correct_includes(project_dir)
    
    print("\n" + "=" * 60)
    print("📋 建议的包含语句:")
    print("=" * 60)
    
    for inc in includes:
        print(inc)
    
    if 'app_x-cube-ai.h' in headers:
        print('\n✅ 应该包含: #include "app_x-cube-ai.h"')
    
    if 'ai_platform.h' in headers:
        print('✅ 应该包含: #include "ai_platform.h"')