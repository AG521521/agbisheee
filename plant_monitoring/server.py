#!/usr/bin/env python3
"""
智能植物生长监测系统 - 服务器端
最简版本，只负责接收STM32数据
"""

import socket
import threading
import json
import time
import datetime
import sqlite3
import os

# 配置
HOST = '0.0.0.0'  # 监听所有接口
PORT = 8080        # 监听端口
DB_FILE = "plant_data.db"

print("=" * 60)
print("🌿 智能植物监测系统 - 数据接收服务器")
print("=" * 60)

class PlantServer:
    def __init__(self):
        self.server_socket = None
        self.running = False
        self.clients = {}
        self.start_time = time.time()
        
        # 获取本机IP
        self.local_ip = self.get_local_ip()
        
        # 初始化数据库
        self.init_database()
        
        print(f"📡 服务器IP: {self.local_ip}")
        print(f"🚪 监听端口: {PORT}")
        print(f"💾 数据库: {DB_FILE}")
        print("=" * 60)
        print("等待STM32设备连接...")
        print("=" * 60)
    
    def get_local_ip(self):
        """获取本地IP地址"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def init_database(self):
        """初始化SQLite数据库"""
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            # 创建设备信息表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT,
                    ip_address TEXT,
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP,
                    status TEXT
                )
            ''')
            
            # 创建设备数据表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sensor_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    temperature REAL,
                    humidity REAL,
                    soil_moisture REAL,
                    light_intensity REAL,
                    health_score REAL,
                    growth_status INTEGER
                )
            ''')
            
            conn.commit()
            conn.close()
            print("✅ 数据库初始化完成")
            
        except Exception as e:
            print(f"❌ 数据库错误: {e}")
    
    def save_to_database(self, device_id, ip_address, data):
        """保存数据到数据库"""
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            # 更新设备信息
            cursor.execute('''
                INSERT OR REPLACE INTO devices (device_id, ip_address, last_seen, status)
                VALUES (?, ?, ?, ?)
            ''', (device_id, ip_address, datetime.datetime.now(), 'online'))
            
            # 保存传感器数据
            cursor.execute('''
                INSERT INTO sensor_data 
                (device_id, temperature, humidity, soil_moisture, light_intensity, health_score, growth_status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                device_id,
                data.get('temperature', 0.0),
                data.get('humidity', 0.0),
                data.get('soil_moisture', 0.0),
                data.get('light_intensity', 0.0),
                data.get('health_score', 0.0),
                data.get('growth_status', 0)
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"❌ 保存数据失败: {e}")
            return False
    
    def handle_client(self, client_socket, client_address):
        """处理客户端连接"""
        client_ip = client_address[0]
        print(f"📱 新设备连接: {client_ip}")
        
        try:
            # 设置超时时间
            client_socket.settimeout(30.0)
            
            while self.running:
                try:
                    # 接收数据
                    data = client_socket.recv(1024)
                    if not data:
                        print(f"📴 设备断开: {client_ip}")
                        break
                    
                    # 尝试解码为字符串
                    try:
                        message = data.decode('utf-8', errors='ignore').strip()
                        
                        # 查找JSON数据
                        start = message.find('{')
                        end = message.rfind('}')
                        
                        if start != -1 and end != -1:
                            json_str = message[start:end+1]
                            
                            try:
                                # 解析JSON
                                json_data = json.loads(json_str)
                                self.process_data(client_socket, client_ip, json_data)
                            except json.JSONDecodeError:
                                print(f"⚠️  无效JSON: {json_str[:50]}...")
                        else:
                            # 不是JSON，可能是AT命令响应
                            if message:
                                print(f"📨 收到文本: {message[:100]}")
                        
                    except Exception as e:
                        print(f"⚠️  解码错误: {e}")
                        print(f"原始数据: {data[:100]}...")
                
                except socket.timeout:
                    # 超时但保持连接
                    continue
                    
                except Exception as e:
                    print(f"❌ 接收错误: {e}")
                    break
        
        except Exception as e:
            print(f"❌ 处理客户端异常: {e}")
        
        finally:
            # 清理连接
            try:
                client_socket.close()
            except:
                pass
            
            # 从客户端列表中移除
            for dev_id, sock in list(self.clients.items()):
                if sock == client_socket:
                    del self.clients[dev_id]
                    break
            
            print(f"🧹 清理连接: {client_ip}")
    
    def process_data(self, client_socket, client_ip, json_data):
        """处理接收到的JSON数据"""
        try:
            # 提取设备ID和数据
            device_id = json_data.get('device', f'STM32_{client_ip}')
            
            # 如果是传感器数据
            if 'temperature' in json_data or 'humidity' in json_data:
                # 保存到数据库
                self.save_to_database(device_id, client_ip, json_data)
                
                # 显示数据
                print(f"📊 传感器数据 - {device_id}:")
                if 'temperature' in json_data:
                    print(f"   温度: {json_data['temperature']}°C")
                if 'humidity' in json_data:
                    print(f"   湿度: {json_data['humidity']}%")
                if 'soil_moisture' in json_data:
                    print(f"   土壤湿度: {json_data['soil_moisture']}%")
                if 'light_intensity' in json_data:
                    print(f"   光照: {json_data['light_intensity']}%")
                if 'health_score' in json_data:
                    print(f"   健康评分: {json_data['health_score']}")
                
                # 发送确认响应
                response = {
                    'status': 'ok',
                    'message': '数据接收成功',
                    'timestamp': time.time()
                }
                
                self.send_response(client_socket, response)
            
            # 如果是心跳包
            elif json_data.get('type') == 'heartbeat':
                response = {
                    'status': 'alive',
                    'timestamp': time.time()
                }
                self.send_response(client_socket, response)
                print(f"💓 心跳: {device_id}")
            
            else:
                print(f"📦 其他数据: {json_data}")
                
                # 发送通用响应
                response = {
                    'status': 'received',
                    'timestamp': time.time()
                }
                self.send_response(client_socket, response)
        
        except Exception as e:
            print(f"❌ 处理数据错误: {e}")
            print(f"原始数据: {json_data}")
    
    def send_response(self, client_socket, response):
        """发送响应给客户端"""
        try:
            response_json = json.dumps(response)
            client_socket.sendall(response_json.encode('utf-8'))
        except Exception as e:
            print(f"❌ 发送响应失败: {e}")
    
    def start(self):
        """启动服务器"""
        try:
            # 创建socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((HOST, PORT))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)
            
            self.running = True
            
            print(f"✅ 服务器启动成功！")
            print(f"   监听: {HOST}:{PORT}")
            print(f"   实际地址: {self.local_ip}:{PORT}")
            
            # 启动状态监控线程
            threading.Thread(target=self.status_monitor, daemon=True).start()
            
            # 主循环
            while self.running:
                try:
                    # 等待客户端连接
                    client_socket, client_address = self.server_socket.accept()
                    
                    # 启动新线程处理客户端
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, client_address),
                        daemon=True
                    )
                    client_thread.start()
                    
                except socket.timeout:
                    # 超时，继续等待
                    continue
                    
                except Exception as e:
                    if self.running:
                        print(f"❌ 接受连接错误: {e}")
                    break
        
        except Exception as e:
            print(f"❌ 服务器启动失败: {e}")
        
        finally:
            self.stop()
    
    def status_monitor(self):
        """状态监控线程"""
        while self.running:
            time.sleep(30)
            
            uptime = int(time.time() - self.start_time)
            
            # 获取数据数量
            try:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM sensor_data")
                data_count = cursor.fetchone()[0]
                conn.close()
            except:
                data_count = 0
            
            print(f"📈 状态 - 运行: {uptime}秒 | 数据: {data_count}条 | 连接: {len(self.clients)}设备")
    
    def stop(self):
        """停止服务器"""
        self.running = False
        
        # 关闭所有客户端连接
        for device_id, client_socket in list(self.clients.items()):
            try:
                client_socket.close()
            except:
                pass
        
        # 关闭服务器socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        print("🛑 服务器已停止")

# 命令行测试工具
def test_connection():
    """测试服务器连接"""
    print("\n🔧 连接测试工具")
    print("=" * 40)
    
    server_ip = input("输入服务器IP (默认: 10.87.12.57): ").strip()
    if not server_ip:
        server_ip = "10.87.12.57"
    
    port = input("输入端口 (默认: 8080): ").strip()
    if not port:
        port = 8080
    else:
        port = int(port)
    
    try:
        # 创建socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        
        print(f"🔄 连接 {server_ip}:{port}...")
        sock.connect((server_ip, port))
        
        print("✅ 连接成功！")
        
        # 发送测试数据
        test_data = {
            'device': 'test_device',
            'temperature': 25.5,
            'humidity': 65.2,
            'timestamp': time.time()
        }
        
        sock.sendall(json.dumps(test_data).encode('utf-8'))
        print(f"📤 发送测试数据: {test_data}")
        
        # 接收响应
        response = sock.recv(1024)
        if response:
            print(f"📥 收到响应: {response.decode('utf-8')}")
        
        sock.close()
        print("✅ 测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")

def view_database():
    """查看数据库内容"""
    print("\n📊 数据库内容")
    print("=" * 40)
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 查看表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"📋 数据表: {[t[0] for t in tables]}")
        
        # 查看设备数据
        print("\n📱 设备列表:")
        cursor.execute("SELECT device_id, ip_address, last_seen FROM devices ORDER BY last_seen DESC")
        devices = cursor.fetchall()
        for device in devices:
            print(f"  {device[0]} - IP: {device[1]} - 最后在线: {device[2]}")
        
        # 查看传感器数据
        print("\n📈 最新传感器数据 (最近10条):")
        cursor.execute('''
            SELECT device_id, timestamp, temperature, humidity, soil_moisture, light_intensity 
            FROM sensor_data 
            ORDER BY timestamp DESC 
            LIMIT 10
        ''')
        data = cursor.fetchall()
        
        for row in data:
            print(f"  {row[0]} - {row[1]}: 温度:{row[2]}°C 湿度:{row[3]}% 土壤:{row[4]}% 光照:{row[5]}%")
        
        # 统计
        cursor.execute("SELECT COUNT(*) FROM sensor_data")
        total = cursor.fetchone()[0]
        print(f"\n📊 总计: {total} 条记录")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 查看数据库失败: {e}")

def main():
    """主函数"""
    print("\n🌿 智能植物监测系统 - 主菜单")
    print("=" * 60)
    print("1. 启动服务器")
    print("2. 测试连接")
    print("3. 查看数据库")
    print("4. 退出")
    print("=" * 60)
    
    choice = input("请选择 (1-4): ").strip()
    
    if choice == '1':
        # 启动服务器
        server = PlantServer()
        
        try:
            server.start()
        except KeyboardInterrupt:
            print("\n🛑 收到停止信号...")
            server.stop()
        except Exception as e:
            print(f"❌ 服务器异常: {e}")
    
    elif choice == '2':
        # 测试连接
        test_connection()
        input("\n按Enter键返回主菜单...")
        main()
    
    elif choice == '3':
        # 查看数据库
        view_database()
        input("\n按Enter键返回主菜单...")
        main()
    
    elif choice == '4':
        print("👋 再见！")
    
    else:
        print("❌ 无效选择")
        input("\n按Enter键返回主菜单...")
        main()

if __name__ == "__main__":
    # 创建数据库目录
    os.makedirs(os.path.dirname(DB_FILE) if os.path.dirname(DB_FILE) else '.', exist_ok=True)
    
    # 运行主函数
    main()