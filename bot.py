import http.client
import json
import time
import datetime
import os

# --- КОНФІГУРАЦІЯ ---
TOKEN = "8222253495:AAFaFUA2ptzYnMGosC4r1wux8sbN3eo7Ovc"
ADMIN_ID = 942015461
HOST = "api.telegram.org"
BASE_URL = f"/bot{TOKEN}"
DB_FILE = "database.json"

last_reminder_date = ""

# --- РОБОТА З ДАНИМИ ---
def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] Помилка читання бази: {e}")
    return {
        "event": {"city": "Черкаси", "date": "20.07.2026", "time": "12:00", "place": "Скейт-парк"},
        "users": {},
        "polls": {}
    }

def save_data():
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump({"event": EVENT, "users": users, "polls": polls}, f, ensure_ascii=False, indent=4)
    except PermissionError:
        print(f"[WARN] Файл {DB_FILE} зайнятий іншою програмою!")
    except Exception as e:
        print(f"[ERROR] Помилка збереження: {e}")

data = load_data()
EVENT = data.get("event", {"city": "Черкаси", "date": "20.07.2026", "time": "12:00", "place": "Скейт-парк"})
if "time" not in EVENT:
    EVENT["time"] = "12:00"

users = data.get("users", {})
polls = data.get("polls", {})
states = {}

# --- API ---
def api_request(method, payload):
    """Єдина точка для всіх запитів до Telegram API."""
    conn = http.client.HTTPSConnection(HOST)
    try:
        conn.request(
            "POST",
            f"{BASE_URL}/{method}",
            body=json.dumps(payload),
            headers={"Content-Type": "application/json"}
        )
        resp = conn.getresponse()
        return json.loads(resp.read())
    except Exception as e:
        print(f"[ERROR] API {method}: {e}")
        return {}
    finally:
        conn.close()

def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    api_request("sendMessage", payload)

def answer_callback(callback_id, text="", alert=False):
    """Прибирає індикатор завантаження з кнопки."""
    api_request("answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": text,
        "show_alert": alert
    })

def get_updates(offset=None):
    conn = http.client.HTTPSConnection(HOST)
    url = f"{BASE_URL}/getUpdates?timeout=30"
    if offset:
        url += f"&offset={offset}"
    try:
        conn.request("GET", url)
        resp = conn.getresponse()
        return json.loads(resp.read()).get("result", [])
    except:
        return []
    finally:
        conn.close()

def broadcast(text, reply_markup=None):
    for uid in users:
        send_message(int(uid), text, reply_markup)

# --- ГОЛОСУВАННЯ ---
def get_next_poll_id():
    return str(max((int(k) for k in polls), default=0) + 1)

def poll_keyboard(poll_id):
    return {
        "inline_keyboard": [
            [{"text": f"  {opt}  ", "callback_data": f"vote:{poll_id}:{i}"}]
            for i, opt in enumerate(polls[poll_id]["options"])
        ]
    }

def send_poll_to_users(poll_id):
    p = polls[poll_id]
    text = (
        f"╔══════════════════╗\n"
        f"       🗳 ГОЛОСУВАННЯ\n"
        f"╚══════════════════╝\n\n"
        f"<b>{p['question']}</b>\n\n"
        f"Оберіть свій варіант 👇"
    )
    broadcast(text, reply_markup=poll_keyboard(poll_id))

def format_poll_results(poll_id):
    p = polls[poll_id]
    total = len(p["votes"])
    status = "🟢 Активне" if p["active"] else "🔴 Закрите"
    lines = [
        f"📊 <b>{p['question']}</b>",
        f"<i>{status}  •  Всього голосів: {total}</i>",
        "─────────────────────"
    ]
    for i, opt in enumerate(p["options"]):
        count = sum(1 for v in p["votes"].values() if v == i)
        pct = round(count / total * 100) if total else 0
        filled = round(pct / 10)
        bar = "🟦" * filled + "⬜" * (10 - filled)
        lines.append(f"<b>{opt}</b>")
        lines.append(f"{bar} {pct}%  ({count} гол.)")
        lines.append("")
    return "\n".join(lines)

# --- КЛАВІАТУРИ ---
def admin_main_menu():
    return {"inline_keyboard": [
        [{"text": "📅 Дата", "callback_data": "edit_date"},
         {"text": "⏰ Час", "callback_data": "edit_time"}],
        [{"text": "🏙 Місто", "callback_data": "edit_city"},
         {"text": "📍 Місце", "callback_data": "edit_place"}],
        [{"text": "🗳 Створити голосування", "callback_data": "create_poll"}],
        [{"text": "📊 Результати", "callback_data": "poll_results"},
         {"text": "🔴 Закрити опитування", "callback_data": "manage_polls"}]
    ]}

def date_selection_keyboard():
    today = datetime.date.today()
    rows = [
        [{"text": f"📅 {(today + datetime.timedelta(days=i)).strftime('%d.%m.%Y')}",
          "callback_data": f"set_date:{(today + datetime.timedelta(days=i)).strftime('%d.%m.%Y')}"}]
        for i in range(1, 8)
    ]
    rows.append([{"text": "⬅️ Назад", "callback_data": "back_to_admin"}])
    return {"inline_keyboard": rows}

def registration_buttons(user_id):
    return {"inline_keyboard": [[
        {"text": "✅ Прийняти", "callback_data": f"accept:{user_id}"},
        {"text": "❌ Відхилити", "callback_data": f"reject:{user_id}"}
    ]]}

def manage_polls_keyboard():
    active = [(pid, p) for pid, p in polls.items() if p["active"]]
    if not active:
        return None
    rows = [
        [{"text": f'⏹ {p["question"][:30]}', "callback_data": f"close_poll:{pid}"}]
        for pid, p in active
    ]
    rows.append([{"text": "⬅️ Назад", "callback_data": "back_to_admin"}])
    return {"inline_keyboard": rows}

# --- НАГАДУВАННЯ ---
def check_and_send_reminders():
    global last_reminder_date
    now = datetime.datetime.now()
    today_str = now.strftime("%d.%m.%Y")
    if last_reminder_date == today_str:
        return

    t = now.strftime("%H:%M")
    if "09:00" <= t <= "09:05":
        if not users:
            send_message(ADMIN_ID, "📋 Щоденний звіт: учасників поки немає.")
        else:
            msg = "📋 <b>Щоденний звіт</b>\n─────────────────────\n\n"
            for u in users.values():
                icon = "✅" if u["status"] == "Прийнятий" else ("❌" if u["status"] == "Відхилений" else "⏳")
                msg += f"{icon} {u['name']} <i>({u.get('level', '—')})</i>\n"
            send_message(ADMIN_ID, msg)
        last_reminder_date = today_str

    elif "10:00" <= t <= "10:05":
        try:
            days_left = (datetime.datetime.strptime(EVENT["date"], "%d.%m.%Y").date() - now.date()).days
            if 0 <= days_left <= 3:
                broadcast(
                    f"🔔 <b>Нагадування!</b>\n\n"
                    f"До BMX CONTEST залишилося: <b>{days_left} дн.</b>\n\n"
                    f"🏙 {EVENT['city']}\n"
                    f"📅 {EVENT['date']}  ⏰ {EVENT['time']}\n"
                    f"📍 {EVENT['place']}\n\n"
                    f"Готуй байк! 🔥"
                )
        except Exception as e:
            print(f"[ERROR] Нагадування: {e}")
        last_reminder_date = today_str

# --- ГОЛОВНИЙ ЦИКЛ ---
print("✅ Бот запущений 🛹")
last_update_id = None

while True:
    check_and_send_reminders()
    updates = get_updates(last_update_id + 1 if last_update_id else None)

    for update in updates:
        last_update_id = update["update_id"]

        # ── CALLBACK КНОПКИ ──
        callback = update.get("callback_query")
        if callback:
            cb_id   = callback["id"]
            cb_data = callback["data"]
            from_id = callback["from"]["id"]

            # Голосування — доступно всім
            if cb_data.startswith("vote:"):
                _, poll_id, idx = cb_data.split(":")
                uid = str(from_id)
                if poll_id in polls and polls[poll_id]["active"]:
                    if uid in polls[poll_id]["votes"]:
                        answer_callback(cb_id, "⚠️ Ви вже проголосували!", alert=True)
                    else:
                        polls[poll_id]["votes"][uid] = int(idx)
                        save_data()
                        chosen = polls[poll_id]["options"][int(idx)]
                        answer_callback(cb_id, f"✅ Прийнято: {chosen}")
                        send_message(from_id,
                            f"✅ <b>Ваш голос враховано!</b>\n\n"
                            f"Ви обрали: <b>{chosen}</b>"
                        )
                else:
                    answer_callback(cb_id, "❌ Голосування закрите", alert=True)
                continue

            # Адмін-кнопки
            if from_id == ADMIN_ID:
                if cb_data == "edit_date":
                    answer_callback(cb_id)
                    send_message(ADMIN_ID, "Оберіть нову дату:", reply_markup=date_selection_keyboard())

                elif cb_data.startswith("set_date:"):
                    new_date = cb_data.split(":", 1)[1]
                    EVENT["date"] = new_date
                    save_data()
                    answer_callback(cb_id, f"✅ Дату змінено на {new_date}")
                    send_message(ADMIN_ID, f"✅ Дату змінено на <b>{new_date}</b>", reply_markup=admin_main_menu())
                    broadcast(f"📢 <b>Увага!</b> Нова дата контесту: <b>{new_date}</b>")

                elif cb_data == "edit_time":
                    answer_callback(cb_id)
                    send_message(ADMIN_ID, "Введіть новий час (наприклад: 15:00):")
                    states[ADMIN_ID] = "admin_expect_time"

                elif cb_data == "edit_city":
                    answer_callback(cb_id)
                    send_message(ADMIN_ID, "Введіть назву нового міста:")
                    states[ADMIN_ID] = "admin_expect_city"

                elif cb_data == "edit_place":
                    answer_callback(cb_id)
                    send_message(ADMIN_ID, "Введіть нову локацію:")
                    states[ADMIN_ID] = "admin_expect_place"

                elif cb_data == "back_to_admin":
                    answer_callback(cb_id)
                    send_message(ADMIN_ID, "🛠 <b>Панель керування</b>", reply_markup=admin_main_menu())

                elif cb_data == "create_poll":
                    answer_callback(cb_id)
                    send_message(ADMIN_ID, "📝 Введіть запитання для голосування:")
                    states[ADMIN_ID] = "admin_expect_poll_question"

                elif cb_data == "poll_results":
                    answer_callback(cb_id)
                    if not polls:
                        send_message(ADMIN_ID, "📊 Голосувань ще не було.")
                    else:
                        for pid in polls:
                            send_message(ADMIN_ID, format_poll_results(pid))

                elif cb_data == "manage_polls":
                    answer_callback(cb_id)
                    kb = manage_polls_keyboard()
                    if kb:
                        send_message(ADMIN_ID, "Оберіть голосування для закриття:", reply_markup=kb)
                    else:
                        send_message(ADMIN_ID, "Немає активних голосувань.")

                elif cb_data.startswith("close_poll:"):
                    poll_id = cb_data.split(":", 1)[1]
                    if poll_id in polls:
                        polls[poll_id]["active"] = False
                        save_data()
                        answer_callback(cb_id, "🔴 Голосування закрито")
                        send_message(ADMIN_ID, format_poll_results(poll_id), reply_markup=admin_main_menu())

                elif ":" in cb_data:
                    action, target_id = cb_data.split(":", 1)
                    if target_id in users:
                        if action == "accept":
                            users[target_id]["status"] = "Прийнятий"
                            answer_callback(cb_id, "✅ Прийнято")
                            send_message(int(target_id),
                                "🎉 <b>Вітаємо!</b> Твою заявку прийнято!\n\nПобачимось на контесті 🛹"
                            )
                        elif action == "reject":
                            users[target_id]["status"] = "Відхилений"
                            answer_callback(cb_id, "❌ Відхилено")
                            send_message(int(target_id),
                                "😔 На жаль, твою заявку відхилено.\nСпробуй наступного разу!"
                            )
                        save_data()
                        send_message(ADMIN_ID, f"Статус оновлено: <b>{users[target_id]['name']}</b>")
                    else:
                        answer_callback(cb_id)
                else:
                    answer_callback(cb_id)
            continue

        # ── ПОВІДОМЛЕННЯ ──
        message = update.get("message")
        if not message or "text" not in message:
            continue

        chat_id = message["chat"]["id"]
        text = message["text"].strip()

        # Команди адміна
        if chat_id == ADMIN_ID:
            if text == "/admin":
                send_message(ADMIN_ID, "🛠 <b>Панель керування</b>", reply_markup=admin_main_menu())
                continue
            elif text == "/list":
                if not users:
                    send_message(ADMIN_ID, "📋 Список учасників порожній.")
                else:
                    msg = "📋 <b>Список учасників</b>\n─────────────────────\n\n"
                    for u in users.values():
                        icon = "✅" if u["status"] == "Прийнятий" else ("❌" if u["status"] == "Відхилений" else "⏳")
                        msg += f"{icon} {u['name']} <i>({u.get('level', '—')})</i>\n"
                    send_message(ADMIN_ID, msg)
                continue

        # Стани адміна
        if chat_id == ADMIN_ID and chat_id in states:
            state = states.pop(chat_id)

            if state == "admin_expect_time":
                EVENT["time"] = text
                save_data()
                send_message(ADMIN_ID, f"✅ Час змінено на: <b>{text}</b>", reply_markup=admin_main_menu())
                broadcast(f"📢 <b>Зміна!</b> Новий час початку: <b>{text}</b>")

            elif state == "admin_expect_city":
                EVENT["city"] = text
                save_data()
                send_message(ADMIN_ID, f"✅ Місто змінено на: <b>{text}</b>", reply_markup=admin_main_menu())
                broadcast(f"📢 <b>Зміна міста!</b> Тепер проводимо в: <b>{text}</b>")

            elif state == "admin_expect_place":
                EVENT["place"] = text
                save_data()
                send_message(ADMIN_ID, f"✅ Локацію змінено на: <b>{text}</b>", reply_markup=admin_main_menu())
                broadcast(f"📢 <b>Нова локація!</b>\n📍 {text}")

            elif state == "admin_expect_poll_question":
                poll_id = get_next_poll_id()
                polls[poll_id] = {"question": text, "options": [], "votes": {}, "active": False}
                states[ADMIN_ID] = f"admin_expect_poll_option:{poll_id}"
                send_message(ADMIN_ID,
                    f"✅ Запитання: <b>{text}</b>\n\n"
                    f"Тепер вводьте варіанти відповідей (по одному).\n"
                    f"Введіть /done коли закінчите (мін. 2 варіанти)."
                )

            elif state.startswith("admin_expect_poll_option:"):
                poll_id = state.split(":", 1)[1]
                if text == "/done":
                    if len(polls[poll_id]["options"]) < 2:
                        states[ADMIN_ID] = state
                        send_message(ADMIN_ID, "⚠️ Потрібно мінімум 2 варіанти. Введіть ще один:")
                    else:
                        polls[poll_id]["active"] = True
                        save_data()
                        send_poll_to_users(poll_id)
                        opts = "\n".join(f"  {i+1}. {o}" for i, o in enumerate(polls[poll_id]["options"]))
                        send_message(ADMIN_ID,
                            f"🚀 <b>Голосування запущено!</b>\n\n"
                            f"❓ {polls[poll_id]['question']}\n\n{opts}\n\n"
                            f"Розіслано всім учасникам ✅",
                            reply_markup=admin_main_menu()
                        )
                else:
                    polls[poll_id]["options"].append(text)
                    states[ADMIN_ID] = state
                    n = len(polls[poll_id]["options"])
                    send_message(ADMIN_ID,
                        f"✅ Варіант {n}: <b>{text}</b>\n\n"
                        f"Додайте ще або напишіть /done"
                    )
            continue

        # Реєстрація користувача
        if text == "/start":
            send_message(chat_id,
                f"🛹 <b>BMX CONTEST</b>\n"
                f"─────────────────────\n"
                f"🏙 Місто:  {EVENT['city']}\n"
                f"📅 Дата:   {EVENT['date']}\n"
                f"⏰ Час:    {EVENT['time']}\n"
                f"📍 Місце:  {EVENT['place']}\n"
                f"─────────────────────\n\n"
                f"Введіть ваше <b>ім'я</b> для реєстрації:"
            )
            states[chat_id] = "expect_name"
            continue

        if chat_id in states:
            state = states[chat_id]
            if state == "expect_name":
                users[str(chat_id)] = {"name": text, "status": "Очікує"}
                send_message(chat_id, f"Привіт, <b>{text}</b>! 👋\n\nТвій рівень катання?\n(Beginner / Amateur / Pro)")
                states[chat_id] = "expect_level"
            elif state == "expect_level":
                users[str(chat_id)]["level"] = text
                send_message(chat_id, "Які трюки ти робиш? Розкажи коротко 🚲")
                states[chat_id] = "expect_tricks"
            elif state == "expect_tricks":
                users[str(chat_id)]["tricks"] = text
                save_data()
                u = users[str(chat_id)]
                send_message(ADMIN_ID,
                    f"🆕 <b>Нова заявка!</b>\n"
                    f"─────────────────────\n"
                    f"👤 Ім'я:   {u['name']}\n"
                    f"📊 Рівень: {u['level']}\n"
                    f"🚲 Трюки:  {u['tricks']}",
                    reply_markup=registration_buttons(chat_id)
                )
                send_message(chat_id,
                    f"✅ <b>Заявку подано!</b>\n\n"
                    f"Очікуй підтвердження від адміністратора 🙌"
                )
                states.pop(chat_id)

    time.sleep(1)
