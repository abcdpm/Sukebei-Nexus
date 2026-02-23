# API 数据模型验证

from pydantic import BaseModel
from typing import List

# --- API 数据模型验证 ---
class SettingsDTO(BaseModel):
    qb_host: str
    qb_user: str
    qb_pass: str
    rss_url: str
    block_prefixes: str
    rss_interval: int

class DownloadRequest(BaseModel):
    items: List[dict]