# 阶段 1: 构建 Vue 前端
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# 阶段 2: 构建 FastAPI 后端运行环境
FROM python:3.10-slim
WORKDIR /app

# 设置时区为亚洲/上海
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# 将阶段 1 打包好的前端文件复制到后端的 static 目录
COPY --from=frontend-builder /app/frontend/dist /app/static

EXPOSE 8000

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]