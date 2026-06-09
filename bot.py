import http.client
import json
import time
import datetime
import os

# --- КОНФІГУРАЦІЯ ---
TOKEN = "8222253495:AAEcKWLqxzN8O2KgkaErHEszzjKeRR039og"
ADMIN_ID = 942015461
HOST = "api.telegram.org"
BASE_URL = f"/bot{TOKEN}"
DB_FILE = "database.json"

# Сховище для відстеження відправки щоденних сповіщень
last_reminder_date = ""

# --- РОБОТА З ДАНИМИ ---
def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Помилка читання бази: {e}")
    return {
        "event": {"city": "Черкаси", "date": "20.07.2026", "time": "12:00", "place": "Скейт-парк"},
        "users": {}
    }

def save_data():
    data = {"event": EVENT, "users": users}
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except PermissionError:
        print(f"⚠️ Файл {DB_FILE} зайнятий іншою програмою!")
    except Exception as e:
        print(f"❌ Помилка збереження: {e}")

# Завантаження початкових даних
data = load_data()
EVENT = data.get("event", {"city": "Черкаси", "date": "20.07.2026", "time": "12:00", "place": "Скейт-парк"})
# Перевірка на випадок, якщо в старій базі не було поля time
if "time" not in EVENT:
    EVENT["time"] = "12:00"

users = data.get("users", {})
states = {}

# --- ФУНКЦІЇ API ---
def send_message(chat_id, text, reply_markup=None):
    conn = http.client.HTTPSConnection(HOST)
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    headers = {"Content-Type": "application/json"}
    try:
        conn.request("POST", f"{BASE_URL}/sendMessage", body=json.dumps(payload), headers=headers)
        conn.getresponse()
    except Exception as e:
        print(f"Помилка API: {e}")
    finally:
        conn.close()

def get_updates(offset=None):
    conn = http.client.HTTPSConnection(HOST)
    url = f"{BASE_URL}/getUpdates?timeout=30"
    if offset: url += f"&offset={offset}"
    try:
        conn.request("GET", url)
        resp = conn.getresponse()
        return json.loads(resp.read())["result"]
    except:
        return []
    finally:
        conn.close()

def broadcast_update(message_text):
    """Розсилка всім учасникам"""
    for user_id in users.keys():
        send_message(int(user_id), message_text)

# --- КЛАВІАТУРИ ---
def admin_main_menu():
    return {
        "inline_keyboard": [
            [{"text": "📅 Змінити Дату", "callback_data": "edit_date"},
             {"text": "⏰ Змінити Час", "callback_data": "edit_time"}],
            [{"text": "🏙 Змінити Місто", "callback_data": "edit_city"}, 
             {"text": "📍 Змінити Місце", "callback_data": "edit_place"}]
        ]
    }

def date_selection_keyboard():
    keyboard = {"inline_keyboard": []}
    today = datetime.date.today()
    for i in range(1, 8): 
        d = (today + datetime.timedelta(days=i)).strftime("%d.%m.%Y")
        keyboard["inline_keyboard"].append([{"text": f"📅 {d}", "callback_data": f"set_date:{d}"}])
    keyboard["inline_keyboard"].append([{"text": "⬅️ Назад", "callback_data": "back_to_admin"}])
    return keyboard

def registration_buttons(user_id):
    return {
        "inline_keyboard": [
            [{"text": "✅ Прийняти", "callback_data": f"accept:{user_id}"},
             {"text": "❌ Відхилити", "callback_data": f"reject:{user_id}"}]
        ]
    }

# --- АВТОМАТИЧНІ НАГАДУВАННЯ ---
def check_and_send_reminders():
    global last_reminder_date
    now = datetime.datetime.now()
    today_str = now.strftime("%d.%m.%Y")
    
    # Спрацьовує раз на день
    if last_reminder_date != today_str:
        current_time_str = now.strftime("%H:%M")
        
        # 1. Автонадсилання списку учасників адміну о 09:00
        if current_time_str >= "09:00" and current_time_str <= "09:05":
            if not users:
                send_message(ADMIN_ID, "📋 Щоденний звіт: Список учасників поки порожній.")
            else:
                msg = "📋 <b>Щоденний звіт. Список учасників:</b>\n\n"
                for uid, u in users.items():
                    msg += f"• {u['name']} ({u.get('level', '-')}) - <b>{u['status']}</b>\n"
                send_message(ADMIN_ID, msg)
            last_reminder_date = today_str
            
        # 2. Автонагадування користувачам про контест о 10:00 (якщо до івенту менше 3 днів)
        elif current_time_str >= "10:00" and current_time_str <= "10:05":
            try:
                event_date = datetime.datetime.strptime(EVENT["date"], "%d.%m.%Y").date()
                days_left = (event_date - now.date()).days
                
                if 0 <= days_left <= 3:
                    reminder_text = (f"🔔 <b>Нагадування про контест!</b>\n\n"
                                     f"🛹 До BMX CONTEST залишилося днів: {days_left}\n"
                                     f"🏙 Місто: {EVENT['city']}\n"
                                     f"📅 Дата: {EVENT['date']}\n"
                                     f"⏰ Час: {EVENT['time']}\n"
                                     f"📍 Місце: {EVENT['place']}\n\n"
                                     f"Готуй байк! 🔥")
                    broadcast_update(reminder_text)
            except Exception as e:
                print(f"Помилка розрахунку дати для нагадування: {e}")
            last_reminder_date = today_str

# --- ЛОГІКА БОТА ---
print("Бот запущений 🛹")
last_update_id = None

while True:
    # Перевірка на необхідність надсилання автонагадувань
    check_and_send_reminders()

    updates = get_updates(last_update_id + 1 if last_update_id else None)

    for update in updates:
        last_update_id = update["update_id"]

        # ОБРОБКА КНОПОК
        callback = update.get("callback_query")
        if callback:
            cb_data = callback["data"]
            from_id = callback["from"]["id"]

            if from_id == ADMIN_ID:
                if cb_data == "edit_date":
                    send_message(ADMIN_ID, "Оберіть нову дату:", reply_markup=date_selection_keyboard())
                elif cb_data.startswith("set_date:"):
                    new_date = cb_data.split(":")[1]
                    EVENT["date"] = new_date
                    save_data()
                    send_message(ADMIN_ID, f"✅ Дату змінено на {new_date}.")
                    broadcast_update(f"<b>⚠️ Увага! Нова дата контесту: {new_date}</b>")
                elif cb_data == "edit_time":
                    send_message(ADMIN_ID, "Напишіть новий час контесту (наприклад, 15:00):")
                    states[ADMIN_ID] = "admin_expect_time"
                elif cb_data == "edit_city":
                    send_message(ADMIN_ID, "Напишіть назву нового міста:")
                    states[ADMIN_ID] = "admin_expect_city"
                elif cb_data == "edit_place":
                    send_message(ADMIN_ID, "Напишіть нову локацію:")
                    states[ADMIN_ID] = "admin_expect_place"
                elif cb_data == "back_to_admin":
                    send_message(ADMIN_ID, "Меню керування:", reply_markup=admin_main_menu())
                elif ":" in cb_data:
                    action, target_id = cb_data.split(":")
                    if target_id in users:
                        if action == "accept":
                            users[target_id]["status"] = "Прийнятий"
                            send_message(int(target_id), "✅ Твоя заявка прийнята! Побачимось!")
                        elif action == "reject":
                            users[target_id]["status"] = "Відхилений"
                            send_message(int(target_id), "❌ Твою заявку відхилено.")
                        save_data()
                        send_message(ADMIN_ID, f"Статус для користувача оновлено.")
            continue

        # ОБРОБКА ПОВІДОМЛЕНЬ
        message = update.get("message")
        if not message or "text" not in message: continue

        chat_id = message["chat"]["id"]
        text = message["text"]

        # Команди адміна
        if chat_id == ADMIN_ID:
            if text == "/admin":
                send_message(ADMIN_ID, "🛠 Панель керування:", reply_markup=admin_main_menu())
                continue
            elif text == "/list":
                if not users:
                    send_message(ADMIN_ID, "Список порожній.")
                else:
                    msg = "📋 <b>Список учасників:</b>\n\n"
                    for uid, u in users.items():
                        msg += f"• {u['name']} ({u.get('level', '-')}) - <b>{u['status']}</b>\n"
                    send_message(ADMIN_ID, msg)
                continue

        # Стани адміна (введення тексту)
        if chat_id == ADMIN_ID and chat_id in states:
            state = states[chat_id]
            if state == "admin_expect_time":
                EVENT["time"] = text
                save_data()
                send_message(ADMIN_ID, f"✅ Час змінено на: {text}", reply_markup=admin_main_menu())
                broadcast_update(f"<b>⏰ Зміна часу контесту!</b> Старт о: {text}")
                states.pop(chat_id)
            elif state == "admin_expect_city":
                EVENT["city"] = text
                save_data()
                send_message(ADMIN_ID, f"✅ Місто змінено на: {text}", reply_markup=admin_main_menu())
                broadcast_update(f"<b>🏙 Зміна міста!</b> Тепер проводимо тут: {text}")
                states.pop(chat_id)
            elif state == "admin_expect_place":
                EVENT["place"] = text
                save_data()
                send_message(ADMIN_ID, f"✅ Локацію змінено на: {text}", reply_markup=admin_main_menu())
                broadcast_update(f"<b>📍 Оновлено локацію!</b>\nНове місце: {text}")
                states.pop(chat_id)
            continue

        # Реєстрація користувача
        if text == "/start":
            send_message(chat_id, 
                f"🛹 <b>BMX CONTEST</b>\n\n🏙 Місто: {EVENT['city']}\n📅 Дата: {EVENT['date']}\n⏰ Час: {EVENT['time']}\n📍 Місце: {EVENT['place']}\n\n"
                f"Введіть ваше ім'я для реєстрації:"
            )
            states[chat_id] = "expect_name"
            continue

        if chat_id in states:
            state = states[chat_id]
            if state == "expect_name":
                users[str(chat_id)] = {"name": text, "status": "Очікує"}
                send_message(chat_id, "Ваш рівень (Beginner/Amateur/Pro):")
                states[chat_id] = "expect_level"
            elif state == "expect_level":
                users[str(chat_id)]["level"] = text
                send_message(chat_id, "Які трюки робиш?")
                states[chat_id] = "expect_tricks"
            elif state == "expect_tricks":
                users[str(chat_id)]["tricks"] = text
                save_data()
                
                # Повний звіт адміну
                u = users[str(chat_id)]
                info = (f"🆕 <b>Нова заявка!</b>\n\n👤 Ім'я: {u['name']}\n"
                        f"📊 Рівень: {u['level']}\n🚲 Трюки: {u['tricks']}")
                send_message(ADMIN_ID, info, reply_markup=registration_buttons(chat_id))
                
                send_message(chat_id, "✅ Реєстрація завершена! Очікуй підтвердження.")
                states.pop(chat_id)

    time.sleep(1)