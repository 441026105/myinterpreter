# 完成说明
## 题⽬1：实现代码执⾏沙箱安全模式

- 沙箱模块：
  - interpreter/tools/sandbox.py
  - 通过docker容器化隔离代码、命令执行环境
  - 保持原有功能，不影响其他正常功能
- 沙箱配置：configs.py
  - 可配置docker镜像，限制cpu、内存、网络、超时执行实践等等
- 测试模块：
  - tests/test_sandbox.py
- 启动说明
  1. poetry install 
  2. docker pull python:3.11-slim
  3. interpreter --model="openai/i" --api-key="x" --api-base="https://api.openinterpreter.com/v0"
