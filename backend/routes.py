import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from qbittorrentapi import Client
from database import get_db
from models import AppSettings, DownloadHistory, MetadataCache, RssItem
from schemas import SettingsDTO, DownloadRequest
from scraper import scrape_and_cache

router = APIRouter()

@router.get("/api/settings")
def get_settings_api(db: Session = Depends(get_db)):
    setting = db.query(AppSettings).first()
    return setting

@router.post("/api/settings")
def save_settings_api(config: SettingsDTO, db: Session = Depends(get_db)):
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
        setting.rss_interval = config.rss_interval
    db.commit()
    return {"status": "success"}

@router.post("/api/qb/test")
def test_qb_connection_api(config: SettingsDTO):
    try:
        qbt_client = Client(host=config.qb_host, username=config.qb_user, password=config.qb_pass)
        qbt_client.auth_log_in()
        return {"status": "success", "message": f"连接成功！qB版本: {qbt_client.app.version}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"连接失败: {str(e)}")

@router.get("/api/rss")
def get_rss_api(page: int = 1, limit: int = 24, db: Session = Depends(get_db)):
    # 需求1: 直接从数据库获取，按 ID 倒序排列保证最新内容在最前面
    total_items = db.query(RssItem).count()
    total_pages = (total_items + limit - 1) // limit if total_items > 0 else 1
    
    offset = (page - 1) * limit
    items = db.query(RssItem).order_by(RssItem.id.desc()).offset(offset).limit(limit).all()
    
    downloaded_codes = {h.code for h in db.query(DownloadHistory).all()}
    
    results = []
    for item in items:
        # 直接附带已缓存的 metadata
        meta = db.query(MetadataCache).filter(MetadataCache.code == item.code).first()
        meta_data = {"cover": "", "samples": []}
        if meta and meta.samples_json:
            meta_data = {"cover": meta.cover_path, "samples": json.loads(meta.samples_json)}
            
        results.append({
            "title": item.title, "link": item.link, "code": item.code,
            "is_downloaded": item.code in downloaded_codes,
            "meta": meta_data if meta_data["cover"] else None
        })
        
    return {"total_pages": total_pages, "page": page, "data": results}

# 需求2: 补回丢失的前端按需触发刮削的接口
@router.get("/api/metadata/{code}")
async def get_metadata_api(code: str, db: Session = Depends(get_db)):
    return await scrape_and_cache(code, db)

@router.post("/api/qb/download")
def push_to_qb_api(req: DownloadRequest, db: Session = Depends(get_db)):
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