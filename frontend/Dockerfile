# =================================================================
# 阶段一: 依赖下载与编译打包 (Build Stage)
# =================================================================
# 使用国内极速高可用的 DaoCloud 代理源拉取 Node 22 镜像，确保绕过腾讯云 500 镜像报错
FROM docker.m.daocloud.io/library/node:22-alpine AS builder

# 安装 pnpm 并配置国内极速镜像源
RUN npm install -g pnpm --registry=https://registry.npmmirror.com

WORKDIR /app

# 优先复制包管理描述文件，利用 Docker 缓存层优化依赖下载速度
COPY package.json pnpm-lock.yaml* ./
RUN pnpm config set registry https://registry.npmmirror.com
RUN pnpm install --frozen-lockfile

# 复制前端全部代码进行生产环境构建 (绕过慢吞吞的 vue-tsc，直接执行极速 vite build)
COPY . .
RUN pnpm exec vite build

# =================================================================
# 阶段二: 轻量级 Nginx 运行环境 (Run Stage)
# =================================================================
FROM docker.m.daocloud.io/library/nginx:alpine

# 将打包好的静态页面复制到 Nginx 默认静态资源路径
COPY --from=builder /app/dist /usr/share/nginx/html

# 用我们自定义的 Nginx 配置覆盖默认配置 (支持 Vue SPA 路由)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露前端访问端口 80
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
