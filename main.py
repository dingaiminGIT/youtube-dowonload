from fastapi import FastAPI, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import os
import asyncio
from datetime import datetime
import humanize
import re
import logging
import http.client
import sys
import traceback
import urllib3
import socks
import socket
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import browser_cookie3  # 需要先安装：pip install browser-cookie3
import tempfile
import json
from http.cookiejar import MozillaCookieJar

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 确保必要的目录存在
DOWNLOAD_DIR = "downloads"
STATIC_DIR = "static"

# 创建必要的目录
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# 在文件开头定义全局变量
PROXY_PORT = 1080  # 设置默认代理端口

# 禁用 SSL 警告
urllib3.disable_warnings()

# 创建 FastAPI 应用
app = FastAPI()

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置静态文件和模板
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory="templates")

# 存储视频信息的列表
videos = []

# 创建一个带有重试机制的 session
def create_session():
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=1,  # 增加重试间隔
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    # 尝试使用 HTTP 代理而不是 SOCKS5
    session.proxies = {
        'http': 'http://127.0.0.1:1080',
        'https': 'http://127.0.0.1:1080'
    }
    session.verify = False
    session.timeout = 30  # 增加超时时间
    return session

# 修改代理测试函数
def test_proxy_connection():
    try:
        # 首先检查代理端口是否开放
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(('127.0.0.1', 1080))
        sock.close()
        
        if result != 0:
            logger.error("Proxy port is not open")
            return False
            
        # 测试多个代理协议和网站
        test_urls = [
            'https://api.ipify.org?format=json',  # 简单的 IP 检查服务
            'https://www.youtube.com/favicon.ico', # YouTube 图标（小文件）
            'https://www.google.com/generate_204'  # Google 连接测试
        ]
        
        for proxy_url in [
            'socks5h://127.0.0.1:1080',  # 让代理处理 DNS
            'socks5://127.0.0.1:1080',
            'http://127.0.0.1:1080'
        ]:
            logger.info(f"Testing proxy: {proxy_url}")
            session = requests.Session()
            session.proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
            session.verify = False
            session.timeout = 10
            
            for test_url in test_urls:
                try:
                    logger.info(f"Testing URL: {test_url}")
                    response = session.get(test_url, allow_redirects=True)
                    if response.status_code in [200, 204]:
                        logger.info(f"Proxy connection successful using {proxy_url} to {test_url}")
                        # 更新全局代理设置
                        os.environ['HTTP_PROXY'] = proxy_url
                        os.environ['HTTPS_PROXY'] = proxy_url
                        if 'ALL_PROXY' in os.environ:
                            del os.environ['ALL_PROXY']
                        
                        # 更新 yt-dlp 配置
                        global ydl_opts
                        ydl_opts['proxy'] = proxy_url
                        return True
                except Exception as e:
                    logger.warning(f"Failed with {proxy_url} to {test_url}: {str(e)}")
                    continue
        
        logger.error("All proxy protocols and URLs failed")
        return False
        
    except Exception as e:
        logger.error(f"Proxy connection test failed: {str(e)}\n{traceback.format_exc()}")
        return False

def check_proxy_ports():
    """检查哪个代理端口可用"""
    import socket
    import socks
    
    ports_to_try = [1080, 1081, 1082, 10808]  # 常见的代理端口
    
    for port in ports_to_try:
        try:
            # 测试端口
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            
            if result == 0:
                logger.info(f"Found active proxy port: {port}")
                return port
        except Exception:
            continue
    
    logger.error("No active proxy ports found")
    return None

def validate_youtube_url(url: str) -> bool:
    youtube_regex = r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$'
    return bool(re.match(youtube_regex, url))

# 添加下载进度回调函数
def download_progress_hook(d):
    if d['status'] == 'downloading':
        try:
            # 计算下载进度
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                progress = (downloaded / total) * 100
                speed = d.get('speed', 0)
                if speed:
                    eta = d.get('eta', 0)
                    logger.info(
                        f"Download progress: {progress:.1f}% "
                        f"Speed: {humanize.naturalsize(speed)}/s "
                        f"ETA: {datetime.timedelta(seconds=eta)}"
                    )
        except Exception as e:
            logger.warning(f"Error calculating progress: {str(e)}")

# 定义全局 yt-dlp 配置
ydl_opts = {
    'format': 'best',  # 使用最简单的格式选择
    'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
    'quiet': False,
    'no_warnings': False,
    'verbose': True,
    'socket_timeout': 30,
    'retries': 5,
    'fragment_retries': 5,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    },
    'proxy': 'socks5h://127.0.0.1:1080',
    'nocheckcertificate': True,
    'no_check_certificate': True,
    'ignoreerrors': True,
    'no_color': True,
    # 移除 cookiesfrombrowser 选项
    'merge_output_format': 'mp4',
    'progress_hooks': [download_progress_hook],  # 添加进度回调
}

# 设置环境变量
os.environ['HTTP_PROXY'] = 'socks5h://127.0.0.1:1080'
os.environ['HTTPS_PROXY'] = 'socks5h://127.0.0.1:1080'
# 移除 ALL_PROXY
if 'ALL_PROXY' in os.environ:
    del os.environ['ALL_PROXY']

@app.on_event("startup")
async def startup_event():
    logger.info("Testing proxy connection...")
    if test_proxy_connection():
        logger.info("Proxy connection established successfully")
    else:
        logger.warning("Failed to establish proxy connection")

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "videos": videos})

# 添加自动获取 cookies 的函数
def get_youtube_cookies():
    """
    自动从浏览器获取 YouTube cookies
    返回临时 cookie 文件的路径
    """
    try:
        # 创建临时文件来存储 cookies
        cookie_file = tempfile.NamedTemporaryFile(suffix='.txt', delete=False)
        cookie_path = cookie_file.name
        cookie_file.close()
        
        # 尝试从不同浏览器获取 cookies
        browsers = [
            ('chrome', browser_cookie3.chrome),
            ('firefox', browser_cookie3.firefox),
            ('safari', browser_cookie3.safari),
            ('edge', browser_cookie3.edge),
            ('chromium', browser_cookie3.chromium),
            ('opera', browser_cookie3.opera),
            ('brave', browser_cookie3.brave),
        ]
        
        for browser_name, browser_func in browsers:
            try:
                logger.info(f"Attempting to get cookies from {browser_name}")
                cookies = browser_func(domain_name='.youtube.com')
                if cookies:
                    # 将 cookies 转换为 Netscape 格式
                    cookie_jar = MozillaCookieJar(cookie_path)
                    for cookie in cookies:
                        try:
                            cookie_jar.set_cookie(cookie)
                        except Exception as e:
                            logger.warning(f"Failed to set cookie: {str(e)}")
                            continue
                    
                    cookie_jar.save()
                    logger.info(f"Successfully saved cookies from {browser_name}")
                    return cookie_path
            except Exception as e:
                logger.warning(f"Failed to get cookies from {browser_name}: {str(e)}")
                continue
        
        logger.warning("No cookies found from any browser")
        return None
        
    except Exception as e:
        logger.error(f"Error getting cookies: {str(e)}")
        return None

@app.post("/download")
async def download_video(request: Request):
    try:
        logger.info("Received download request")
        data = await request.json()
        url = data.get("url")
        
        logger.info(f"Processing URL: {url}")
        
        if not url:
            raise HTTPException(status_code=400, detail="URL is required")
        
        if not validate_youtube_url(url):
            logger.warning(f"Invalid URL format: {url}")
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")
        
        # 使用环境变量方式设置代理
        current_opts = ydl_opts.copy()
        
        # 获取 cookies
        cookie_path = get_youtube_cookies()
        if cookie_path:
            current_opts['cookiefile'] = cookie_path
            logger.info(f"Using cookies from browser")
        else:
            logger.warning("No browser cookies found, trying without cookies")
        
        try:
            logger.info("Extracting video info...")
            logger.debug(f"Using yt-dlp options: {current_opts}")
            
            with yt_dlp.YoutubeDL(current_opts) as ydl:
                try:
                    # 先获取基本信息
                    basic_info = ydl.extract_info(url, download=False, process=False)
                    logger.debug(f"Basic info extracted: {basic_info}")
                    
                    if not basic_info:
                        raise Exception("Failed to extract basic video information")
                    
                    # 然后获取详细信息
                    info = ydl.extract_info(url, download=False)
                    logger.debug(f"Full info extracted: {info}")
                    
                    if not info:
                        raise Exception("Failed to extract detailed video information")
                    
                    # 检查是否有可用的格式
                    if 'formats' not in info or not info['formats']:
                        raise Exception("No available formats found for this video")
                    
                    # 开始异步下载
                    asyncio.create_task(download_task(url, current_opts, info))
                    
                    return JSONResponse({
                        "status": "success",
                        "message": "Download started",
                        "title": info.get('title', 'Unknown Title')
                    })
                    
                except Exception as e:
                    logger.error(f"Error during video info extraction: {str(e)}")
                    raise
                    
        except Exception as e:
            logger.error(f"YouTube download error: {str(e)}")
            raise HTTPException(status_code=400, detail=f"YouTube download error: {str(e)}")
            
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

async def download_task(url, opts, info):
    retry_count = 0
    max_retries = 3
    cookie_path = opts.get('cookiefile')
    
    try:
        while retry_count < max_retries:
            try:
                logger.info(f"Download attempt {retry_count + 1} of {max_retries}")
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
                break  # 如果下载成功，跳出循环
            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    raise  # 如果达到最大重试次数，抛出异常
                logger.warning(f"Download failed, retrying ({retry_count}/{max_retries}): {str(e)}")
                await asyncio.sleep(2)  # 等待一段时间后重试
        
        # 获取下载文件的信息
        filename = f"{info['title']}.mp4"  # 强制使用 mp4 扩展名
        filepath = os.path.join(DOWNLOAD_DIR, filename)
        
        if not os.path.exists(filepath):
            logger.warning(f"File not found at expected path: {filepath}")
            # 尝试查找实际文件
            for file in os.listdir(DOWNLOAD_DIR):
                if info['title'] in file:
                    filepath = os.path.join(DOWNLOAD_DIR, file)
                    break
        
        filesize = os.path.getsize(filepath)
        
        logger.info(f"Download completed: {filename}")
        
        # 添加到视频列表
        video_info = {
            "title": info['title'],
            "duration": str(datetime.timedelta(seconds=info['duration'])),
            "author": info.get('uploader', 'Unknown'),
            "description": info.get('description', '')[:200] + "...",
            "size": humanize.naturalsize(filesize),
            "path": filepath,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        videos.append(video_info)
        logger.info("Video info added to list")
        
    except Exception as e:
        logger.error(f"Download task error: {str(e)}\n{traceback.format_exc()}")
    finally:
        # 清理临时 cookie 文件
        if cookie_path and os.path.exists(cookie_path):
            try:
                os.unlink(cookie_path)
                logger.debug("Cleaned up temporary cookie file")
            except Exception as e:
                logger.warning(f"Failed to clean up cookie file: {str(e)}")

@app.get("/videos")
async def get_videos():
    return JSONResponse({"videos": videos}) 