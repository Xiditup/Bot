import logging
from telegram import Update
from telegram.ext import Application, ChatJoinRequestHandler, CommandHandler, ContextTypes
from datetime import datetime, timedelta

# Включите логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Токен бота и ваш Telegram ID
BOT_TOKEN = '7933619829:AAFtJ1eCfnn5VXdJSQf7S15-vx6-yA9jvvg'
YOUR_USER_ID = 5929692940

# Глобальные переменные
total_requests = 0  # Общее количество заявок за текущий день
last_reset_date = datetime.now().date()  # Дата последнего сброса счётчика текущего дня
weekly_stats = {}  # Словарь для статистики по дням недели (дата: количество заявок)


def update_weekly_stats():
    """Обновляет статистику за неделю"""
    global weekly_stats
    current_date = datetime.now().date()

    # Очищаем старые записи (более 7 дней)
    week_ago = current_date - timedelta(days=7)
    weekly_stats = {date: count for date, count in weekly_stats.items() if date > week_ago}

    # Добавляем или обновляем текущий день
    weekly_stats[current_date] = total_requests


async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик заявок на вступление в канал"""
    global total_requests, last_reset_date

    join_request = update.chat_join_request
    user = join_request.from_user
    chat = join_request.chat
    current_date = datetime.now().date()

    # Сброс счётчика, если день сменился
    if current_date > last_reset_date:
        total_requests = 0
        last_reset_date = current_date

    # Увеличиваем счётчик заявок
    total_requests += 1
    update_weekly_stats()  # Обновляем статистику

    # Формируем уведомление
    message = (
        f"Новая заявка на вступление!\n"
        f"Пользователь: {user.full_name} (@{user.username if user.username else 'нет username'})\n"
        f"ID: {user.id}\n"
        f"Канал: {chat.title} (@{chat.username if chat.username else 'нет username'})\n"
        f"Дата и время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Всего заявок за день: {total_requests}"
    )

    # Отправляем уведомление владельцу
    await context.bot.send_message(chat_id=YOUR_USER_ID, text=message)
    logging.info(f"Получена заявка от {user.full_name} (@{user.username}) в {chat.title}")


async def reset_requests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для ручного сброса счётчика заявок: /resetrequests"""
    global total_requests, last_reset_date, weekly_stats

    if update.effective_user.id != YOUR_USER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    total_requests = 0
    last_reset_date = datetime.now().date()
    update_weekly_stats()  # Обновляем статистику после сброса
    await update.message.reply_text(
        f"Счётчик заявок сброшен!\n"
        f"Текущая дата: {last_reset_date}\n"
        f"Всего заявок за день: {total_requests}"
    )
    logging.info("Счётчик заявок сброшен вручную")


async def weekly_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для получения статистики за неделю: /weeklystats"""
    if update.effective_user.id != YOUR_USER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    update_weekly_stats()  # Убеждаемся, что статистика актуальна
    current_date = datetime.now().date()
    week_ago = current_date - timedelta(days=6)  # Последние 7 дней, включая сегодня

    # Формируем статистику
    stats_message = "Статистика заявок за последнюю неделю:\n"
    total_weekly = 0

    for i in range(7):
        date = week_ago + timedelta(days=i)
        count = weekly_stats.get(date, 0)  # 0, если данных за день нет
        total_weekly += count
        stats_message += f"{date.strftime('%Y-%m-%d')} ({['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'][date.weekday()]}): {count} заявок\n"

    stats_message += f"\nИтого за неделю: {total_weekly} заявок"
    await update.message.reply_text(stats_message)
    logging.info("Запрошена статистика за неделю")


def main() -> None:
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()

    # Обработчики
    application.add_handler(ChatJoinRequestHandler(handle_join_request))
    application.add_handler(CommandHandler("resetrequests", reset_requests))
    application.add_handler(CommandHandler("weeklystats", weekly_stats_command))

    # Запуск бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
