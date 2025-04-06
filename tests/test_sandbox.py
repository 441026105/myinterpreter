import docker
import pytest

from interpreter.tools.sandbox import SandboxManager, SandboxConfig


@pytest.fixture
def sandbox_manager():
    return SandboxManager()


@pytest.fixture
def docker_client():
    return docker.from_env()


# 单元测试
class TestSandboxUnit:
    def test_singleton_pattern(self):
        manager1 = SandboxManager()
        manager2 = SandboxManager()
        assert manager1 is manager2

    def test_config_defaults(self):
        config = SandboxConfig()
        assert config.memory_limit == '128m'
        assert config.timeout == 30


# 集成测试
class TestSandboxIntegration:
    @pytest.mark.asyncio
    async def test_container_lifecycle(self, sandbox_manager, docker_client):
        # 测试容器创建
        await sandbox_manager._ensure_container()
        container = sandbox_manager.container
        assert container.status in ('running', 'created')

        # 测试命令执行
        result = await sandbox_manager.execute("echo 'hello'")
        assert result['exit_code'] == 0
        assert 'hello' in result['output']

        # 测试容器清理
        sandbox_manager.sync_cleanup()
        with pytest.raises(docker.errors.NotFound):
            docker_client.containers.get(container.id)

    @pytest.mark.asyncio
    async def test_cleanup_on_exception(self, sandbox_manager, docker_client):
        try:
            await sandbox_manager.execute("invalid_command")
        except:
            pass

        # 验证异常后容器依然存在（未意外清理）
        assert sandbox_manager.container is not None


# 修改配置文件，设置内存限制为6M，测试内存限制是否生效
@pytest.mark.asyncio
async def test_high_memory_usage(sandbox_manager):
    result = await sandbox_manager.execute("python -c 's = \" \" * 10_000_000'")

    assert result['exit_code'] == 137
