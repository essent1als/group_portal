#!/usr/bin/env python3
"""
Сохраняет HTML страницу Modeus после входа
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
from pathlib import Path

MODEUS_URL = "https://sfedu.modeus.org"
HTML_FILE = Path(__file__).parent.parent / "data" / "modeus_cache" / "schedule.html"

def main():
    print("=" * 60)
    print("   Сохранение HTML Modeus")
    print("=" * 60)
    print()
    print("Инструкция:")
    print("1. Откроется браузер Chrome")
    print("2. Войдите на https://sfedu.modeus.org")
    print("3. Откройте страницу расписания")
    print("4. Дождитесь полной загрузки")
    print("5. Скрипт автоматически сохранит HTML")
    print()
    
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        print("Открываем Modeus...")
        driver.get(MODEUS_URL)
        
        print("\n" + "="*60)
        print("ВНИМАНИЕ: Не закрывайте браузер!")
        print("Дождитесь пока страница полностью загрузится")
        print("Затем скрипт сам сохранит HTML и закроет браузер")
        print("="*60)
        
        # Ждём пока пользователь загрузит расписание
        print("\nОжидание 90 секунд...")
        time.sleep(90)
        
        print("Сохраняем HTML...")
        
        # Сохраняем весь HTML
        with open(HTML_FILE, 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        
        print(f"Сохранено в: {HTML_FILE}")
        
        # Также пробуем сохранить только видимую часть
        try:
            # Ищем элемент расписания
            body = driver.find_element("tag name", "body")
            body_html = body.get_attribute("innerHTML")
            
            body_file = Path(__file__).parent / "modeus_body.html"
            with open(body_file, 'w', encoding='utf-8') as f:
                f.write(body_html)
            print(f"Тело сохранено в: {body_file}")
        except:
            pass
        
        print("\nГОТОВО!")
        
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        driver.quit()
        print("Браузер закрыт")

if __name__ == "__main__":
    main()
