import os
import re
import json
import feedparser
import httpx
import asyncio
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from qbittorrentapi import Client

# --- 数据库配置 ---
DATA_DIR = "./data"
IMG_DIR = "./data/img" # 需求1: 图片缓存目录
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATA_DIR}/nexus.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

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

class MetadataCache(Base):
    __tablename__ = "metadata_cache"
    code = Column(String, primary_key=True, index=True)
    cover_path = Column(String)
    samples_json = Column(String)

Base.metadata.create_all(bind=engine)

# 自动数据库升级与自愈修复
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE app_settings ADD COLUMN block_prefixes VARCHAR DEFAULT 'XB-,MD-,JV-'"))
        conn.commit()
except Exception:
    pass

try:
    with engine.connect() as conn:
        # 核心修复：清理掉之前因为网络超时导致没有抓到详细图的坏缓存，让它们重新满血复活！
        conn.execute(text("DELETE FROM metadata_cache WHERE samples_json = '[]' OR samples_json IS NULL"))
        conn.commit()
except Exception:
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(title="Sukebei-Nexus API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# 挂载本地图片目录
app.mount("/img", StaticFiles(directory=IMG_DIR), name="img")

# --- 请求伪装 Headers，防止被目标网站拦截 ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# --- 1. 设置 API ---
class SettingsDTO(BaseModel):
    qb_host: str
    qb_user: str
    qb_pass: str
    rss_url: str
    block_prefixes: str

@app.get("/api/settings")
def get_settings(db: Session = Depends(get_db)):
    setting = db.query(AppSettings).first()
    if not setting:
        setting = AppSettings()
        db.add(setting)
        db.commit()
    return setting

@app.post("/api/settings")
def save_settings(config: SettingsDTO, db: Session = Depends(get_db)):
    setting = db.query(AppSettings).first()
    if not setting:
        setting = AppSettings(**config.dict())
        db.add(setting)
    else:
        setting.qb_host = config.qb_host
        setting.qb_user = config.qb_user
        setting.qb_pass = config.qb_pass
        setting.rss_url = config.rss_url
        setting.block_prefixes = config.block_prefixes
    db.commit()
    return {"status": "success"}

@app.post("/api/qb/test")
def test_qb_connection(config: SettingsDTO):
    try:
        qbt_client = Client(host=config.qb_host, username=config.qb_user, password=config.qb_pass)
        qbt_client.auth_log_in()
        return {"status": "success", "message": f"连接成功！qB版本: {qbt_client.app.version}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"连接失败: {str(e)}")

# --- 2. RSS 解析与正则修复 ---
@app.get("/api/rss")
def get_rss(page: int = 1, limit: int = 24, db: Session = Depends(get_db)):
    setting = db.query(AppSettings).first()
    base_url = setting.rss_url if setting and setting.rss_url else "https://sukebei.nyaa.si/?page=rss&u=offkab"
    if page > 1:
        base_url += f"&p={page}"
        
    feed = feedparser.parse(base_url)
    downloaded_codes = [h.code for h in db.query(DownloadHistory).all()]
    
    # 提取屏蔽前缀列表
    block_prefixes = []
    if setting and setting.block_prefixes:
        block_prefixes = [p.strip().upper() for p in setting.block_prefixes.split(',') if p.strip()]

    # 先过滤出有效的条目，彻底踢出被屏蔽的番号
    filtered_entries = []
    for entry in feed.entries:
        title = entry.title
        match_fc2 = re.search(r'FC2[^\d]*(\d{5,8})', title, re.IGNORECASE)
        match_date = re.search(r'(\d{6}[-_]\d{3}(?:[-_][A-Za-z]+)?)', title, re.IGNORECASE)
        match_normal = re.search(r'\b(?!(?:PPV|FC2)\-)([A-Za-z]{2,8}[-_]\d{2,5})\b', title, re.IGNORECASE)
        
        code = "UNKNOWN"
        if match_fc2:
            code = f"FC2-PPV-{match_fc2.group(1)}"
        elif match_date:
            code = match_date.group(1).upper()
        elif match_normal:
            code = match_normal.group(1).upper()
            
        # 如果番号匹配屏蔽前缀，直接丢弃
        if any(code.startswith(bp) for bp in block_prefixes):
            continue
            
        filtered_entries.append({
            "title": title, "link": entry.link, "code": code,
            "is_downloaded": code in downloaded_codes
        })

    total_items = len(filtered_entries)
    total_pages = (total_items + limit - 1) // limit if total_items > 0 else 1
    
    start = (page - 1) * limit
    end = start + limit
    
    return {"total_pages": total_pages, "page": page, "data": filtered_entries[start:end]}

# 工具函数：并发安全的极速图片下载
async def download_image(client, url, filepath):
    if not url: return False
    if url.startswith('//'): url = 'https:' + url # 修复 FC2 相对路径
    if os.path.exists(filepath): return True # 本地秒开
    try:
        resp = await client.get(url, cookies={'age_check_done': '1'}, follow_redirects=True, timeout=10.0)
        if resp.status_code == 200:
            # 放入后台线程写入，绝对不阻塞异步循环
            def write_file():
                with open(filepath, 'wb') as f:
                    f.write(resp.content)
            await asyncio.to_thread(write_file)
            return True
    except Exception:
        pass
    return False

# 工具函数：生成 DMM 标准 ID
def get_dmm_id(code: str) -> str:
    match = re.match(r'([a-zA-Z]+)[-_]?(\d+)', code)
    if match:
        prefix = match.group(1).lower()
        num = match.group(2).zfill(5)
        return f"{prefix}{num}"
    return code.lower().replace('-', '')

# --- 3. 封面刮削 (极速并发版) ---
@app.get("/api/metadata/{code}")
async def get_metadata(code: str, db: Session = Depends(get_db)):
    if code == "UNKNOWN":
        return {"cover": "", "samples": []}
        
    # 需求1: 优先从本地 SQLite 缓存读取
    cached = db.query(MetadataCache).filter(MetadataCache.code == code).first()
    if cached and cached.samples_json:
        samples_list = json.loads(cached.samples_json)
        if len(samples_list) > 0 or code.startswith("FC2"):
            return {"cover": cached.cover_path, "samples": samples_list}
    
    cover_img = ""
    samples = []
    is_dmm = False
    dmm_base_url = ""

    # 使用较大的连接池
    limits = httpx.Limits(max_connections=50, max_keepalive_connections=10)
    async with httpx.AsyncClient(timeout=15.0, headers=HEADERS, limits=limits) as client:
        
        # A. FC2 资源官网刮削
        if code.startswith("FC2-PPV-"):
            fc2_id = code.split('-')[-1]
            try:
                resp = await client.get(f"https://adult.contents.fc2.com/article/{fc2_id}/", cookies={'age_check_done': '1'}, follow_redirects=True)
                soup = BeautifulSoup(resp.text, 'html.parser')
                og_img = soup.find('meta', property='og:image')
                cover_img = og_img['content'] if og_img else ""
                
                # 双重保险：优先通过 CSS 抓取，抓不到就用正则强行在源码里找
                for img in soup.select('.items_article_SampleImages img, .sample-image-wrap img'):
                    src = img.get('src') or img.get('data-src') or img.get('href')
                    if src: samples.append(src)
                    
                if not samples:
                    found = re.findall(r'https?://[^\s"\'<>]+/sample/[^\s"\'<>]+\.(?:jpg|png|jpeg)', resp.text)
                    samples = list(dict.fromkeys(found)) # 去重
            except Exception:
                pass
                
        # B. 普通番号刮削
        else:
            dmm_id = get_dmm_id(code)
            dmm_base_url = f"https://pics.dmm.co.jp/digital/video/{dmm_id}/{dmm_id}"
            
            try:
                # 探测 DMM
                resp_dmm = await client.head(f"{dmm_base_url}pl.jpg", cookies={'age_check_done': '1'}, follow_redirects=True)
                if resp_dmm.status_code == 200:
                    cover_img = f"{dmm_base_url}pl.jpg"
                    is_dmm = True
            except Exception:
                pass
                
            # 若 DMM 失败，回落使用 JavBus
            if not cover_img:
                first_url = f"https://www.javbus.com/uncensored/{code}" if code[0].isdigit() else f"https://www.javbus.com/{code}"
                second_url = f"https://www.javbus.com/{code}" if code[0].isdigit() else f"https://www.javbus.com/uncensored/{code}"
                try:
                    resp = await client.get(first_url, follow_redirects=True)
                    if resp.status_code == 404:
                        resp = await client.get(second_url, follow_redirects=True)
                        
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    cover_tag = soup.select_one('.bigImage img')
                    
                    if cover_tag:
                        cover_img = cover_tag.get('src', '')
                    else:
                        resp_search = await client.get(f"https://www.javbus.com/search/{code}", follow_redirects=True)
                        soup_search = BeautifulSoup(resp_search.text, 'html.parser')
                        search_img = soup_search.select_one('#waterfall .movie-box img')
                        if search_img:
                            cover_img = search_img.get('src', '').replace('thumb/', 'cover/').replace('_b.jpg', '_b.jpg')

                    if cover_img and not cover_img.startswith('http'):
                        cover_img = "https://www.javbus.com" + cover_img
                        
                    samples = [img.get('src') for img in soup.select('.sample-box img') if img.get('src')]
                except Exception:
                    pass

        # === 核心优化：并发下载图片，不再傻等 ===
        tasks = []
        c_path = ""
        local_cover = ""
        
        # 准备封面下载任务
        if cover_img:
            if cover_img.startswith('//'): cover_img = 'https:' + cover_img
            ext = cover_img.split('.')[-1][:4]
            ext = re.sub(r'[^a-zA-Z0-9]', '', ext) or 'jpg'
            c_path = f"{IMG_DIR}/{code}_cover.{ext}"
            tasks.append(download_image(client, cover_img, c_path))
        else:
            tasks.append(asyncio.sleep(0)) # 占位
            
        # 准备详细图下载任务 (限制最多前10张，提升极速加载体验)
        s_paths = []
        if is_dmm:
            for i in range(1, 11):
                s_url = f"{dmm_base_url}jp-{i}.jpg"
                s_path = f"{IMG_DIR}/{code}_sample_{i}.jpg"
                s_paths.append((s_path, f"/img/{code}_sample_{i}.jpg"))
                tasks.append(download_image(client, s_url, s_path))
        else:
            for idx, s_url in enumerate(samples[:10]):
                if s_url.startswith('//'): s_url = 'https:' + s_url
                ext = s_url.split('.')[-1][:4]
                ext = re.sub(r'[^a-zA-Z0-9]', '', ext) or 'jpg'
                s_path = f"{IMG_DIR}/{code}_sample_{idx+1}.{ext}"
                s_paths.append((s_path, f"/img/{code}_sample_{idx+1}.{ext}"))
                tasks.append(download_image(client, s_url, s_path))

        # 【并发执行】瞬间完成所有下载！
        results = await asyncio.gather(*tasks)
        
        # 整理结果
        if results[0] and c_path:
            local_cover = f"/img/{os.path.basename(c_path)}"
            
        local_samples = []
        for idx, success in enumerate(results[1:]):
            if success:
                local_samples.append(s_paths[idx][1])

        # 写入缓存
        if local_cover or local_samples:
            cache_entry = db.query(MetadataCache).filter(MetadataCache.code == code).first()
            if cache_entry:
                cache_entry.cover_path = local_cover or cache_entry.cover_path
                cache_entry.samples_json = json.dumps(local_samples)
            else:
                cache_entry = MetadataCache(code=code, cover_path=local_cover, samples_json=json.dumps(local_samples))
                db.add(cache_entry)
            db.commit()
            
        return {"cover": local_cover, "samples": local_samples}

# --- 4. qB 推送 ---
class DownloadRequest(BaseModel):
    items: list[dict]

@app.post("/api/qb/download")
def push_to_qb(req: DownloadRequest, db: Session = Depends(get_db)):
    setting = db.query(AppSettings).first()
    try:
        qbt_client = Client(host=setting.qb_host, username=setting.qb_user, password=setting.qb_pass)
        qbt_client.auth_log_in()
        urls = [item['link'] for item in req.items]
        qbt_client.torrents_add(urls=urls)
        
        for item in req.items:
            if not db.query(DownloadHistory).filter(DownloadHistory.code == item['code']).first():
                history = DownloadHistory(code=item['code'], title=item['title'], torrent_url=item['link'])
                db.add(history)
        db.commit()
        return {"status": "success", "message": f"成功推送 {len(urls)} 个任务"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推送失败: {str(e)}")

if os.path.exists("static"):
    app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")
    @app.get("/{catchall:path}")
    def serve_vue_app(catchall: str):
        return FileResponse("static/index.html")