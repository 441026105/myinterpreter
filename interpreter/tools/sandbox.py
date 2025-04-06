import os
import docker
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

class SandboxConfig:
    """沙箱安全配置项"""
    def __init__(self):
        # 默认资源限制
        self.cpu_quota = 100000  # 单位微秒 (100ms)
        self.memory_limit = '128m'
        self.timeout = 30  # 秒
        self.readonly_filesystem = False
        self.allowed_ports = []  # 允许的网络端口
        self.volumes = {
            str(Path.cwd()): {
                'bind': '/workspace',
                'mode': 'ro'  # 默认只读挂载
            }
        }

class SandboxManager:
    """沙箱执行管理器"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.client = docker.from_env()
            cls._instance.config = SandboxConfig()
        return cls._instance

    async def execute(self, command: str, **kwargs) -> Dict[str, Any]:
        """在沙箱中执行命令"""
        container = None
        try:
            import base64
            encoded_cmd = base64.b64encode(command.encode()).decode()
            exec_cmd = f"echo {encoded_cmd} | base64 -d | sh -e"
            # 创建容器配置
            container_config = {
                'image': 'python:3.11-slim',
                'command': ["sh","-c",command],
                'volumes': self.config.volumes,
                'working_dir': '/workspace',
                'environment': {
                    'DEBIAN_FRONTEND': 'noninteractive',
                    'NONINTERACTIVE': '1'
                },
                'mem_limit': self.config.memory_limit,
                'cpu_quota': self.config.cpu_quota,
                'network_mode': 'none' if not self.config.allowed_ports else 'bridge',
                'read_only': self.config.readonly_filesystem,
                'detach': True,
                'stdout':True,
               'stderr':True
            }

            # 创建容器
            container = await asyncio.to_thread(
                self.client.containers.run,
                **container_config
            )

            exit_code = await asyncio.wait_for(
                asyncio.to_thread(
                    container.wait,
                    timeout=self.config.timeout
                ),
                timeout=self.config.timeout + 5
            )

            logs_bytes = await asyncio.to_thread(container.logs,stdout=True,stderr=True)  # 先获取字节数据
            logs = logs_bytes.decode('utf-8', errors='replace')  # 再解码字符串

            return {
                "exit_code": exit_code['StatusCode'],
                "output": logs,
                "stats": await asyncio.to_thread(container.stats, stream=False)
            }

        except asyncio.TimeoutError:
            if container:
                await asyncio.to_thread(container.stop)
            return {"error": "Execution timeout"}
        except Exception as e:
            print(str(e))
            return {"error": str(e)}
        finally:
            if container:
                await asyncio.to_thread(container.remove)