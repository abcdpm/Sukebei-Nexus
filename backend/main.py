import os
import re
import feedparser
import httpx
import asyncio
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from qbittorrentapi import Client

# --- 数据库配置 ---
DATA_DIR = "./data"
os.makedirs(DATA_DIR, exist_ok=True)
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

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(title="Sukebei-Nexus API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- 请求伪装 Headers，防止被目标网站拦截 ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# --- 1. 设置 API ---
class SettingsDTO(BaseModel):
    qb_host: str
    qb_user: str
    qb_pass: str
    rss_url: str

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
    results = []
    downloaded_codes = [h.code for h in db.query(DownloadHistory).all()]
    
    # 【修复分页逻辑】RSS 默认给 100 条，我们要根据当前页码在后端进行切片
    total_items = len(feed.entries)
    total_pages = (total_items + limit - 1) // limit if total_items > 0 else 1
    
    start = (page - 1) * limit
    end = start + limit
    entries = feed.entries[start:end]
    
    for entry in entries:
        title = entry.title
        
        # 1. 优先匹配 FC2 (绕过混淆字符，只取后面 5-8 位数字)
        match_fc2 = re.search(r'FC2[^\d]*(\d{5,8})', title, re.IGNORECASE)
        # 2. 匹配加长版日期番号 (如 022326-001, 022326-001-CARIB)
        match_date = re.search(r'(\d{6}[-_]\d{3}(?:[-_][A-Za-z]+)?)', title, re.IGNORECASE)
        # 3. 匹配常规番号 (如 HEYZO-3789, IPX-123)，排除掉 FC2
        match_normal = re.search(r'\b(?!(?:PPV|FC2)\-)([A-Za-z]{2,8}[-_]\d{2,5})\b', title, re.IGNORECASE)
        
        code = "UNKNOWN"
        if match_fc2:
            code = f"FC2-PPV-{match_fc2.group(1)}"
        elif match_date:
            code = match_date.group(1).upper()
        elif match_normal:
            code = match_normal.group(1).upper()
            
        # 【需求3】清理标题：剥离 ++ 、括号内容以及番号本身
        clean_title = re.sub(r'^[+\s]+', '', title)  # 去掉开头的 ++
        clean_title = re.sub(r'^\[.*?\]\s*', '', clean_title)  # 去掉开头的 [FHD] 等
        if code != "UNKNOWN":
            # 忽略大小写，将匹配到的番号从标题中剥离
            clean_title = re.sub(rf'{code}\s*', '', clean_title, flags=re.IGNORECASE).strip()
            
        results.append({
            "title": clean_title, "link": entry.link, "code": code,
            "is_downloaded": code in downloaded_codes
        })
    # 返回总页数给前端生成 1 2 3 4 按钮
    return {"total_pages": total_pages, "page": page, "data": results}

# --- 3. 封面刮削 (分流处理) ---
@app.get("/api/metadata/{code}")
async def get_metadata(code: str):
    if code == "UNKNOWN":
        return {"cover": "", "samples": []}
    
    async with httpx.AsyncClient(timeout=20.0, headers=HEADERS) as client:
        # A. FC2 资源官网刮削
        if code.startswith("FC2-PPV-"):
            fc2_id = code.split('-')[-1]
            cookies = {'age_check_done': '1'}
            try:
                resp = await client.get(f"https://adult.contents.fc2.com/article/{fc2_id}/", cookies=cookies, follow_redirects=True)
                soup = BeautifulSoup(resp.text, 'html.parser')
                og_img = soup.find('meta', property='og:image')
                cover_img = og_img['content'] if og_img else ""
                samples = [img.get('src') for img in soup.select('.items_article_SampleImages img') if img.get('src')]
                return {"cover": cover_img, "samples": samples}
            except Exception as e:
                return {"cover": "", "samples": [], "error": str(e)}
                
        # B. 非FC2 资源处理
        else:
            cover_img = ""
            samples = []
            
            # 【需求4】第一梯队：如果是正规 DMM 番号格式，直接从 DMM 官方图库拉取，无视反爬
            m = re.match(r'^([A-Za-z]+)[-_]?(\d{2,5})$', code)
            if m:
                prefix = m.group(1).lower()
                number = m.group(2).zfill(5) # 比如 123 补全为 00123
                dmm_code = f"{prefix}{number}"
                # DMM 封面链接格式
                dmm_cover_url = f"https://pics.dmm.co.jp/mono/movie/adult/{dmm_code}/{dmm_code}pl.jpg"
                try:
                    # 使用 HEAD 请求快速验证图片是否存在
                    dmm_resp = await client.head(dmm_cover_url, timeout=5.0)
                    if dmm_resp.status_code == 200:
                        cover_img = dmm_cover_url
                        # 获取缩略图，通常为 dmm_code-1.jpg 到 dmm_code-5.jpg
                        for i in range(1, 6):
                            sample_url = f"https://pics.dmm.co.jp/mono/movie/adult/{dmm_code}/{dmm_code}-{i}.jpg"
                            s_resp = await client.head(sample_url, timeout=2.0)
                            if s_resp.status_code == 200:
                                samples.append(sample_url)
                            else:
                                break
                except Exception as e:
                    pass

            # 第二梯队：如果 DMM 没找到 (或者是 HEYZO/加勒比)，走 JavBus 备用线路
            if not cover_img:
                bus_url = f"https://www.javbus.com/{code}"
                try:
                    resp = await client.get(bus_url, follow_redirects=True)
                    
                    # 如果有码区找不到，尝试无码区路径
                    if resp.status_code == 404:
                        bus_url = f"https://www.javbus.com/uncensored/{code}"
                        resp = await client.get(bus_url, follow_redirects=True)
                        
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    cover_tag = soup.select_one('.bigImage img')
                    
                    # 如果详情页依然拿不到，直接请求 Search 页面刮削第一张瀑布流图片
                    if cover_tag:
                        cover_img = cover_tag['src']
                    else:
                        search_url = f"https://www.javbus.com/search/{code}"
                        resp_search = await client.get(search_url, follow_redirects=True)
                        soup_search = BeautifulSoup(resp_search.text, 'html.parser')
                        search_img = soup_search.select_one('#waterfall .movie-box img')
                        if search_img:
                            cover_img = search_img.get('src', '')

                    # 补全绝对路径
                    if cover_img and not cover_img.startswith('http'):
                        cover_img = "https://www.javbus.com" + cover_img
                        
                    # 提取详情页预览图
                    bus_samples = [img['src'] for img in soup.select('.sample-box img') if img.get('src')]
                    if bus_samples:
                        samples = bus_samples
                except Exception as e:
                    pass
                    
            return {"cover": cover_img, "samples": samples}

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