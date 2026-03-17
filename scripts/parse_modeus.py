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
    
    # Типы занятий
    type_map = {
        'mds-event-type-lect': 'Лекция',
        'mds-event-type-lab': 'Лабораторная',
        'mds-event-type-semi': 'Практика',
        'mds-event-type-pract': 'Практика'
    }
    
    # Находим все дни недели из заголовка
    day_headers = soup.find_all('th', class_='fc-day-header')
    
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
    
    # Сопоставляем дни с датами
    days_info = []
    for header in day_headers:
        classes = header.get('class', [])
        data_date = header.get('data-date', '')
        
        # Определяем день недели из классов
        day_name = None
        for cls in classes:
            if cls in day_map:
                day_name = day_map[cls]
                break
        
        # Форматируем дату (2026-03-16 -> 16.03)
        date_str = ""
        if data_date:
            try:
                dt = datetime.strptime(data_date, '%Y-%m-%d')
                date_str = dt.strftime('%d.%m')
            except:
                pass
        
        if day_name and data_date:
            days_info.append({
                'name': day_name,
                'date': date_str
            })
    
    print(f"Найдено дней: {len(days_info)}")
    
    if not days_info:
        return
    
    # Находим контейнер с событиями - fc-content-skeleton
    content_skeleton = soup.find('div', class_='fc-content-skeleton')
    if not content_skeleton:
        print("Не найден fc-content-skeleton")
        return
    
    # Находим все строки в скелетоне
    skeleton_table = content_skeleton.find('table')
    if not skeleton_table:
        print("Не найдена таблица в fc-content-skeleton")
        return
    
    tbody = skeleton_table.find('tbody')
    if not tbody:
        print("Не найден tbody")
        return
    
    tr = tbody.find('tr')
    if not tr:
        print("Не найдена строка tr")
        return
    
    # Находим все ячейки (первая - ось времени, остальные - дни)
    tds = tr.find_all('td')
    print(f"Найдено ячеек в скелетоне: {len(tds)}")
    
    # Запишем отладку
    with open('data/debug_parse.txt', 'w', encoding='utf-8') as f:
        f.write(f"Дней: {len(days_info)}\n")
        f.write(f"Ячеек в skeleton: {len(tds)}\n")
        for i, td in enumerate(tds):
            ev = td.find_all('a', class_='fc-time-grid-event')
            f.write(f"  td[{i}]: класс={td.get('class')}, событий={len(ev)}")
            if ev:
                f.write(f"\n    первое событие классы: {ev[0].get('class')}")
                title = ev[0].find('div', class_='fc-title')
                if title:
                    f.write(f", title: {title.get_text()[:50]}")
            f.write("\n")
    
    # Для каждого дня (пропускаем первую ячейку - ось времени)
    for idx, day_info in enumerate(days_info):
        cell_idx = idx + 1  # +1 because first is time axis
        if cell_idx >= len(tds):
            break
        
        td = tds[cell_idx]
        day_name = day_info['name']
        
        # Сохраняем дату для этого дня
        schedule["week_1"][day_name]["date"] = day_info['date']
        
        # Находим все события напрямую в td
        events = td.find_all('a', class_='fc-time-grid-event')
        
        for event in events:
            # Извлекаем время
            time_div = event.find('div', class_='fc-time')
            if time_div:
                time_full = time_div.get('data-full', '')
                if not time_full:
                    time_full = time_div.get_text(strip=True)
            else:
                time_full = ""
            
            # Извлекаем название предмета
            title_div = event.find('div', class_='fc-title')
            subject = title_div.get_text(strip=True) if title_div else ""
            
            # Извлекаем аудиторию
            room = ""
            if time_div:
                room_small = time_div.find('small', class_='text-muted')
                if room_small:
                    room = room_small.get_text(strip=True)
            
            # Определяем тип занятия
            event_classes = event.get('class', [])
            lesson_type = "Практика"  # по умолчанию
            for cls in event_classes:
                if cls in type_map:
                    lesson_type = type_map[cls]
                    break
            
            # Создаём запись
            lesson = {
                "time": time_full,
                "subject": subject,
                "type": lesson_type,
                "teacher": "",
                "room": room
            }
            
            schedule["week_1"][day_name]["lessons"].append(lesson)
            print(f"  {day_name}: {time_full} - {subject[:50]}...")
    
    # Сохраняем в JSON
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(schedule, f, ensure_ascii=False, indent=2)
    
    print(f"\nСохранено в: {output_json}")
    return schedule

if __name__ == '__main__':
    html_file = 'data/modeus_cache/schedule.html'
    json_file = 'data/schedule_static.json'
    
    print("=" * 50)
    print("Парсинг расписания Modeus")
    print("=" * 50)
    
    try:
        schedule = parse_modeus_schedule(html_file, json_file)
        print("\nГотово!")
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
