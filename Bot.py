import logging
import sqlite3
from telegram import Update
from telegram.ext import (
    Application, ChatJoinRequestHandler, CommandHandler, ContextTypes,
    ConversationHandler, MessageHandler, filters
)
from datetime import datetime, timedelta

# Включите логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Токен бота и ваш Telegram ID
BOT_TOKEN = '7933619829:AAFtJ1eCfnn5VXdJSQf7S15-vx6-yA9jvvg'
YOUR_USER_ID = 5929692940

# Абсолютный путь к базе данных
DB_PATH = '/root/Zayavka/BD/BD/join_requests.db'


# Глобальные переменные
total_requests = 0
last_reset_date = datetime.now().date()
weekly_stats = {}

# Состояния для ConversationHandler
WAITING_FOR_USER_ID, WAITING_FOR_REASON, WAITING_FOR_LEAD_NAME = range(3)

def init_db():
    """Создает базы данных и таблицы, если они не существуют, и обновляет структуру."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Таблица заявок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            user_id INTEGER,
            username TEXT,
            full_name TEXT,
            chat_id INTEGER,
            chat_title TEXT,
            request_date TEXT
        )
    ''')

    # Таблица черного списка
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blacklist (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            lead_name TEXT,
            reason TEXT,
            added_date TEXT
        )
    ''')

    # Проверка и добавление столбца lead_name, если его нет
    cursor.execute("PRAGMA table_info(blacklist)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'lead_name' not in columns:
        cursor.execute('ALTER TABLE blacklist ADD COLUMN lead_name TEXT')
        logging.info("Добавлен столбец lead_name в таблицу blacklist")

    conn.commit()
    conn.close()

# Инициализация базы данных при запуске
init_db()

def update_weekly_stats():
    """Обновляет статистику за неделю."""
    global weekly_stats
    current_date = datetime.now().date()
    week_ago = current_date - timedelta(days=7)
    weekly_stats = {date: count for date, count in weekly_stats.items() if date > week_ago}
    weekly_stats[current_date] = total_requests

def check_blacklist(user_id):
    """Проверяет, находится ли пользователь в черном списке."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT lead_name, reason, added_date FROM blacklist WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result

async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик заявок на вступление в канал."""
    global total_requests, last_reset_date

    join_request = update.chat_join_request
    user = join_request.from_user
    chat = join_request.chat
    current_date = datetime.now().date()

    if current_date > last_reset_date:
        total_requests = 0
        last_reset_date = current_date

    total_requests += 1
    update_weekly_stats()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Проверка черного списка
    blacklist_info = check_blacklist(user.id)

    cursor.execute('SELECT chat_title, request_date FROM requests WHERE user_id = ?', (user.id,))
    existing_requests = cursor.fetchall()

    message = (
        f"Новая заявка на вступление!\n"
        f"Пользователь: {user.full_name} (@{user.username if user.username else 'нет username'})\n"
        f"ID: {user.id}\n"
        f"Канал: {chat.title} (@{chat.username if chat.username else 'нет username'})\n"
        f"Дата и время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Всего заявок за день: {total_requests}"
    )

    if blacklist_info:
        lead_name, reason, added_date = blacklist_info
        message += (
            f"\n\n⚠️ ВНИМАНИЕ: ПОЛЬЗОВАТЕЛЬ В ЧЕРНОМ СПИСКЕ ⚠️\n"
            f"Имя лида: {lead_name if lead_name else 'Не указано'}\n"
            f"Комментарии:\n{reason}\n"
            f"Впервые добавлен: {added_date}"
        )

    if existing_requests:
        message += "\n\nРанее подавал заявки в:\n"
        for req in existing_requests:
            message += f"- {req[0]} ({req[1]})\n"

    cursor.execute('''
        INSERT INTO requests (user_id, username, full_name, chat_id, chat_title, request_date)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user.id, user.username, user.full_name, chat.id, chat.title, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()

    await context.bot.send_message(chat_id=YOUR_USER_ID, text=message)
    logging.info(f"Получена заявка от {user.full_name} (@{user.username}) в {chat.title}")

async def reset_requests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для ручного сброса счётчика заявок: /resetrequests."""
    global total_requests, last_reset_date, weekly_stats

    if update.effective_user.id != YOUR_USER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    total_requests = 0
    last_reset_date = datetime.now().date()
    update_weekly_stats()
    await update.message.reply_text(
        f"Счётчик заявок сброшен!\n"
        f"Текущая дата: {last_reset_date}\n"
        f"Всего заявок за день: {total_requests}"
    )
    logging.info("Счётчик заявок сброшен вручную")

async def weekly_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для получения статистики за неделю: /weeklystats."""
    if update.effective_user.id != YOUR_USER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    update_weekly_stats()
    current_date = datetime.now().date()
    week_ago = current_date - timedelta(days=6)

    stats_message = "Статистика заявок за последнюю неделю:\n"
    total_weekly = 0

    for i in range(7):
        date = week_ago + timedelta(days=i)
        count = weekly_stats.get(date, 0)
        total_weekly += count
        stats_message += f"{date.strftime('%Y-%m-%d')} ({['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'][date.weekday()]}): {count} заявок\n"

    stats_message += f"\nИтого за неделю: {total_weekly} заявок"
    await update.message.reply_text(stats_message)
    logging.info("Запрошена статистика за неделю")

async def global_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для получения глобальной статистики: /globalstats."""
    if update.effective_user.id != YOUR_USER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM requests')
    total_requests_db = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(DISTINCT user_id) FROM requests')
    unique_users = cursor.fetchone()[0]

    stats_message = (
        f"Глобальная статистика:\n"
        f"Всего заявок: {total_requests_db}\n"
        f"Уникальных пользователей: {unique_users}"
    )

    await update.message.reply_text(stats_message)
    logging.info("Запрошена глобальная статистика")
    conn.close()

async def search_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало процесса поиска пользователя: запрос ID."""
    if update.effective_user.id != YOUR_USER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return ConversationHandler.END

    await update.message.reply_text("Пожалуйста, введите ID пользователя.")
    return WAITING_FOR_USER_ID

async def search_user_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка введённого ID пользователя, вывод всей информации из базы."""
    user_input = update.message.text

    try:
        user_id = int(user_input)
    except ValueError:
        await update.message.reply_text("ID пользователя должен быть числом. Попробуйте снова.")
        return WAITING_FOR_USER_ID

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, username, full_name, chat_id, chat_title, request_date 
        FROM requests 
        WHERE user_id = ? 
        ORDER BY request_date DESC
    ''', (user_id,))
    requests = cursor.fetchall()
    conn.close()

    if not requests:
        await update.message.reply_text(f"Заявки от пользователя с ID {user_id} не найдены.")
    else:
        message = f"Найденные заявки от пользователя с ID {user_id}:\n\n"
        for i, (user_id, username, full_name, chat_id, chat_title, request_date) in enumerate(requests, 1):
            user_info = f"@{username}" if username else "нет username"
            message += (
                f"Заявка #{i}:\n"
                f"ID пользователя: {user_id}\n"
                f"Ник: {user_info}\n"
                f"Полное имя: {full_name}\n"
                f"ID чата: {chat_id}\n"
                f"Название чата: {chat_title}\n"
                f"Дата и время: {request_date}\n"
                f"{'-' * 20}\n"
            )
        await update.message.reply_text(message)

    logging.info(f"Запрошен поиск заявок для user_id {user_id}")
    return ConversationHandler.END

async def search_user_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена процесса поиска."""
    await update.message.reply_text("Поиск отменён.")
    return ConversationHandler.END

async def search_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для поиска заявок по chat_id: /searchchat <chat_id>."""
    if update.effective_user.id != YOUR_USER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    if not context.args:
        await update.message.reply_text("Пожалуйста, укажите ID чата. Пример: /searchchat -100123456789")
        return

    try:
        chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID чата должен быть числом.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT username, full_name, request_date 
        FROM requests 
        WHERE chat_id = ? 
        ORDER BY request_date DESC
    ''', (chat_id,))
    requests = cursor.fetchall()
    conn.close()

    if not requests:
        await update.message.reply_text(f"Заявки для чата с ID {chat_id} не найдены.")
    else:
        message = f"Найденные заявки для чата с ID {chat_id}:\n"
        for i, (username, full_name, request_date) in enumerate(requests, 1):
            user_info = f"@{username}" if username else full_name
            message += f"{i}. Пользователь: {user_info} ({request_date})\n"
        await update.message.reply_text(message)

    logging.info(f"Запрошен поиск заявок для chat_id {chat_id}")

async def blacklist_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало процесса добавления в черный список."""
    if update.effective_user.id != YOUR_USER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return ConversationHandler.END

    await update.message.reply_text("Пожалуйста, введите ID пользователя для добавления в черный список.")
    return WAITING_FOR_USER_ID

async def blacklist_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение ID пользователя для черного списка."""
    user_input = update.message.text

    try:
        user_id = int(user_input)
        context.user_data['blacklist_user_id'] = user_id
        await update.message.reply_text("Введите причину добавления в черный список.")
        return WAITING_FOR_REASON
    except ValueError:
        await update.message.reply_text("ID должен быть числом. Попробуйте снова.")
        return WAITING_FOR_USER_ID

async def blacklist_get_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение причины и запрос имени лида."""
    reason = update.message.text
    context.user_data['blacklist_reason'] = reason
    await update.message.reply_text("Введите имя лида (или напишите 'нет', если не хотите указывать).")
    return WAITING_FOR_LEAD_NAME

async def blacklist_get_lead_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Добавление пользователя в черный список с учетом истории комментариев и имени лида."""
    lead_name_input = update.message.text
    user_id = context.user_data.get('blacklist_user_id')
    new_reason = context.user_data.get('blacklist_reason')

    lead_name = None if lead_name_input.lower() == 'нет' else lead_name_input

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Проверяем, есть ли пользователь уже в черном списке
    cursor.execute('SELECT username, full_name, reason, added_date FROM blacklist WHERE user_id = ?', (user_id,))
    existing_entry = cursor.fetchone()

    if existing_entry:
        # Если пользователь уже в черном списке, добавляем новый комментарий
        username, full_name, existing_reason, added_date = existing_entry
        updated_reason = f"{existing_reason}\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {new_reason}"
        cursor.execute('''
            UPDATE blacklist 
            SET reason = ?, lead_name = ?
            WHERE user_id = ?
        ''', (updated_reason, lead_name, user_id))
        message = (
            f"Пользователь с ID {user_id} уже был в черном списке. Добавлен новый комментарий:\n"
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {new_reason}"
        )
    else:
        # Если пользователя нет в черном списке, добавляем новую запись
        cursor.execute('SELECT username, full_name FROM requests WHERE user_id = ? ORDER BY request_date DESC LIMIT 1', (user_id,))
        user_info = cursor.fetchone()
        username = user_info[0] if user_info else None
        full_name = user_info[1] if user_info else "Неизвестно"
        
        cursor.execute('''
            INSERT INTO blacklist (user_id, username, full_name, lead_name, reason, added_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, username, full_name, lead_name, f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {new_reason}", datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        message = (
            f"Пользователь с ID {user_id} добавлен в черный список.\n"
            f"Причина: {new_reason}\n"
            f"Имя лида: {lead_name if lead_name else 'Не указано'}"
        )

    conn.commit()
    conn.close()

    await update.message.reply_text(message)
    logging.info(f"Пользователь {user_id} обновлен/добавлен в черный список")
    return ConversationHandler.END

async def blacklist_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена добавления в черный список."""
    await update.message.reply_text("Добавление в черный список отменено.")
    return ConversationHandler.END

async def check_blacklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Проверка статуса пользователя в черном списке: /checkblacklist <user_id>."""
    if update.effective_user.id != YOUR_USER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    if not context.args:
        await update.message.reply_text("Укажите ID пользователя. Пример: /checkblacklist 123456789")
        return

    try:
        user_id = int(context.args[0])
        blacklist_info = check_blacklist(user_id)

        if blacklist_info:
            lead_name, reason, added_date = blacklist_info
            await update.message.reply_text(
                f"Пользователь с ID {user_id} в черном списке.\n"
                f"Имя лида: {lead_name if lead_name else 'Не указано'}\n"
                f"Комментарии:\n{reason}\n"
                f"Впервые добавлен: {added_date}"
            )
        else:
            await update.message.reply_text(f"Пользователь с ID {user_id} не найден в черном списке.")
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")

async def remove_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаление пользователя из черного списка: /removeblacklist <user_id>."""
    if update.effective_user.id != YOUR_USER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    if not context.args:
        await update.message.reply_text("Укажите ID пользователя. Пример: /removeblacklist 123456789")
        return

    try:
        user_id = int(context.args[0])
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Проверяем, есть ли пользователь в черном списке
        cursor.execute('SELECT lead_name FROM blacklist WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        if result:
            cursor.execute('DELETE FROM blacklist WHERE user_id = ?', (user_id,))
            conn.commit()
            await update.message.reply_text(f"Пользователь с ID {user_id} удалён из черного списка.")
            logging.info(f"Пользователь {user_id} удалён из черного списка")
        else:
            await update.message.reply_text(f"Пользователь с ID {user_id} не найден в черном списке.")
        
        conn.close()
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")

def main() -> None:
    """Запуск бота."""
    application = Application.builder().token(BOT_TOKEN).build()

    # ConversationHandler для поиска пользователя
    search_user_conv = ConversationHandler(
        entry_points=[CommandHandler("searchuser", search_user_start)],
        states={
            WAITING_FOR_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_user_process)],
        },
        fallbacks=[CommandHandler("cancel", search_user_cancel)],
    )

    # ConversationHandler для черного списка
    blacklist_conv = ConversationHandler(
        entry_points=[CommandHandler("addblacklist", blacklist_start)],
        states={
            WAITING_FOR_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, blacklist_get_id)],
            WAITING_FOR_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, blacklist_get_reason)],
            WAITING_FOR_LEAD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, blacklist_get_lead_name)],
        },
        fallbacks=[CommandHandler("cancel", blacklist_cancel)],
    )

    # Обработчики
    application.add_handler(ChatJoinRequestHandler(handle_join_request))
    application.add_handler(CommandHandler("resetrequests", reset_requests))
    application.add_handler(CommandHandler("weeklystats", weekly_stats_command))
    application.add_handler(CommandHandler("globalstats", global_stats_command))
    application.add_handler(search_user_conv)
    application.add_handler(CommandHandler("searchchat", search_chat))
    application.add_handler(blacklist_conv)
    application.add_handler(CommandHandler("checkblacklist", check_blacklist_command))
    application.add_handler(CommandHandler("removeblacklist", remove_blacklist))

    # Запуск бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
