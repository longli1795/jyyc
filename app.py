"""
重构后的应用启动文件
"""
import os
import signal
import sys
from app.main import run_app

def signal_handler(sig, frame):
    """优雅关闭信号处理器"""
    print('\n正在关闭服务器...')
    sys.exit(0)

if __name__ == '__main__':
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        app = run_app()
        
        # 生产模式配置
        debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
        host = os.getenv('FLASK_HOST', '0.0.0.0')
        port = int(os.getenv('FLASK_PORT', '8080'))
        
        print(f"启动服务器: http://{host}:{port}")
        print("按 Ctrl+C 停止服务器")
        
        # 使用更稳定的配置启动
        app.run(
            debug=debug_mode, 
            host=host, 
            port=port,
            threaded=True,  # 启用多线程
            use_reloader=False,  # 在生产环境中禁用重载器
            use_debugger=debug_mode  # 只在调试模式下启用调试器
        )
        
    except OSError as e:
        if "WinError 10038" in str(e):
            print("检测到Windows套接字错误，这通常是正常的服务器关闭过程。")
        else:
            print(f"服务器启动失败: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n服务器已停止")
        sys.exit(0)
    except Exception as e:
        print(f"应用启动失败: {e}")
        sys.exit(1) 