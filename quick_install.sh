#!/bin/bash
# 🦭 SealPlayerok Bot - Быстрый установщик
# Использование: curl -sSL URL | bash

set -e
SERVICE="seal-playerok-bot"
INSTALL_DIR="$HOME/SealPlayerokBot"

echo "🦭 Установка SealPlayerok Bot..."

# Установка зависимостей
sudo apt update -qq && sudo apt install -y -qq software-properties-common git python3.12 python3.12-venv 2>/dev/null || {
    echo "📦 Добавляем PPA для Python 3.12..."
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt update -qq
    sudo apt install -y -qq python3.12 python3.12-venv
}

# Клонирование
cd ~ && rm -rf SealPlayerokBot 2>/dev/null
git clone https://github.com/leizov/Seal-Playerok-Bot.git SealPlayerokBot
cd SealPlayerokBot

# Виртуальное окружение
python3.12 -m venv venv
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
deactivate

# Systemd сервис
sudo tee /etc/systemd/system/${SERVICE}.service > /dev/null << EOF
[Unit]
Description=SealPlayerok Bot
After=network.target
[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/bot.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1
[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable $SERVICE 2>/dev/null

# Команда управления
cat > $INSTALL_DIR/commands.sh << 'CMDEOF'
#!/bin/bash
SERVICE="seal-playerok-bot"
INSTALL_DIR="$HOME/SealPlayerokBot"

is_running() { systemctl is-active --quiet $SERVICE; }

case "$1" in
    start)
        if is_running; then echo "⚠️ Бот уже запущен!"; else sudo systemctl start $SERVICE && echo "✅ Бот запущен"; fi ;;
    stop)
        if ! is_running; then echo "⚠️ Бот уже остановлен!"; else sudo systemctl stop $SERVICE && echo "✅ Бот остановлен"; fi ;;
    restart) sudo systemctl restart $SERVICE && echo "✅ Бот перезапущен" ;;
    status)  if is_running; then echo "✅ Бот РАБОТАЕТ"; else echo "❌ Бот ОСТАНОВЛЕН"; fi; sudo systemctl status $SERVICE --no-pager ;;
    logs)    journalctl -u $SERVICE -f --no-hostname ;;
    setup)   echo "🔧 Настройка..."; cd $INSTALL_DIR && source venv/bin/activate && python bot.py ;;
    enable)  sudo systemctl enable $SERVICE 2>/dev/null && echo "✅ Автозапуск включён" ;;
    disable) sudo systemctl disable $SERVICE 2>/dev/null && echo "✅ Автозапуск отключён" ;;
    *)       echo "seal-pln start|stop|restart|status|logs|setup|enable|disable"; if is_running; then echo "Статус: ✅ Работает"; else echo "Статус: ❌ Остановлен"; fi ;;
esac
CMDEOF
chmod +x $INSTALL_DIR/commands.sh
sudo ln -sf $INSTALL_DIR/commands.sh /usr/local/bin/seal-pln 2>/dev/null || true

# Первоначальная настройка
echo ""
echo "🔧 Настройка токенов..."
echo "   Введи токены когда бот попросит."
echo "   После настройки нажми Ctrl+C"
echo ""
read -p "Нажми Enter для настройки..." -r
cd $INSTALL_DIR && source venv/bin/activate && python bot.py || true
deactivate

# Запуск как сервис
echo ""
echo "🚀 Запуск бота как сервис..."
sudo systemctl start $SERVICE

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║     🎉 SealPlayerok Bot установлен и запущен! 🎉     ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "┌────────────────────────────────────────────────────────┐"
echo "│  📢 Канал:  https://t.me/SealPlayerok                │"
echo "│  💬 Чат:    https://t.me/SealPlayerokChat            │"
echo "│  🤖 Бот:    https://t.me/SealPlayerokBot             │"
echo "│  📦 GitHub: github.com/leizov/Seal-Playerok-Bot      │"
echo "│  👨‍💻 Автор:  @leizov                                  │"
echo "└────────────────────────────────────────────────────────┘"
echo ""
echo "🎮 КОМАНДЫ:"
echo "  seal-pln start    - Запустить бота"
echo "  seal-pln stop     - Остановить бота"
echo "  seal-pln restart  - Перезапустить бота"
echo "  seal-pln status   - Статус"
echo "  seal-pln logs     - Логи (Ctrl+C выход)"
echo "  seal-pln setup    - Настройка токенов"
echo ""
echo "🦭 Проверь логи: seal-pln logs"
