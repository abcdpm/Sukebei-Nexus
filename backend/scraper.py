import os
import re
import json
import httpx
import asyncio
from bs4 import BeautifulSoup
from database import IMG_DIR
from models import MetadataCache

# --- 请求伪装 Headers，防止被目标网站拦截 ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 工具函数：生成 DMM 标准 ID (例如 SCPX-547 -> scpx00547)
def get_dmm_id(code: str) -> str:
    match = re.match(r'([a-zA-Z]+)[-_]?(\d+)', code)
    if match:
        prefix = match.group(1).lower()
        num = match.group(2).zfill(5)
        return f"{prefix}{num}"
    return code.lower().replace('-', '')

# 工具函数：并发安全的极速图片下载
async def download_image(client, url, filepath):
    if not url: return False
    if url.startswith('//'): url = 'https:' + url # 修复 FC2 相对路径
    if os.path.exists(filepath): return True # 优先读取本地
    try:
        resp = await client.get(url, cookies={'age_check_done': '1'}, follow_redirects=True, timeout=10.0)
        if resp.status_code == 200:
            def write_file():
                with open(filepath, 'wb') as f:
                    f.write(resp.content)
            await asyncio.to_thread(write_file)
            return True
    except Exception:
        pass
    return False

# --- 核心后台刮削逻辑 ---
async def scrape_and_cache(code: str, db):
    print(f"[Scraper] 开始处理番号: {code}", flush=True) # 需求2: 输出 Docker 日志

    # 优先从本地 SQLite 缓存读取
    cached = db.query(MetadataCache).filter(MetadataCache.code == code).first()
    if cached and cached.samples_json:
        samples_list = json.loads(cached.samples_json)
        if len(samples_list) > 0 or code.startswith("FC2"):
            print(f"[Scraper] {code} 命中本地缓存，瞬间返回!", flush=True)
            return {"cover": cached.cover_path, "samples": samples_list}

    cover_img = ""
    samples = []
    is_dmm = False
    dmm_base_url = ""

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
                    samples = list(dict.fromkeys(found))
            except Exception as e:
                print(f"[Scraper Error] FC2 {code} 刮削失败: {e}", flush=True)
                pass
                
        # B. 普通番号刮削
        else:
            # 需求4: 优先尝试 DMM 官网强行组合提取
            dmm_id = get_dmm_id(code)
            dmm_base_url = f"https://pics.dmm.co.jp/digital/video/{dmm_id}/{dmm_id}"
            try:
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
                except Exception as e:
                    print(f"[Scraper Error] JavBus {code} 刮削失败: {e}", flush=True)
                    pass

        # === 核心优化：并发下载图片，不再傻等 ===
        tasks = []
        c_path = ""
        local_cover = ""
        
        # 准备封面下载任务 (需求5: 后缀强制转小写)
        if cover_img:
            if cover_img.startswith('//'): cover_img = 'https:' + cover_img
            ext = cover_img.split('.')[-1][:4].lower()
            ext = re.sub(r'[^a-z0-9]', '', ext) or 'jpg'
            c_path = f"{IMG_DIR}/{code}_cover.{ext}"
            tasks.append(download_image(client, cover_img, c_path))
        else:
            tasks.append(asyncio.sleep(0))
            
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
                ext = s_url.split('.')[-1][:4].lower()
                ext = re.sub(r'[^a-z0-9]', '', ext) or 'jpg'
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
            print(f"[Scraper] {code} 刮削并缓存完毕! 封面: {'有' if local_cover else '无'}, 详情图: {len(local_samples)}张", flush=True)
        else:
            print(f"[Scraper] {code} 刮削失败，未找到任何图片资源", flush=True)

        return {"cover": local_cover, "samples": local_samples}