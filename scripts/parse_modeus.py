#!/usr/bin/env python3
"""
Парсер расписания из сохранённого HTML Modeus
"""
import json
import re
from bs4 import BeautifulSoup
from datetime import datetime

def parse_modeus_schedule(html_path: str, output_json: str):
    """Парсит HTML файл Modeus и сохраняет в JSON"""
    
    with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # День недели -> номер (Понедельник = 0)
    day_map = {
        'fc-mon': 'Понедельник',
        'fc-tue': 'Вторник',
        'fc-wed': 'Среда',
        'fc-thu': 'Четверг',
        'fc-fri': 'Пятница',
        'fc-sat': 'Суббота',
        'fc-sun': 'Воскресенье'
    }
    
    # Сопоставление времён с номерами пар
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
    
    # Карта названий дней для определения дат
    day_names_order = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    
    # Сначала найдём все даты из заголовков или календаря
    dates_found = {}
    
    # Ищем даты в заголовках
    date_headers = soup.find_all('th', class_='fc-col-header-cell-caption')
    for i, header in enumerate(date_headers):
        date_text = header.get_text(strip=True)
        # Формат: "16 марта" или "16.03"
        day_name = day_names_order[i] if i < len(day_names_order) else None
        if day_name and date_text:
            # Извлекаем число
            match = re.search(r'(\d+)', date_text)
            if match:
                day_num = match.group(1)
                dates_found[day_name] = f"{day_num}.03"
    
    # Создаём структуру расписания
    # Формат: "Понедельник": {"date": "18.03", "lessons": []}
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
    
    # Проставляем даты
    for day in day_names_order:
        if day in dates_found:
            schedule["week_1"][day]["date"] = dates_found[day]
        else:
            # Генерируем дату на основе соседних дней
            pass
    
    # Ищем все события (lessons)
    events = soup.find_all('div', class_='fc-event')
    
    all_lessons = []
    days_info = {}
    
    for event in events:
        try:
            # Время
            time_elem = event.find('span', class_='fc-time')
            time_str = time_elem.get_text(strip=True) if time_elem else ''
            
            # Предмет
            title_elem = event.find('span', class_='fc-title')
            subject = title_elem.get_text(strip=True) if title_elem else ''
            
            # Место (может быть в другом элементе)
            location_elem = event.find('span', class_='fc-location')
            room = location_elem.get_text(strip=True) if location_elem else ''
            
            # Определяем тип занятия
            event_class = event.get('class', [])
            lesson_type = 'Лекция'  # по умолчанию
            if 'practice' in event_class or 'лабораторн' in subject.lower():
                lesson_type = 'Лабораторная'
            elif 'семинар' in subject.lower() or 'практик' in subject.lower():
                lesson_type = 'Практика'
            
            # День недели
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
            
            day_name = ''
            for key, val in day_map.items():
                if key in (day_class or ''):
                    day_name = val
                    break
            
            if not day_name:
                continue
            
            # Номер пары
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
    
    # Сохраняем в JSON
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(schedule, f, ensure_ascii=False, indent=2)
    
    return schedule


if __name__ == '__main__':
    html_file = 'data/modeus_cache/schedule.html'
    json_file = 'data/schedule_static.json'
    
    print("=" * 50)
    print("Парсер расписания Modeus")
    print("=" * 50)
    
    try:
        schedule = parse_modeus_schedule(html_file, json_file)
        
        total_days = len(schedule.get('week_1', {}))
        total_lessons = sum(len(day['lessons']) for day in schedule.get('week_1', {}).values())
        
        print(f"Дней в расписании: {total_days}")
        print(f"Всего пар в расписании: {total_lessons}")
        
        for day_name, day_data in schedule['week_1'].items():
            if day_data['lessons']:
                print(f"\n{day_name}:")
                for lesson in day_data['lessons']:
                    print(f"  {lesson['time']} - {lesson['subject'][:50]}...")
        
        print(f"\nСохранено в: {json_file}")
        print("\nГотово!")
        
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
