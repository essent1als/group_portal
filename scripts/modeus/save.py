#!/usr/bin/env python3
"""
Скрипт для сохранения HTML страницы Modeus через undetected-chromedriver
Использует постоянный профиль браузера для сохранения сессии
"""
import os
import sys
from datetime import datetime, timedelta
import undetected_chromedriver as uc

# Конфигурация - относительные пути от scripts/modeus/
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))

CHROME_PROFILE_PATH = os.path.join(PROJECT_ROOT, "chrome_profile")
MODEUS_URL = "https://sfedu.modeus.org"
MODEUS_SCHEDULE_URL = "https://sfedu.modeus.org/schedule/calendar"
OUTPUT_HTML = os.path.join(PROJECT_ROOT, "data", "modeus", "modeus_schedule.html")
OUTPUT_LOG = os.path.join(PROJECT_ROOT, "data", "modeus", "session_log.txt")
WARN_BEFORE_DAYS = 7


def get_driver():
    options = uc.ChromeOptions()
    
    profile_path = os.path.normpath(CHROME_PROFILE_PATH)
    os.makedirs(profile_path, exist_ok=True)
    
    options.add_argument(f"--user-data-dir={profile_path}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    driver = uc.Chrome(options=options, version_main=None)
    return driver


def check_session_expiry(driver):
    driver.get(MODEUS_URL)
    cookies = driver.get_cookies()
    
    if not cookies:
        print("[!] Куки не найдены. Войдите в систему вручную.")
        return False
    
    min_expiry = None
    
    print("\n" + "=" * 50)
    print("Информация о сессии:")
    print("=" * 50)
    
    for cookie in cookies:
        name = cookie['name']
        domain = cookie.get('domain', 'unknown')
        
        if 'expiry' in cookie:
            expiry_timestamp = cookie['expiry']
            expiry_date = datetime.fromtimestamp(expiry_timestamp)
            time_left = expiry_date - datetime.now()
            
            print(f"[COOKIE] {name}")
            print(f"   Домен: {domain}")
            print(f"   Истекает: {expiry_date.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Осталось: {time_left.days} дней")
            print()
            
            if name == 'tc01':
                if min_expiry is None or expiry_timestamp < min_expiry:
                    min_expiry = expiry_timestamp
            elif min_expiry is None:
                min_expiry = expiry_timestamp
        else:
            print(f"[COOKIE] {name} (session)")
            print(f"   Домен: {domain}")
            print(f"   Сессия без срока действия")
            print()
    
    try:
        user_avatar = driver.find_element("css selector", "[class*='user'] img, [class*='avatar'], .profile-avatar")
        if user_avatar:
            print("[OK] Сессия активна - пользователь залогинен")
    except:
        print("[!] Не удалось подтвердить вход (но куки есть)")
    
    if min_expiry:
        expiry_date = datetime.fromtimestamp(min_expiry)
        time_left = expiry_date - datetime.now()
        
        if time_left <= timedelta(days=WARN_BEFORE_DAYS):
            print(f"\n[WARNING] ВНИМАНИЕ: Сессия истекает через {time_left.days} дней!")
            print(f"   Пожалуйста, перелогиньтесь заранее.")
            print(f"   Для входа: {MODEUS_URL}")
            
            os.makedirs(os.path.dirname(OUTPUT_LOG), exist_ok=True)
            with open(OUTPUT_LOG, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M')} - WARNING: Сессия истекает через {time_left.days} дней\n")
    
    print("=" * 50 + "\n")
    return True


def save_schedule_page(driver):
    print(f"Открываю страницу расписания: {MODEUS_SCHEDULE_URL}")
    
    driver.get(MODEUS_SCHEDULE_URL)
    
    # Делаем скриншот для отладки
    driver.save_screenshot(os.path.join(PROJECT_ROOT, "data", "modeus", "screenshot.png"))
    print("Скриншот сохранён")
    
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    
    print("Ожидание загрузки расписания...")
    
    try:
        # Ждём появления элемента расписания (календарь)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "fc-calendar"))
        )
        print("Календарь загружен!")
    except:
        print("Не дождались календаря, используем время...")
        import time
        time.sleep(5)
    
    html_content = driver.page_source
    
    os.makedirs(os.path.dirname(OUTPUT_HTML), exist_ok=True)
    
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"[OK] Страница сохранена в: {OUTPUT_HTML}")
    return OUTPUT_HTML


def main():
    print("=" * 50)
    print("Сохранение страницы Modeus (undetected-chromedriver)")
    print("=" * 50)
    print(f"Профиль браузера: {CHROME_PROFILE_PATH}")
    print()
    
    driver = None
    try:
        driver = get_driver()
        
        session_ok = check_session_expiry(driver)
        
        if not session_ok:
            print("\n[ERROR] Сессия недействительна.")
            print(f"   Пожалуйста, залогиньтесь: {MODEUS_URL}")
            input("\nНажмите Enter после входа...")
            check_session_expiry(driver)
        
        output_path = save_schedule_page(driver)
        
        print("\n[OK] Готово!")
        
    except Exception as e:
        print(f"[ERROR] Ошибка: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()
