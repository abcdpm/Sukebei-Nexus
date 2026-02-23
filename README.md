# Sukebei-Nexus
Sukebei-Nexus 是一个专为 HomeLab 设计的现代优美 Web 聚合应用。它可以自动化处理 Sukebei Nyaa 的 RSS 订阅，智能提取番号，自动刮削高清封面与预览图，并提供一键推送到 qBittorrent 的无缝下载体验。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Docker](https://img.shields.io/badge/docker-ready-blue.svg)
![Vue3](https://img.shields.io/badge/vue-3.0-brightgreen.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal.svg)

## ✨ 核心特性

- **🚀 智能聚合与解析**：定时解析特定 Nyaa RSS 源或网页用户发布列表，利用正则精准提取番号 (Code)。
- **🖼️ 自动元数据刮削**：自动从 JavBus 刮削高清大图封面及预览图，并在前端以现代化的卡片瀑布流展示，支持图片点击放大预览。
- **📥 qBittorrent 深度集成**：内置 qB 客户端连接测试功能，支持批量选中种子，一键推送到本地或远端 qB 进行下载。
- **📝 下载历史记录**：基于 SQLite 本地记录已推送历史，前端自动将已推送的番号进行“灰显”或打上“已下载”标记，避免重复下载。
- **🔗 快捷跳转导航**：每张番号卡片底部提供直达 JavBus、Avbase 和 Nyaa 搜索页的快捷按钮，方便交叉查阅。
- **🐳 极简部署**：前后端分离架构，已打包为纯净的 Docker 镜像，只需几行配置即可在 NAS 上飞速跑起来。

## 🛠️ 技术栈

* **前端**：Vue 3 + Vite + Tailwind CSS + Element Plus
* **后端**：Python 3.10 + FastAPI + SQLite + httpx + BeautifulSoup4
* **部署**：Docker + Docker Compose

## 🚀 快速开始 (基于 Docker)

我们推荐使用 Docker Compose 进行部署。

1. 创建 `docker-compose.yml` 文件：

```yaml
version: '3.8'
services:
  javcatcher:
    image: yourusername/sukebeinexus:latest # 替换为你未来推送到dockerhub的镜像名
    container_name: sukebeinexus
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data  # 挂载 SQLite 数据库目录以持久化
    restart: unless-stopped
```

2. 运行容器：

```Bash
docker-compose up -d
```

3. 打开浏览器访问：`http://你的NAS_IP:8000`

# ⚠️ 注意事项与免责声明
网络环境：刮削数据强依赖于您的网络环境。如果宿主机无法直接访问相关站点，请在后端代码中配置 HTTP 代理。

反爬策略：频繁请求目标网站可能会触发 Cloudflare 质询或 IP 封禁，建议合理设置 RSS 获取频率。

免责声明：本项目仅供技术交流与学习 Python 爬虫、FastAPI 框架以及 Vue3 前端技术，作者不对用户使用本项目下载和传播的任何内容负责。

# 🤝 参与贡献
欢迎提交 Issue 报告 Bug 或者提出新功能建议，也非常欢迎提交 Pull Request！
