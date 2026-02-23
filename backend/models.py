from sqlalchemy import Column, String, Integer, DateTime, text
import datetime
from database import Base, engine

class DownloadHistory(Base):
    __tablename__ = "download_history"
    code = Column(String, primary_key=True, index=True)
    title = Column(String)
    torrent_url = Column(String)

class AppSettings(Base):
    __tablename__ = "app_settings"
    id = Column(Integer, primary_key=True, index=True)
    qb_host = Column(String, default="http://192.168.0.x:8080")
    qb_user = Column(String, default="admin")
    qb_pass = Column(String, default="adminadmin")
    rss_url = Column(String, default="https://sukebei.nyaa.si/?page=rss&u=offkab")
    block_prefixes = Column(String, default="XB-,MD-,JV-") # 需求3: 屏蔽前缀
    rss_interval = Column(Integer, default=15) # 需求3: 定时间隔(分钟)

class MetadataCache(Base):
    __tablename__ = "metadata_cache"
    code = Column(String, primary_key=True, index=True)
    cover_path = Column(String)
    samples_json = Column(String)

# 新增：用于存储后台抓取的 RSS 数据，实现极速翻页
class RssItem(Base):
    __tablename__ = "rss_items"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String, unique=True, index=True)
    title = Column(String)
    link = Column(String)
    pub_date = Column(DateTime, default=datetime.datetime.utcnow)

Base.metadata.create_all(bind=engine)

# 自动数据库升级与自愈修复 (将每条语句独立分离，防止一个错误阻断另一个)
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE app_settings ADD COLUMN block_prefixes VARCHAR DEFAULT 'XB-,MD-,JV-'"))
        conn.commit()
except Exception:
    pass

try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE app_settings ADD COLUMN rss_interval INTEGER DEFAULT 15"))
        conn.commit()
except Exception:
    pass

try:
    with engine.connect() as conn:
        # 核心修复：清理掉之前因为网络超时导致没有抓到详细图的坏缓存
        conn.execute(text("DELETE FROM metadata_cache WHERE samples_json = '[]' OR samples_json IS NULL"))
        conn.commit()
except Exception:
    pass