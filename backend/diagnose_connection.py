#!/usr/bin/env python3
"""
诊断连接问题的脚本
"""
import asyncio
import os
import sys
import logging
import time

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 设置环境变量启用模拟器
os.environ["USE_ROBOT_SIMULATOR"] = "true"

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.ssh_service import ssh_service


async def diagnose_connection():
    """诊断连接问题"""
    print("=== 连接诊断工具 ===\n")
    
    # 1. 检查模拟器模式
    print(f"1. 模拟器模式: {'已启用' if ssh_service.use_simulator else '已禁用'}")
    
    if not ssh_service.use_simulator:
        print("   ⚠️ 模拟器未启用，将尝试真实SSH连接")
    else:
        print("   ✓ 使用模拟器进行测试")
    
    # 2. 测试基本连接
    print("\n2. 测试基本连接...")
    
    robot_id = "diagnose_test"
    host = "192.168.1.100"
    port = 22
    username = "leju"
    password = "test123"
    
    start_time = time.time()
    
    try:
        success, error = await ssh_service.connect(robot_id, host, port, username, password)
        elapsed = time.time() - start_time
        
        print(f"   连接结果: {'成功' if success else '失败'}")
        if error:
            print(f"   错误信息: {error}")
        print(f"   耗时: {elapsed:.2f}秒")
        
        if elapsed > 2:
            print("   ⚠️ 连接时间过长")
        
        if success:
            # 3. 测试命令执行
            print("\n3. 测试命令执行...")
            
            cmd_start = time.time()
            success, stdout, stderr = await ssh_service.execute_command(
                robot_id,
                "cat /etc/robot_info.json"
            )
            cmd_elapsed = time.time() - cmd_start
            
            print(f"   执行结果: {'成功' if success else '失败'}")
            print(f"   耗时: {cmd_elapsed:.2f}秒")
            
            if success and stdout:
                print(f"   输出预览: {stdout[:100]}...")
            
            # 4. 测试断开连接
            print("\n4. 测试断开连接...")
            
            disc_start = time.time()
            disconnected = await ssh_service.disconnect(robot_id)
            disc_elapsed = time.time() - disc_start
            
            print(f"   断开结果: {'成功' if disconnected else '失败'}")
            print(f"   耗时: {disc_elapsed:.2f}秒")
            
    except Exception as e:
        print(f"   ✗ 发生异常: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # 5. 测试并发连接
    print("\n5. 测试并发连接...")
    
    async def connect_robot(index):
        robot_id = f"robot_{index}"
        try:
            start = time.time()
            success, error = await ssh_service.connect(
                robot_id,
                f"192.168.1.{100 + index}",
                22,
                "leju",
                f"test{index}"
            )
            elapsed = time.time() - start
            
            if success:
                await ssh_service.disconnect(robot_id)
            
            return index, success, elapsed
        except Exception as e:
            return index, False, 0
    
    # 并发连接5个设备
    tasks = [connect_robot(i) for i in range(5)]
    results = await asyncio.gather(*tasks)
    
    success_count = sum(1 for _, success, _ in results if success)
    avg_time = sum(elapsed for _, _, elapsed in results) / len(results)
    
    print(f"   成功连接: {success_count}/5")
    print(f"   平均耗时: {avg_time:.2f}秒")
    
    # 6. 检查事件循环
    print("\n6. 事件循环状态...")
    
    loop = asyncio.get_event_loop()
    print(f"   运行中: {loop.is_running()}")
    print(f"   已关闭: {loop.is_closed()}")
    
    # 7. 建议
    print("\n7. 诊断建议:")
    
    if ssh_service.use_simulator:
        print("   ✓ 模拟器模式正常")
        print("   - 如果连接仍然卡住，检查是否有其他阻塞操作")
        print("   - 确保所有模拟器方法都在线程池中执行")
    else:
        print("   - 如需测试，请设置 USE_ROBOT_SIMULATOR=true")
        print("   - 真实SSH连接需要确保网络通畅")
    
    print("\n诊断完成!")


if __name__ == "__main__":
    asyncio.run(diagnose_connection())