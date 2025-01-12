# YouTube Video Downloader

一个基于 FastAPI + yt-dlp 的 YouTube 视频下载器，支持代理设置、自动获取浏览器 cookies、进度显示和视频管理。

## 特性

- 🚀 异步下载，不阻塞主线程
- 🔄 实时显示下载进度
- 🔒 自动获取浏览器 cookies，无需手动配置
- 🌐 支持代理设置
- 📺 支持视频预览和管理
- 🎯 简单易用的界面

## 技术栈

- **后端框架**: FastAPI
- **下载工具**: yt-dlp
- **前端样式**: Tailwind CSS
- **模板引擎**: Jinja2
- **代理支持**: SOCKS5/HTTP 代理

## 项目结构
project/
├── main.py # 主程序
├── templates/ # 模板文件
│ └── index.html # 主页面
├── static/ # 静态文件
│ └── style.css # 样式文件
├── downloads/ # 下载文件存储目录
└── .gitignore # Git 忽略配置



## 安装步骤

1. 克隆项目：
bash
git clone [repository_url]
cd youtube-download

2. 创建虚拟环境：
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

## 使用方法

1. 配置代理（如果需要）：
   - 确保代理服务器（如 V2Ray/Clash）运行在 localhost:1080
   - 或修改 `main.py` 中的代理端口设置

2. 启动服务器：
```bash
uvicorn main:app --reload --port 8000
```

3. 使用浏览器访问：
   - 打开 `http://localhost:8000`
   - 确保已在浏览器中登录 YouTube 账号
   - 复制 YouTube 视频链接并粘贴到输入框
   - 点击下载按钮

## 隐私保护

### Cookie 处理
- 自动从浏览器获取 YouTube cookies
- cookies 信息仅临时使用，使用后立即删除
- 只读取 youtube.com 域名的 cookies
- 所有操作在本地进行，不会上传到任何服务器

### 支持的浏览器
- Google Chrome
- Mozilla Firefox
- Microsoft Edge
- Safari (macOS)
- Chromium
- Opera
- Brave

### 数据安全
- 下载的视频保存在本地 downloads 目录
- 不收集任何用户数据
- 不保存任何登录信息
- 临时文件会自动清理

## 注意事项

1. 代理设置：
   - 确保代理服务器正常运行
   - 检查代理端口配置是否正确
   - 支持 SOCKS5 和 HTTP 代理

2. 浏览器配置：
   - 确保至少有一个浏览器登录了 YouTube
   - 程序会自动检测并使用可用的 cookies
   - 无需手动配置 cookies

3. 存储空间：
   - 定期清理 downloads 目录
   - 确保有足够的磁盘空间

## 常见问题

1. 下载失败：
   - 检查代理连接
   - 确认浏览器已登录 YouTube
   - 检查视频是否可用

2. 代理问题：
   - 验证代理服务是否运行
   - 检查代理端口设置
   - 尝试切换代理协议

3. Cookie 问题：
   - 确保浏览器已登录 YouTube
   - 尝试使用其他支持的浏览器
   - 检查浏览器权限设置

## 部署

### Vercel 部署
1. Fork 本项目到你的 GitHub
2. 在 Vercel 中导入项目
3. 部署时会自动识别并使用 `vercel.json` 配置
4. 等待部署完成

注意：由于 Vercel 的限制，在线部署版本：
- 不支持本地文件存储，建议使用云存储服务
- 不支持长时间运行的下载任务
- 建议用于小文件或测试用途

### 本地部署
如果需要完整功能，建议本地部署：

```bash
# 克隆项目
git clone [repository_url]
cd youtube-download

# 安装依赖
pip install -r requirements.txt

# 启动服务
uvicorn main:app --reload
```

## 贡献

欢迎提交 Issue 和 Pull Request 来改进项目。

## 许可证

[MIT License](LICENSE)