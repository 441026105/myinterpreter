import docker
import asyncio
from pathlib import Path
from typing import Dict, Any
import atexit
import docker


class SandboxConfig:
    """沙箱安全配置项"""

    def __init__(self):
        self.image = 'python:3.11-slim'
        self.cpu_period = 100000
        self.cpu_quota = 100000
        self.memory_limit = '128m'
        self.timeout = 30  # 秒
        self.readonly_filesystem = False
        self.network_mode = 'bridge'
        self.volumes = {
            str(Path.cwd()): {
                'bind': '/workspace',
                'mode': 'ro'
            }
        }
        self.load_config()

    def load_config(self):
        import yaml
        project_root = Path(__file__).resolve().parent.parent.parent  

        with open(project_root/'configs.yaml', 'r') as f:
            sandbox_config = yaml.safe_load(f).get("sandbox")
            for item in sandbox_config:
                setattr(self, item, sandbox_config[item])


class SandboxManager:
    """沙箱执行管理器（单容器复用版）"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.client = docker.from_env()
            cls._instance.config = SandboxConfig()
            cls._instance.container = None  # 持久化容器实例
            # 注册退出清理函数
            atexit.register(cls._instance.sync_cleanup)  # 改为注册同步方法
        return cls._instance

    async def _ensure_container(self):
        """确保容器已创建并运行"""
        if self.container and self.container.status == 'running':
            return

        # 清理旧容器
        if self.container:
            await asyncio.to_thread(self.container.remove, force=True)
        # 创建新容器配置
        container_config = {
            'image': self.config.image,
            'command': ['tail', '-f', '/dev/null'],
            'working_dir': '/workspace',
            'environment': {
                'DEBIAN_FRONTEND': 'noninteractive',
                'NONINTERACTIVE': '1'
            },
            'detach': True,
            'volumes': self.config.volumes,
            # 假设 volumes 格式正确，如 {'/host/path': {'bind': '/container/path', 'mode': 'rw'}}
            'mem_limit': self.config.memory_limit,
            'cpu_period': self.config.cpu_period,
            'cpu_quota': self.config.cpu_quota,
            'network_mode': self.config.network_mode,
            'read_only': self.config.readonly_filesystem
        }

        # 创建容器
        self.container = await asyncio.to_thread(
            self.client.containers.run,
            **container_config
        )

    async def execute(self, command: str) -> Dict[str, Any]:
        """在持久化容器中执行命令"""
        try:
            # 确保容器就绪
            await self._ensure_container()
            container = self.client.containers.get(self.container.id)

            # 执行命令
            exec_result = await asyncio.wait_for(asyncio.to_thread(
                self.container.exec_run,
                cmd=['sh', '-c', command],
                demux=True,
                environment={
                    'DEBIAN_FRONTEND': 'noninteractive',
                    'NONINTERACTIVE': '1'
                }
            ), timeout=self.config.timeout)
            output = ""
            for item in exec_result.output:
                output += item.decode() if item is not None else ""

            return {
                "exit_code": exec_result.exit_code,
                "output": output,
                "stats": await asyncio.to_thread(container.stats, stream=False)
            }
        except Exception as e:
            return {"error": f"执行失败: {str(e)}"}

    def sync_cleanup(self):
        """同步清理方法供atexit使用"""
        if self.container:
            # 直接使用同步方法移除容器
            try:
                self.container.remove(force=True)
            except Exception as e:
                pass  # 忽略已关闭的容器
            self.container = None
