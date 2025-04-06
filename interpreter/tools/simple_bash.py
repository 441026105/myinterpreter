import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import ClassVar, Literal

from anthropic.types.beta import BetaToolBash20241022Param

from .base import BaseAnthropicTool, CLIResult, ToolError, ToolResult
from .sandbox import SandboxManager  # 新增导入
import docker  # 新增docker库依赖

# print("Using simple bash tool")


class BashTool(BaseAnthropicTool):
    """A tool that executes bash commands in Docker container and returns their output."""

    name: ClassVar[Literal["bash"]] = "bash"
    api_type: ClassVar[Literal["bash_20241022"]] = "bash_20241022"

    # 新增容器配置
    _client = docker.from_env()
    _container_image = "python:3.11-slim"  # 基础镜像
    _container_volumes = {os.getcwd(): {'bind': '/app', 'mode': 'rw'}}  # 挂载当前目录

    def to_params(self) -> BetaToolBash20241022Param:
        return {
            "type": self.api_type,
            "name": self.name,
        }


    async def __call__(self, command: str | None = None, **kwargs):
        if not command:
            raise ToolError("no command provided")
        
        # 获取沙箱管理器实例
        sandbox = SandboxManager()
        result = await sandbox.execute(command)

        if 'error' in result:
            print(result['error'])
            return ToolResult(error=result['error'])
            
        # 记录安全日志
        self._log_execution(command, result)
        
        # 打印并返回结果
        print(result['output'], end="", flush=True)
        return CLIResult(output=result['output'])

    def _log_execution(self, command: str, result: dict):
        """记录安全日志"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'command': command,
            'exit_code': result.get('exit_code'),
            'resource_usage': result.get('stats', {}),
            'security_checks': []
        }
        # 这里可以添加安全检查逻辑
        if result.get('exit_code') != 0:
            log_entry['security_checks'].append('Non-zero exit code')
        
        # 保存日志到文件
        Path('security.log').open("a").write(json.dumps(log_entry) + '\n')
