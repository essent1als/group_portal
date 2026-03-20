#!/usr/bin/env python3
"""
Парсер расписания из сохранённого HTML Modeus
"""
import json
import re
import os
from bs4 import BeautifulSoup
from datetime import datetime

# Относительные пути от scripts/modeus/
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))

HTML_PATH = os.path.join(PROJECT_ROOT, "data", "modeus", "modeus_schedule.html")
OUTPUT_JSON = os.path.join(PROJECT_ROOT, "data", "modeus", "schedule_static.json")


def parse_modeus_schedule(html_path: str, output_json: str):
    """Парсит HTML файл Modeus и сохраняет в JSON"""
    
    if not os.path.exists(html_path):
        print(f"[ERROR] Файл не найден: {html_path}")
        return None
    
    with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    day_map = {
        'fc-mon': 'Понедельник',
        'fc-tue': 'Вторник',
        'fc-wed': 'Среда',
        'fc-thu': 'Четверг',
        'fc-fri': 'Пятница',
        'fc-sat': 'Суббота',
        'fc-sun': 'Воскресенье'
    }
    
    time_to_pair = {
        '08:00': 1, '08:30': 1,
        '09:50': 2, '10:00': 2,
        '11:55': 3, '12:00': 3,
        '13:45': 4, '14:00': 4,
        '15:50': 5, '16:00': 5,
        '17:35': 6, '18:00': 6,
        '19:15': 7, '19:30': 7,
        '20:55': 8, '21:00': 8
    }
    
    day_names_order = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    
    dates_found = {}
    
    date_headers = soup.find_all('th', class_='fc-col-header-cell-caption')
    for i, header in enumerate(date_headers):
        date_text = header.get_text(strip=True)
        day_name = day_names_order[i] if i < len(day_names_order) else None
        if day_name and date_text:
            match = re.search(r'(\d+)', date_text)
            if match:
                day_num = match.group(1)
                dates_found[day_name] = f"{day_num}.03"
    
    schedule = {
        "week_1": {
            "Понедельник": {"date": "", "lessons": []},
            "Вторник": {"date": "", "lessons": []},
            "Среда": {"date": "", "lessons": []},
            "Четверг": {"date": "", "lessons": []},
            "Пятница": {"date": "", "lessons": []},
            "Суббота": {"date": "", "lessons": []},
            "Воскресенье": {"date": "", "lessons": []}
        }
    }
    
    for day in day_names_order:
        if day in dates_found:
            schedule["week_1"][day]["date"] = dates_found[day]
    
    # Сначала соберём соответствие колонок дням
    day_headers = soup.find_all('th', class_='fc-day-header')
    day_columns = []
    for header in day_headers:
        date = header.get('data-date', '')
        classes = header.get('class', [])
        
        day_name = ''
        for c in classes:
            if 'fc-mon' in c: day_name = 'Понедельник'
            elif 'fc-tue' in c: day_name = 'Вторник'
            elif 'fc-wed' in c: day_name = 'Среда'
            elif 'fc-thu' in c: day_name = 'Четверг'
            elif 'fc-fri' in c: day_name = 'Пятница'
            elif 'fc-sat' in c: day_name = 'Суббота'
            elif 'fc-sun' in c: day_name = 'Воскресенье'
        
        if day_name:
            day_columns.append((day_name, date))
    
    print(f"Дни недели: {day_columns}")
    
    events = soup.find_all('a', class_='fc-time-grid-event')
    
    print(f"Найдено событий: {len(events)}")
    
    all_lessons = []
    days_info = {}
    
    # Определяем день по позиции в HTML
    event_cols = soup.find_all('td', class_='fc-content-col')
    
    # Создаем карту всех td.fc-content-col с их индексами
    td_index_map = {}
    for idx, td in enumerate(event_cols):
        # Используем id или позицию как ключ
        td_index_map[id(td)] = idx
    
    
    for idx, event in enumerate(events):
        try:
            # Новый формат - ищем внутри fc-content
            content = event.find('div', class_='fc-content')
            
            time_elem = content.find('div', class_='fc-time') if content else None
            time_str = time_elem.get_text(strip=True) if time_elem else ''
            
            title_elem = content.find('div', class_='fc-title') if content else None
            subject = title_elem.get_text(strip=True) if title_elem else ''
            
            # Определяем день по позиции колонки - ищем ближайший родительский td
            day_name = ''
            
            # Поднимаемся вверх от события к td
            # Структура: a -> div.fc-event-container -> div.fc-content-col -> td
            parent = event.parent
            target_td = None
            while parent:
                if parent.name == 'td':
                    target_td = parent
                    break
                parent = parent.parent
            
            if target_td:
                # Нашли td - теперь нужно определить его индекс среди всех td
                # Ищем все td на том же уровне (внутри той же таблицы)
                # Считаем сколько td с классом fc-content-col было перед этим
                
                # Альтернативный подход: ищем всех соседей td с классом fc-content-col
                all_td_with_col = soup.find_all('td', class_='fc-content-col')
                
                # Находим позицию target_td в общем списке td
                # Для этого ищем ближайший родительский tr и считаем позицию td в ней
                parent_tr = None
                p = target_td
                while p:
                    if p.name == 'tr':
                        parent_tr = p
                        break
                    p = p.parent
                
                if parent_tr:
                    # Находим все td в этой строке
                    tds_in_row = parent_tr.find_all('td', recursive=False)
                    
                    # Ищем позицию target_td в списке td
                    td_index = -1
                    for i, td in enumerate(tds_in_row):
                        if td is target_td:
                            td_index = i
                            break
                    
                    # td_index 1 = Понедельник, 2 = Вторник, и т.д.
                    day_idx = td_index - 1
                    if day_idx >= 0 and day_idx < len(day_columns):
                        day_name = day_columns[day_idx][0]
            
            if not day_name:
                # Запасной вариант - ищем по классам
                parent = event.parent
                day_class = ''
                while parent:
                    if parent.name == 'tr' or parent.name == 'tbody':
                        classes = parent.get('class', [])
                        for c in classes:
                            if c.startswith('fc-') and any(x in c for x in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']):
                                day_class = c
                                break
                    parent = parent.parent
                
                for key, val in day_map.items():
                    if key in (day_class or ''):
                        day_name = val
                        break
            
            if not day_name:
                continue
            
            # Определяем тип занятия
            event_class = event.get('class', [])
            lesson_type = 'Лекция'
            if 'lab' in event_class or 'лабораторн' in subject.lower():
                lesson_type = 'Лабораторная'
            elif 'semi' in event_class or 'семинар' in subject.lower() or 'практик' in subject.lower():
                lesson_type = 'Практика'
            
            # Извлекаем аудиторию из time элемента
            room = ''
            if time_elem:
                small = time_elem.find('small', class_='text-muted')
                if small:
                    room_text = small.get_text(strip=True)
                    # Аудитория обычно в формате "корпус / ауд"
                    room = room_text.split('/')[-1].strip() if '/' in room_text else room_text
            
            pair_num = 1
            for time_key, num in time_to_pair.items():
                if time_key in time_str:
                    pair_num = num
                    break
            
            if day_name not in days_info:
                days_info[day_name] = {'count': 0}
            days_info[day_name]['count'] += 1
            
            lesson = {
                'time': time_str,
                'subject': subject,
                'type': lesson_type,
                'teacher': '',
                'room': room
            }
            
            all_lessons.append(lesson)
            schedule["week_1"][day_name]["lessons"].append(lesson)
            
        except Exception as e:
            print(f"Error parsing event: {e}")
            continue
    
    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(schedule, f, ensure_ascii=False, indent=2)
    
    return schedule


if __name__ == '__main__':
    print("=" * 50)
    print("Парсер расписания Modeus")
    print("=" * 50)
    print(f"HTML: {HTML_PATH}")
    print(f"JSON: {OUTPUT_JSON}")
    print()
    
    try:
        schedule = parse_modeus_schedule(HTML_PATH, OUTPUT_JSON)
        
        if schedule:
            total_days = len(schedule.get('week_1', {}))
            total_lessons = sum(len(day['lessons']) for day in schedule.get('week_1', {}).values())
            
            print(f"Дней в расписании: {total_days}")
            print(f"Всего пар в расписании: {total_lessons}")
            
            for day_name, day_data in schedule['week_1'].items():
                if day_data['lessons']:
                    print(f"\n{day_name}:")
                    for lesson in day_data['lessons']:
                        print(f"  {lesson['time']} - {lesson['subject'][:50]}...")
            
            print(f"\nСохранено в: {OUTPUT_JSON}")
            print("\n[OK] Готово!")
        else:
            print("[ERROR] Не удалось распарсить расписание")
        
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
