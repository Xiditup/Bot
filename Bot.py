import logging
from telegram import Update
from telegram.ext import Application, ChatJoinRequestHandler, ContextTypes, CommandHandler
from datetime import datetime, timedelta
from collections import deque

# Включите логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Токен бота и ваш Telegram ID
BOT_TOKEN = '7933619829:AAFtJ1eCfnn5VXdJSQf7S15-vx6-yA9jvvg'
YOUR_USER_ID = 5929692940

# Глобальные переменные
total_requests = 0  # Общее количество заявок за день
auto_approve = False  # Флаг авто-принятия
approved_in_period = 0  # Сколько принято в текущем 30-минутном периоде
last_period_reset = datetime.now()  # Время последнего сброса периода
pending_requests = deque()  # Очередь необработанных заявок
MAX_PER_PERIOD = 5  # Максимум заявок за 30 минут
PERIOD_MINUTES = 30  # Период в минутах
welcome_message = (
    "Добро пожаловать в {chat_title}, @{username}!\n"
    "Мы рады видеть вас здесь. Ознакомьтесь с правилами и наслаждайтесь!"
)  # Для справки, но не используется в коде

async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик заявок на вступление в канал"""
    global total_requests, auto_approve, approved_in_period, last_period_reset

    join_request = update.chat_join_request
    user = join_request.from_user
    chat = join_request.chat

    # Добавляем заявку в очередь
    pending_requests.append((chat.id, user.id, user.full_name, user.username, chat.title, chat.username))
    total_requests += 1

    # Проверяем сброс 30-минутного периода
    current_time = datetime.now()
    if current_time >= last_period_reset + timedelta(minutes=PERIOD_MINUTES):
        approved_in_period = 0
        last_period_reset = current_time

    # Обрабатываем заявки
    if auto_approve:
        if len(pending_requests) == 1 and approved_in_period < MAX_PER_PERIOD:
            chat_id, user_id, full_name, username, chat_title, chat_username = pending_requests.popleft()
            await context.bot.approve_chat_join_request(chat_id=chat_id, user_id=user_id)
            approved_in_period += 1
            message = (
                f"Новая заявка принята (единственная)!\n"
                f"Пользователь: {full_name} (@{username})\n"
                f"ID: {user_id}\n"
                f"Канал: {chat_title} (@{chat_username})\n"
                f"Принято в текущем периоде: {approved_in_period}/{MAX_PER_PERIOD}\n"
                f"Всего заявок за день: {total_requests}"
            )
            await context.bot.send_message(chat_id=YOUR_USER_ID, text=message)
        elif len(pending_requests) > 0:
            while pending_requests and approved_in_period < MAX_PER_PERIOD:
                chat_id, user_id, full_name, username, chat_title, chat_username = pending_requests.popleft()
                await context.bot.approve_chat_join_request(chat_id=chat_id, user_id=user_id)
                approved_in_period += 1
                message = (
                    f"Новая заявка принята!\n"
                    f"Пользователь: {full_name} (@{username})\n"
                    f"ID: {user_id}\n"
                    f"Канал: {chat_title} (@{chat_username})\n"
                    f"Принято в текущем периоде: {approved_in_period}/{MAX_PER_PERIOD}\n"
                    f"Всего заявок за день: {total_requests}"
                )
                await context.bot.send_message(chat_id=YOUR_USER_ID, text=message)
        if pending_requests and approved_in_period >= MAX_PER_PERIOD:
            message = (
                f"Лимит {MAX_PER_PERIOD} заявок за {PERIOD_MINUTES} минут достигнут.\n"
                f"Ожидающих заявок: {len(pending_requests)}\n"
                f"Следующий период начнется в {last_period_reset + timedelta(minutes=PERIOD_MINUTES)}"
            )
            await context.bot.send_message(chat_id=YOUR_USER_ID, text=message)
    else:
        message = (
            f"Новая заявка на вступление (в очереди)!\n"
            f"Пользователь: {user.full_name} (@{user.username})\n"
            f"ID: {user.id}\n"
            f"Канал: {chat.title} (@{chat.username})\n"
            f"Всего заявок за день: {total_requests}"
        )
        await context.bot.send_message(chat_id=YOUR_USER_ID, text=message)

async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для изменения приветственного сообщения: /setwelcome <текст>"""
    global welcome_message

    if update.effective_user.id != YOUR_USER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    if not context.args:
        await update.message.reply_text(
            "Использование: /setwelcome <текст>\n"
            "Используйте {chat_title} для названия канала и {username} для имени пользователя.\n"
            "Текущий текст:\n" + welcome_message + "\n"
            "Настройте это сообщение в Telegram Business для отправки от вашего аккаунта."
        )
        return

    new_message = " ".join(context.args)
    welcome_message = new_message
    await update.message.reply_text(
        f"Приветственное сообщение обновлено:\n{welcome_message}\n"
        f"Настройте его в Telegram Business для отправки от вашего аккаунта."
    )

async def start_auto_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для включения авто-принятия: /startapprove"""
    global auto_approve, approved_in_period, last_period_reset

    if update.effective_user.id != YOUR_USER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    auto_approve = True
    approved_in_period = 0
    last_period_reset = datetime.now()

    await update.message.reply_text(
        f"Авто-принятие включено!\n"
        f"Лимит: {MAX_PER_PERIOD} заявок каждые {PERIOD_MINUTES} минут."
    )
    await process_pending_requests(update, context)

async def stop_auto_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для отключения авто-принятия: /stopapprove"""
    global auto_approve

    if update.effective_user.id != YOUR_USER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    auto_approve = False
    await update.message.reply_text("Авто-принятие отключено.")

async def process_pending_requests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка очереди заявок"""
    global approved_in_period, last_period_reset

    current_time = datetime.now()
    if current_time >= last_period_reset + timedelta(minutes=PERIOD_MINUTES):
        approved_in_period = 0
        last_period_reset = current_time

    if len(pending_requests) == 1 and approved_in_period < MAX_PER_PERIOD:
        chat_id, user_id, full_name, username, chat_title, chat_username = pending_requests.popleft()
        await context.bot.approve_chat_join_request(chat_id=chat_id, user_id=user_id)
        approved_in_period += 1
        message = (
            f"Новая заявка принята (единственная)!\n"
            f"Пользователь: {full_name} (@{username})\n"
            f"ID: {user_id}\n"
            f"Канал: {chat_title} (@{chat_username})\n"
            f"Принято в текущем периоде: {approved_in_period}/{MAX_PER_PERIOD}\n"
            f"Всего заявок за день: {total_requests}"
        )
        await context.bot.send_message(chat_id=YOUR_USER_ID, text=message)
    else:
        while pending_requests and approved_in_period < MAX_PER_PERIOD:
            chat_id, user_id, full_name, username, chat_title, chat_username = pending_requests.popleft()
            await context.bot.approve_chat_join_request(chat_id=chat_id, user_id=user_id)
            approved_in_period += 1
            message = (
                f"Новая заявка принята!\n"
                f"Пользователь: {full_name} (@{username})\n"
                f"ID: {user_id}\n"
                f"Канал: {chat_title} (@{chat_username})\n"
                f"Принято в текущем периоде: {approved_in_period}/{MAX_PER_PERIOD}\n"
                f"Всего заявок за день: {total_requests}"
            )
            await context.bot.send_message(chat_id=YOUR_USER_ID, text=message)

def main() -> None:
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()

    # Обработчики
    application.add_handler(ChatJoinRequestHandler(handle_join_request))
    application.add_handler(CommandHandler("startapprove", start_auto_approve))
    application.add_handler(CommandHandler("stopapprove", stop_auto_approve))
    application.add_handler(CommandHandler("setwelcome", set_welcome))

    # Запуск бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()