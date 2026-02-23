import requests
import pandas as pd
from bs4 import BeautifulSoup
import json
import os
import time

# Cấu hình Telegram lấy từ GitHub Secrets
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DATA_FILE = "data.json"
URL = "https://zh.wikipedia.org/wiki/%E4%B8%AD%E5%9B%BD%E5%A4%A7%E9%99%86%E7%94%B5%E8%A7%86%E5%89%A7%E5%88%97%E8%A1%A8_(2026%E5%B9%B4)"

def send_telegram(message):
    if not TOKEN or not CHAT_ID:
        print("Thiếu Token hoặc Chat ID")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    requests.post(url, json=payload)

def get_wiki_data():
    print("Đang tải dữ liệu từ Wiki...")
    try:
        response = requests.get(URL)
        response.encoding = 'utf-8' # Đảm bảo không lỗi font tiếng Trung
        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"Lỗi tải trang: {e}")
        return {}

    # Logic phân loại bảng dựa trên tiêu đề (Headline) phía trước nó
    current_status = None
    movies = {} # Format: {'Tên phim': 'Trạng thái'}

    # Duyệt qua các thẻ tiêu đề và bảng
    # Wiki cấu trúc thường là: h2/h3/dl -> table
    for element in soup.find_all(['h2', 'h3', 'dl', 'table']):
        tag_name = element.name
        text = element.get_text().strip()

        if tag_name in ['h2', 'h3', 'dl']:
            # Xác định trạng thái dựa trên từ khóa bạn yêu cầu
            if "禁播" in text or "2020年" in text:
                current_status = "IGNORE"
            elif "开拍中" in text:
                current_status = "Đang quay 🎬"
            elif "待播" in text:
                current_status = "Chờ chiếu ⏳"
            elif "电视剧" in text or "网络剧" in text:
                # Nếu không phải chờ chiếu hay đang quay thì là đã có lịch
                # Cần cẩn thận logic ở đây vì mục '待播' cũng chứa chữ '电视剧'
                # Nhưng code chạy tuần tự từ trên xuống, nên các mục con sẽ được update
                if "待播" not in text and "开拍中" not in text:
                    current_status = "Đã có lịch 📺"
        
        elif tag_name == 'table':
            if current_status == "IGNORE" or current_status is None:
                continue
            
            # Phân tích bảng
            try:
                # Dùng pandas đọc bảng cho lẹ
                df = pd.read_html(str(element))[0]
                # Tìm cột chứa tên phim. Thường là cột '剧名' hoặc cột đầu tiên
                col_name = None
                for col in df.columns:
                    if '剧名' in str(col):
                        col_name = col
                        break
                if not col_name: 
                    col_name = df.columns[0] # Mặc định cột 0
                
                # Lưu vào dict
                for movie_name in df[col_name].dropna():
                    # Làm sạch tên phim (bỏ mấy cái chú thích [1][2] nếu có)
                    clean_name = str(movie_name).split('[')[0].strip()
                    if len(clean_name) > 1:
                        movies[clean_name] = current_status
            except Exception as e:
                continue
                
    return movies

def compare_and_notify(new_data):
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        old_data = {}

    changes = []
    
    # 1. Kiểm tra phim chuyển trạng thái (Quan trọng nhất)
    # Logic ưu tiên: Đang quay -> Chờ chiếu -> Có lịch
    
    for name, new_status in new_data.items():
        old_status = old_data.get(name)
        
        if old_status and old_status != new_status:
            # Chỉ báo nếu có sự thay đổi "tiến lên" (hoặc thay đổi bất kỳ tùy bạn)
            changes.append(f"🔄 <b>{name}</b>: {old_status} ➡ {new_status}")
        
        # Nếu muốn báo cả phim mới xuất hiện thì mở comment dưới:
        # elif not old_status:
        #    changes.append(f"🆕 <b>{name}</b>: Mới thêm vào mục {new_status}")

    if changes:
        msg = f"🔔 <b>Cập nhật Phim Trung Quốc 2026</b>\n\n" + "\n".join(changes)
        print("Phát hiện thay đổi, đang gửi Telegram...")
        send_telegram(msg)
    else:
        print("Không có thay đổi trạng thái nào.")

    # Lưu dữ liệu mới
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    data = get_wiki_data()
    if data:
        compare_and_notify(data)