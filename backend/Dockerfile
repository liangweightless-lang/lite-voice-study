# 使用官方超轻量的 Python 3.12 镜像作为基础环境
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置 Python 环境变量 (防写入 pyc 缓存，开启输出缓冲实时打印日志)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 复制依赖描述文件并安装 (使用国内清华大学极速镜像源，加速 pip 依赖包拉取)
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 复制后端所有代码到容器中
COPY . .

# 暴露后端 WebSocket 监听端口
EXPOSE 9090

# 启动微服务网关
CMD ["python", "main.py"]
