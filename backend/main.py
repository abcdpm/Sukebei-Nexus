# FastAPI 主入口

import asyncio
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from database import IMG_DIR
from routes import router
from scheduler import rss_scheduler_loop

app = FastAPI(title="Sukebei-Nexus API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.mount("/img", StaticFiles(directory=IMG_DIR), name="img")
app.include_router(router)

@app.on_event("startup")
async def startup_event():
    # 启动后台定时任务
    asyncio.create_task(rss_scheduler_loop())

if os.path.exists("static"):
    app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")
    @app.get("/{catchall:path}")
    def serve_vue_app(catchall: str):
        return FileResponse("static/index.html")