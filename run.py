import time
import logging
import requests
from PIL import Image
from io import BytesIO
import os
from flask import Flask, render_template, request, Response, jsonify, send_from_directory
import threading

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("screenshot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ================= 配置区 =================
ESP32_URL = "http://192.168.1.38/mjpeg/1"  # 摄像头地址
SAVE_DIR = "./screenshots"                 # 保存目录
INTERVAL = 5                               # 截图间隔(秒)
TIMEOUT = 15                               # 连接超时时间

app = Flask(__name__)
is_running = False
stop_event = threading.Event()

def print_welcome():
    logger.info("""
███████╗███████╗██████╗.██████╗.██████╗..██████╗.█████╗.███╗...███╗
██╔════╝██╔════╝██╔══██╗╚════██╗╚════██╗██╔════╝██╔══██╗████╗.████║
█████╗..███████╗██████╔╝.█████╔╝.█████╔╝██║.....███████║██╔████╔██║
██╔══╝..╚════██║██╔═══╝..╚═══██╗██╔═══╝.██║.....██╔══██║██║╚██╔╝██║
███████╗███████║██║.....██████╔╝███████╗╚██████╗██║..██║██║.╚═╝.██║
╚══════╝╚══════╝╚═╝.....╚═════╝.╚══════╝.╚═════╝╚═╝..╚═╝╚═╝.....╚═╝
    """)
    logger.info("""
██╗....██╗███████╗██████╗...██████╗..█████╗.███╗...██╗███████╗██╗...
██║....██║██╔════╝██╔══██╗..██╔══██╗██╔══██╗████╗..██║██╔════╝██║...
██║.█╗.██║█████╗..██████╔╝..██████╔╝███████║██╔██╗.██║█████╗..██║...
██║███╗██║██╔══╝..██╔══██╗..██╔═══╝.██╔══██║██║╚██╗██║██╔══╝..██║...
╚███╔███╔╝███████╗██████╔╝..██║.....██║..██║██║.╚████║███████╗█████╗
.╚══╝╚══╝.╚══════╝╚═════╝...╚═╝.....╚═╝..╚═╝╚═╝..╚═══╝╚══════╝╚════╝
    """)
    logger.info("""
.██████.██...██.███████....██....██....██....██....██.
██......██...██.██........███...███...███...███...███.
██......███████.█████......██....██....██....██....██.
██......██...██.██.........██....██....██....██....██.
.██████.██...██.███████....██....██....██....██....██.
    """)
    logger.info("""
Github:
https://github.com/che11111/esp32cam-webPanel
    """)
    logger.info(f"🔗 目标地址: {ESP32_URL}")
    logger.info(f"📁 保存目录: {os.path.abspath(SAVE_DIR)}")
    logger.info(f"⏱ 抓取间隔: {INTERVAL}秒")

def take_screenshot():
    try:
        current_time = time.localtime()
        year_month_day = time.strftime("%Y%m%d", current_time)
        hour = time.strftime("%H", current_time)

        daily_hourly_dir = os.path.join(SAVE_DIR, year_month_day, hour)
        os.makedirs(daily_hourly_dir, exist_ok=True)

        response = requests.get(ESP32_URL, stream=True, timeout=TIMEOUT)
        boundary = response.headers['Content-Type'].split('=')[1]
        content = b''
        for chunk in response.iter_content(chunk_size=1024):
            content += chunk
            if b'\r\n--' + boundary.encode() in content:
                parts = content.split(b'\r\n--' + boundary.encode())
                for part in parts:
                    if b'Content-Type: image/jpeg' in part:
                        image_start = part.find(b'\r\n\r\n') + 4
                        image_data = part[image_start:]
                        try:
                            timestamp = int(time.time())
                            img = Image.open(BytesIO(image_data))
                            screenshot_path = os.path.join(daily_hourly_dir, f"screenshot_{timestamp}.png")
                            img.save(screenshot_path)
                            logger.info(f"✅ 捕获成功，保存路径: {screenshot_path}")
                            return
                        except Exception as e:
                            logger.error(f"🛑 处理图像时出错: {str(e)}")
                content = parts[-1]
    except Exception as e:
        logger.error(f"💀 捕获失败: {str(e)}")

def screenshot_loop():
    global is_running
    while not stop_event.is_set():
        take_screenshot()
        time.sleep(INTERVAL)
    is_running = False

# ================= Flask路由 =================
@app.route('/')
def index():
    return render_template('index.html', is_running=is_running)

@app.route('/start', methods=['POST'])
def start():
    global is_running
    if not is_running:
        stop_event.clear()
        is_running = True
        threading.Thread(target=screenshot_loop).start()
        return "🔄 程序已启动"
    return "✅ 程序已经在运行中"

@app.route('/stop', methods=['POST'])
def stop():
    global is_running
    if is_running:
        stop_event.set()
        return "🛑 程序已停止"
    return "🛑 程序已经停止"

@app.route('/log')
def log():
    def generate():
        with open('screenshot.log', 'r') as f:
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                yield f"data: {line}\n\n"
    return Response(generate(), mimetype='text/event-stream')

@app.route('/images')
def images():
    image_paths = []
    for root, dirs, files in os.walk(SAVE_DIR):
        for file in files:
            if file.endswith('.png'):
                image_paths.append(os.path.join(root, file))
    return render_template('images.html', image_paths=image_paths)

@app.route('/screenshot/<path:filename>')
def get_screenshot(filename):
    base_dir = os.path.abspath(SAVE_DIR)
    target_path = os.path.join(base_dir, filename)
    
    if not target_path.startswith(base_dir):
        return "🛑 非法路径访问", 403
        
    if not os.path.exists(target_path):
        return "🛑 文件不存在", 404
        
    return send_from_directory(SAVE_DIR, filename)

@app.route('/api/images')
def api_images():
    path = request.args.get('path', '')
    base_dir = os.path.abspath(SAVE_DIR)
    target_dir = os.path.join(base_dir, path)
    
    if not target_dir.startswith(base_dir):
        return jsonify({"error": "🛑 非法路径访问"}), 403
    
    if not os.path.exists(target_dir):
        return jsonify({"error": "🛑 路径不存在"}), 404
    
    directories = []
    images = []
    
    try:
        for item in sorted(os.listdir(target_dir), reverse=True):
            item_path = os.path.join(target_dir, item)
            if os.path.isdir(item_path):
                directories.append({"name": item})
            elif item.lower().endswith('.png'):
                try:
                    timestamp = int(item.split('_')[1].split('.')[0])
                    time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
                    
                    rel_path = os.path.join(path, item) if path else item
                    images.append({
                        "name": item,
                        "url": f"/screenshot/{rel_path}",
                        "time": time_str
                    })
                except Exception as e:
                    logger.error(f"💀 解析文件 {item} 失败: {str(e)}")
    except Exception as e:
        logger.error(f"💀 读取目录错误: {str(e)}")
        return jsonify({"error": "💀 服务器错误"}), 500
    
    return jsonify({
        "directories": directories,
        "images": images
    })

if __name__ == "__main__":
    os.makedirs(SAVE_DIR, exist_ok=True)
    print_welcome()
    app.run(host='0.0.0.0', port=5001, debug=True)