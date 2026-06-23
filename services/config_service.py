"""
配置服务层

封装配置管理的业务逻辑。
"""

from typing import Dict, Any

from repositories.base import ConfigRepository


class ConfigService:
    """配置服务"""

    def __init__(self, repo: ConfigRepository):
        self.repo = repo

    async def get(self, key: str, default: str = "") -> str:
        """获取配置值"""
        return await self.repo.get(key, default)

    async def set(self, key: str, value: str) -> None:
        """设置配置值"""
        await self.repo.set(key, value)

    async def get_all(self) -> Dict[str, str]:
        """获取所有配置"""
        return await self.repo.get_all()
