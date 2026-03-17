from flask import *
from pathlib import Path
import json
import traceback
import requests
from datetime import datetime

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent


def is_mobile_device(user_agent: str) -> bool:
    """Определяет, является ли устройство мобильным"""
    mobile_keywords = ['android', 'webos', 'iphone', 'ipad', 'ipod', 'blackberry', 'windows phone', 'mobile']
    user_agent_lower = user_agent.lower()
    return any(keyword in user_agent_lower for keyword in mobile_keywords)


def _resolve_data_path(path_str: str) -> Path:
    primary_path = BASE_DIR / path_str

    if primary_path.exists():
        return primary_path

    if primary_path.name == "schedule.json":
        fallback_path = primary_path.with_name("sсhedule.json")
        if fallback_path.exists():
            return fallback_path

    return primary_path


def _load_json(path_str: str, default):
    path = _resolve_data_path(path_str)

    if not path.exists():
        return default

    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        return default


def _get_today_schedule(schedule_list):
    """Получить расписание на сегодня"""
    # Дни недели на русском
    days_map = {
        0: "Понедельник",
        1: "Вторник",
        2: "Среда",
        3: "Четверг",
        4: "Пятница",
        5: "Суббота",
        6: "Воскресенье"
    }
    
    today = datetime.now()
    today_day_name = days_map[today.weekday()]
    
    today_schedule = [item for item in schedule_list if item.get("day") == today_day_name]
    return today_schedule


@app.route("/")
def home():
    full_schedule = _load_json("data/schedule.json", [])
    today_schedule = _get_today_schedule(full_schedule)
    
    user_agent = request.headers.get('User-Agent', '')
    is_mobile = is_mobile_device(user_agent)
    template = "mobile-index.html" if is_mobile else "index.html"
    
    return render_template(
        template,
        schedule=today_schedule,
        full_schedule=full_schedule,
        links=_load_json("data/links_flat.json", []),
        announcements=_load_json("data/announcements.json", []),
        group=_load_json("data/group.json", []),
        vk_config=_load_json("data/config.json", {"vk_group_id": 66692771, "vk_widget_width": "100%"}),
    )


@app.route("/schedule")
def schedule_page():
    config = _load_json("data/config.json", {})
    modeus_url = config.get("modeus_url", "https://sfedu.modeus.org")
    modeus_embed = config.get("modeus_embed_url", "https://sfedu.modeus.org/schedule")
    
    user_agent = request.headers.get('User-Agent', '')
    is_mobile = is_mobile_device(user_agent)
    template = "mobile-schedule.html" if is_mobile else "schedule.html"
    
    return render_template(
        template, 
        schedule=_load_json("data/schedule.json", []),
        modeus_url=modeus_url,
        modeus_embed_url=modeus_embed
    )


@app.route("/links")
def links_page():
    user_agent = request.headers.get('User-Agent', '')
    is_mobile = is_mobile_device(user_agent)
    template = "mobile-links.html" if is_mobile else "links.html"
    return render_template(template, links=_load_json("data/links.json", []))


@app.route("/announcements")
def announcements_page():
    user_agent = request.headers.get('User-Agent', '')
    is_mobile = is_mobile_device(user_agent)
    template = "mobile-announcements.html" if is_mobile else "announcements.html"
    return render_template(template, announcements=_load_json("data/announcements.json", []))


@app.errorhandler(404)
def not_found(e):
    return render_template("index.html", schedule=[], links=[], announcements=[], group=[]), 404


@app.route("/api/vk-news")
def vk_news():
    """Получение новостей из ВКонтакте"""
    config = _load_json("data/config.json", {})
    group_id = config.get("vk_group_id", 66692771)
    access_token = config.get("vk_access_token", "")
    
    if not access_token or access_token == "YOUR_VK_ACCESS_TOKEN_HERE":
        return jsonify({"error": "VK access token not configured"}), 400
    
    try:
        # Получаем записи со стены группы
        url = "https://api.vk.com/method/wall.get"
        params = {
            "owner_id": f"-{group_id}",
            "count": 10,
            "access_token": access_token,
            "v": "5.131"
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if "error" in data:
            return jsonify({"error": data["error"]["error_msg"]}), 400
        
        posts = data.get("response", {}).get("items", [])
        
        # Обрабатываем посты
        processed_posts = []
        for post in posts:
            processed_post = {
                "id": post.get("id"),
                "date": post.get("date"),
                "text": post.get("text", ""),
                "likes": post.get("likes", {}).get("count", 0),
                "comments": post.get("comments", {}).get("count", 0),
                "reposts": post.get("reposts", {}).get("count", 0),
                "attachments": []
            }
            
            # Обрабатываем вложения
            attachments = post.get("attachments", [])
            for att in attachments:
                if att["type"] == "photo":
                    photos = att["photo"].get("sizes", [])
                    # Берём фото максимального размера
                    if photos:
                        max_photo = max(photos, key=lambda x: x.get("width", 0))
                        processed_post["attachments"].append({
                            "type": "photo",
                            "url": max_photo.get("url", "")
                        })
                elif att["type"] == "video":
                    processed_post["attachments"].append({
                        "type": "video",
                        "title": att["video"].get("title", "")
                    })
                elif att["type"] == "link":
                    processed_post["attachments"].append({
                        "type": "link",
                        "title": att["link"].get("title", ""),
                        "url": att["link"].get("url", "")
                    })
            
            processed_posts.append(processed_post)
        
        return jsonify({"posts": processed_posts})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/announcements", methods=["POST"])
def add_announcement():
    """Добавление нового объявления"""
    data = request.get_json()
    
    if not data or not data.get("text"):
        return jsonify({"error": "Текст объявления обязателен"}), 400
    
    text = data.get("text").strip()
    author = data.get("author", "Аноним").strip() or "Аноним"
    
    if not text:
        return jsonify({"error": "Текст объявления не может быть пустым"}), 400
    
    # Загружаем текущие объявления
    announcements = _load_json("data/announcements.json", [])
    
    # Создаём новое объявление
    new_id = max([a.get("id", 0) for a in announcements], default=0) + 1
    new_announcement = {
        "id": new_id,
        "text": text,
        "author": author,
        "date": datetime.now().strftime("%Y-%m-%d")
    }
    
    # Добавляем в начало списка
    announcements.insert(0, new_announcement)
    
    # Сохраняем
    path = _resolve_data_path("data/announcements.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(announcements, f, ensure_ascii=False, indent=2)
    
    return jsonify({"success": True, "announcement": new_announcement})


@app.errorhandler(500)
def server_error(e):
    return "<h1>500</h1><p>Внутренняя ошибка сервера</p>", 500


if __name__ == "__main__":
    app.run(debug=True)
