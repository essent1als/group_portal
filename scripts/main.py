from flask import *
from pathlib import Path
import json
import traceback
from datetime import datetime, timedelta
import requests
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'  # Для сессий

BASE_DIR = Path(__file__).resolve().parent

# Конфигурация Modeus
MODEUS_BASE_URL = "https://sfedu.modeus.org"


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


def _get_today_lessons_from_static(static_schedule):
    """Получить расписание на сегодня из статического расписания"""
    if not static_schedule:
        return []
    
    today = datetime.now()
    weekday = today.weekday()  # 0 = понедельник, 6 = воскресенье
    
    if weekday == 6:  # Воскресенье - нет пар
        return []
    
    # Определяем четная или нечетная неделя (1-53)
    week_number = today.isocalendar()[1]
    is_even_week = week_number % 2 == 0
    week_key = "week_2" if is_even_week else "week_1"
    
    # Дни недели на русском
    days_map = {
        0: "Понедельник",
        1: "Вторник",
        2: "Среда",
        3: "Четверг",
        4: "Пятница",
        5: "Суббота"
    }
    
    today_name = days_map.get(weekday, "Понедельник")
    
    if week_key in static_schedule:
        week_schedule = static_schedule[week_key]
        if today_name in week_schedule:
            return week_schedule[today_name]
    
    return []


@app.route("/")
def home():
    full_schedule = _load_json("data/schedule.json", [])
    today_schedule = _get_today_schedule(full_schedule)
    
    # Загружаем статическое расписание для мобильных
    static_schedule = _load_json("data/schedule_static.json", {})
    today_lessons = _get_today_lessons_from_static(static_schedule)
    
    config = _load_json("data/config.json", {})
    modeus_url = config.get("modeus_url", "https://sfedu.modeus.org")
    modeus_embed = config.get("modeus_embed_url", "https://sfedu.modeus.org/schedule")
    
    user_agent = request.headers.get('User-Agent', '')
    is_mobile = is_mobile_device(user_agent)
    template = "mobile-index.html" if is_mobile else "index.html"
    
    return render_template(
        template,
        schedule=today_schedule,
        today_lessons=today_lessons,
        full_schedule=full_schedule,
        links=_load_json("data/links_flat.json", []),
        announcements=_load_json("data/announcements.json", []),
        group=_load_json("data/group.json", []),
        vk_config=_load_json("data/config.json", {"vk_group_id": 66692771, "vk_widget_width": "100%"}),
        modeus_url=modeus_url,
        modeus_embed_url=modeus_embed,
    )


@app.route("/schedule")
def schedule_page():
    config = _load_json("data/config.json", {})
    modeus_url = config.get("modeus_url", "https://sfedu.modeus.org")
    modeus_embed = config.get("modeus_embed_url", "https://sfedu.modeus.org/schedule")
    
    user_agent = request.headers.get('User-Agent', '')
    is_mobile = is_mobile_device(user_agent)
    template = "mobile-schedule.html" if is_mobile else "schedule.html"
    
    # Загружаем статическое расписание
    static_schedule = _load_json("data/schedule_static.json", {})
    
    # Данные об авторизации
    modeus_logged_in = session.get('modeus_logged_in', False)
    modeus_username = session.get('modeus_username', '')
    
    # Пробуем получить расписание из Modeus
    modeus_schedule = None
    if modeus_logged_in:
        schedule_data = _get_modeus_schedule_data()
        if schedule_data:
            modeus_schedule = _parse_modeus_schedule(schedule_data)
    
    return render_template(
        template, 
        schedule=_load_json("data/schedule.json", []),
        modeus_url=modeus_url,
        modeus_embed_url=modeus_embed,
        static_schedule=static_schedule,
        modeus_logged_in=modeus_logged_in,
        modeus_username=modeus_username,
        modeus_schedule=modeus_schedule
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


# ==================== Modeus (отключено) ====================

# Функции входа в Modeus отключены

@app.route("/modeus-login")
def modeus_login_page():
    """Перенаправление на вход в Modeus"""
    return redirect(url_for('schedule_page'))


@app.route("/modeus-login", methods=["POST"])
def modeus_login():
    """Вход в Modeus"""
    return redirect(url_for('schedule_page'))


@app.route("/modeus-logout")
def modeus_logout():
    """Выход из Modeus"""
    session.pop('modeus_logged_in', None)
    session.pop('modeus_username', None)
    session.pop('modeus_user_id', None)
    session.pop('modeus_cookies', None)
    
    return redirect(url_for('schedule_page'))


@app.route("/api/save-schedule", methods=["POST"])
def save_schedule():
    """Сохранение расписания от клиента (после парсинга)"""
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "Нет данных"})
        
        # Сохраняем в файл schedule_static.json
        schedule_path = BASE_DIR / "data" / "schedule_static.json"
        
        with open(schedule_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error saving schedule: {e}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/data/schedule_static.json")
def serve_schedule_json():
    """Отдача файла расписания"""
    return send_from_directory(BASE_DIR / "data", "schedule_static.json")


def _get_modeus_schedule_data():
    """Получить данные расписания из Modeus"""
    if not session.get('modeus_logged_in'):
        return None
    
    cookies = session.get('modeus_cookies', {})
    if not cookies:
        return None
    
    try:
        session_req = requests.Session()
        session_req.cookies.update(cookies)
        
        # Пробуем разные endpoints для получения расписания
        # 1. API календаря
        calendar_url = f"{MODEUS_BASE_URL}/api/schedule-calendar/my"
        params = {
            'timeZone': '"Europe/Moscow"',
            'calendar': '{"view":"agendaWeek"}'
        }
        response = session_req.get(calendar_url, params=params, timeout=15)
        
        if response.status_code == 200:
            return response.json()
        
        # 2. Пробуем получить персональное расписание
        personal_url = f"{MODEUS_BASE_URL}/api/schedule-builder/persons/{session.get('modeus_user_id')}/calendar-view"
        response = session_req.get(personal_url, timeout=15)
        
        if response.status_code == 200:
            return response.json()
        
        return None
        
    except Exception as e:
        print(f"Error fetching Modeus schedule: {e}")
        return None


def _parse_modeus_schedule(schedule_data):
    """Парсит данные расписания Modeus в удобный формат"""
    if not schedule_data:
        return {}
    
    # Структура для хранения расписания
    schedule = {
        "week_1": {},
        "week_2": {}
    }
    
    days_map = {
        "Monday": "Понедельник",
        "Tuesday": "Вторник",
        "Wednesday": "Среда",
        "Thursday": "Четверг",
        "Friday": "Пятница",
        "Saturday": "Суббота",
        "Sunday": "Воскресенье"
    }
    
    try:
        events = schedule_data.get('events', [])
        if not events:
            events = schedule_data.get('data', [])
        
        for event in events:
            # Извлекаем данные о занятии
            start = event.get('start', {})
            end = event.get('end', {})
            title = event.get('title', 'Занятие')
            
            # Время
            start_time = start.get('time', '')
            end_time = end.get('time', '')
            time_str = f"{start_time} - {end_time}"
            
            # День недели
            date = start.get('date', '')
            
            # Преподаватель
            teachers = event.get('teachers', [])
            teacher_name = teachers[0].get('name', '') if teachers else ''
            
            # Аудитория
            rooms = event.get('rooms', [])
            room_name = rooms[0].get('name', '') if rooms else ''
            
            # Тип занятия (лекция, практика и т.д.)
            event_type = event.get('eventType', {}).get('name', '')
            
            lesson = {
                "time": time_str,
                "subject": title,
                "type": event_type,
                "teacher": teacher_name,
                "room": room_name
            }
            
            # Добавляем в структуру
            # Определяем день недели
            weekday = 0
            if date:
                from datetime import datetime
                try:
                    d = datetime.strptime(date, '%Y-%m-%d')
                    weekday = d.weekday()
                except:
                    pass
            
            day_names = list(days_map.values())
            if weekday < len(day_names):
                day_name = day_names[weekday]
                
                # Определяем неделю (чётная/нечётная)
                if date:
                    try:
                        d = datetime.strptime(date, '%Y-%m-%d')
                        week_num = d.isocalendar()[1] % 2
                        week_key = "week_2" if week_num == 0 else "week_1"
                    except:
                        week_key = "week_1"
                else:
                    week_key = "week_1"
                
                if day_name not in schedule[week_key]:
                    schedule[week_key][day_name] = []
                schedule[week_key][day_name].append(lesson)
                
    except Exception as e:
        print(f"Error parsing Modeus schedule: {e}")
    
    return schedule


@app.route("/api/fetch-modeus-schedule", methods=["POST"])
def fetch_modeus_schedule_with_auth():
    """
    API endpoint для получения и сохранения расписания с Modeus
    Принимает учетные данные пользователя
    """
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "Нет данных"})
        
        login = data.get('login', '')
        password = data.get('password', '')
        
        if not login or not password:
            return jsonify({"success": False, "error": "Введите логин и пароль"})
        
        # Создаём сессию для запросов
        session_req = requests.Session()
        
        try:
            # Пробуем войти через API Modeus
            api_url = f"{MODEUS_BASE_URL}/api/sessions"
            
            login_data = {
                "login": login,
                "password": password
            }
            
            response = session_req.post(api_url, json=login_data, timeout=15)
            
            if response.status_code == 201:
                # Успешный вход
                user_data = response.json()
                user_id = user_data.get('person', {}).get('id', '')
                
                # Получаем расписание
                schedule_data = _fetch_user_schedule(session_req, user_id)
                
                if schedule_data:
                    parsed = _parse_modeus_schedule(schedule_data)
                    
                    # Сохраняем
                    schedule_path = BASE_DIR / "data" / "schedule_static.json"
                    with open(schedule_path, "w", encoding="utf-8") as f:
                        json.dump(parsed, f, ensure_ascii=False, indent=2)
                    
                    return jsonify({"success": True, "message": "Расписание обновлено", "data": parsed})
                else:
                    return jsonify({"success": False, "error": "Не удалось получить расписание"})
            else:
                return jsonify({"success": False, "error": f"Ошибка входа: {response.status_code}"})
                
        except requests.RequestException as e:
            return jsonify({"success": False, "error": f"Ошибка соединения: {str(e)}"})
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


def _fetch_user_schedule(session_req, user_id):
    """Получить расписание для пользователя"""
    try:
        # Пробуем разные endpoints
        urls_to_try = [
            f"{MODEUS_BASE_URL}/api/schedule-builder/persons/{user_id}/calendar-view",
            f"{MODEUS_BASE_URL}/api/schedule-calendar/my",
            f"{MODEUS_BASE_URL}/api/schedule/own",
        ]
        
        for url in urls_to_try:
            try:
                response = session_req.get(url, timeout=15)
                if response.status_code == 200:
                    try:
                        return response.json()
                    except:
                        pass
            except:
                continue
        
        return None
    except Exception as e:
        print(f"Error fetching user schedule: {e}")
        return None


@app.errorhandler(500)
def server_error(e):
    return "<h1>500</h1><p>Внутренняя ошибка сервера</p>", 500


if __name__ == "__main__":
    app.run(debug=True)
