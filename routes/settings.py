"""
设置路由

/api/settings 路由保留在 main.py 中，因为需要访问全局变量进行热更新。
"""

from typing import Dict, Any
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()

# /api/settings 路由保留在 main.py 中
