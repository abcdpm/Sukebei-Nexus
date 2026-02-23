import asyncio
import feedparser
import re
from database import SessionLocal
from models import AppSettings, RssItem
from scraper import scrape_and_cache

# 需求3 & 4: 后台定时拉取 RSS，增量更新并直接刮削
async def fetch_rss_and_scrape():
    db = SessionLocal()
    try:
        setting = db.query(AppSettings).first()
        if not setting or not setting.rss_url:
            return
            
        base_url = setting.rss_url
        feed = feedparser.parse(base_url)
        
        block_prefixes = [p.strip().upper() for p in setting.block_prefixes.split(',') if p.strip()] if setting.block_prefixes else []

        # 需求1: 将 feed.entries 倒序遍历。RSS中最新的在前面，倒序后最新的最后入库，获得最大的 ID。
        # 这样在首页按照 ID 倒序查询时，最新抓取的就会绝对显示在第一页最前面！
        for entry in reversed(feed.entries):
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
                
            if code == "UNKNOWN" or any(code.startswith(bp) for bp in block_prefixes):
                continue
            
            # 需求4: 增量更新。判断 code 是否已存在
            existing_item = db.query(RssItem).filter(RssItem.code == code).first()
            if not existing_item:
                # 检查 title 是否重名，如果重名自动加后缀防覆盖
                existing_title = db.query(RssItem).filter(RssItem.title == title).first()
                if existing_title:
                    title = f"{title} (1)"
                    
                new_item = RssItem(code=code, title=title, link=entry.link)
                db.add(new_item)
                db.commit()
                print(f"[Scheduler] 发现新番号入库: {code} -> {title}", flush=True) # 需求2: 加入进度日志
                # 入库后立即触发后台刮削任务
                await scrape_and_cache(code, db)

    except Exception as e:
        print(f"[Scheduler] RSS Fetch Error: {e}", flush=True)
    finally:
        db.close()

# 定时器 Loop
async def rss_scheduler_loop():
    # 启动时立刻执行一次
    print("[Scheduler] 启动初始化，正在拉取 RSS...", flush=True)
    await fetch_rss_and_scrape()
    while True:
        db = SessionLocal()
        interval = 15
        try:
            setting = db.query(AppSettings).first()
            if setting and setting.rss_interval:
                interval = setting.rss_interval
        finally:
            db.close()
        
        await asyncio.sleep(interval * 60) # 分钟转秒
        print(f"[Scheduler] 执行定时任务拉取 RSS...", flush=True)
        await fetch_rss_and_scrape()