#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# 🦭 SealPlayerok Bot - Установщик для Ubuntu/Linux
# ═══════════════════════════════════════════════════════════════════════════════
# Использование:
#   curl -sSL https://raw.githubusercontent.com/leizov/Seal-Playerok-Bot/main/install.sh | bash
#   или
#   wget -qO- https://raw.githubusercontent.com/leizov/Seal-Playerok-Bot/main/install.sh | bash
# ═══════════════════════════════════════════════════════════════════════════════

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Конфигурация
REPO_URL="https://github.com/leizov/Seal-Playerok-Bot.git"
INSTALL_DIR="$HOME/SealPlayerokBot"
PYTHON_VERSION="3.12"
SERVICE_NAME="seal-playerok-bot"

# Логирование
log_info() {
    echo -e "${CYAN}🦭 [INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}✅ [OK]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠️  [WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}❌ [ERROR]${NC} $1"
}

log_step() {
    echo -e "\n${BLUE}═══════════════════════════════════════${NC}"
    echo -e "${BLUE}🌊 $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════${NC}\n"
}

# ASCII арт
show_banner() {
    echo -e "${CYAN}"
    cat << 'EOF'
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║    🦭 SealPlayerok Bot - Installer for Ubuntu/Linux 🦭   ║
    ║                                                           ║
    ║              Милый бот-помощник для Playerok              ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

# Проверка root
check_not_root() {
    if [ "$EUID" -eq 0 ]; then
        log_warning "Не рекомендуется запускать от root!"
        log_info "Продолжаем установку..."
    fi
}

# Проверка системы
check_system() {
    log_step "Проверка системы"
    
    # Проверяем что это Linux
    if [[ "$OSTYPE" != "linux-gnu"* ]]; then
        log_error "Этот установщик только для Linux!"
        exit 1
    fi
    
    # Проверяем Ubuntu/Debian
    if ! command -v apt &> /dev/null; then
        log_error "Требуется система с apt (Ubuntu/Debian)"
        exit 1
    fi
    
    log_success "Система: $(lsb_release -d 2>/dev/null | cut -f2 || cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2 | tr -d '"')"
}

# Установка системных зависимостей
install_dependencies() {
    log_step "Установка системных зависимостей"
    
    log_info "Обновление пакетов..."
    sudo apt update -qq
    
    log_info "Установка необходимых пакетов..."
    sudo apt install -y -qq \
        software-properties-common \
        git \
        curl \
        wget \
        build-essential \
        libssl-dev \
        libffi-dev \
        python3-dev \
        python3-pip \
        python3-venv \
        2>/dev/null
    
    log_success "Системные зависимости установлены"
}

# Установка Python 3.12
install_python() {
    log_step "Установка Python ${PYTHON_VERSION}"
    
    # Проверяем есть ли уже Python 3.12
    if command -v python${PYTHON_VERSION} &> /dev/null; then
        CURRENT_VERSION=$(python${PYTHON_VERSION} --version 2>&1 | cut -d' ' -f2)
        log_success "Python ${CURRENT_VERSION} уже установлен"
        return 0
    fi
    
    log_info "Добавление репозитория deadsnakes..."
    sudo add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || {
        log_warning "Не удалось добавить PPA, пробуем альтернативный метод..."
    }
    
    sudo apt update -qq
    
    log_info "Установка Python ${PYTHON_VERSION}..."
    sudo apt install -y -qq python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python${PYTHON_VERSION}-dev 2>/dev/null || {
        log_error "Не удалось установить Python ${PYTHON_VERSION}"
        log_info "Попробуйте установить вручную: sudo apt install python3.12"
        exit 1
    }
    
    # Проверяем установку
    if command -v python${PYTHON_VERSION} &> /dev/null; then
        log_success "Python $(python${PYTHON_VERSION} --version) установлен"
    else
        log_error "Python ${PYTHON_VERSION} не установлен!"
        exit 1
    fi
}

# Клонирование репозитория
clone_repository() {
    log_step "Клонирование репозитория"
    
    if [ -d "$INSTALL_DIR" ]; then
        log_warning "Директория $INSTALL_DIR уже существует"
        read -p "Удалить и установить заново? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$INSTALL_DIR"
        else
            log_info "Обновляем существующую установку..."
            cd "$INSTALL_DIR"
            git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || {
                log_warning "Не удалось обновить, продолжаем с текущей версией"
            }
            return 0
        fi
    fi
    
    log_info "Клонирование из ${REPO_URL}..."
    git clone "$REPO_URL" "$INSTALL_DIR" 2>/dev/null || {
        log_error "Не удалось клонировать репозиторий"
        log_info "Проверьте URL: ${REPO_URL}"
        exit 1
    }
    
    log_success "Репозиторий клонирован в $INSTALL_DIR"
}

# Создание виртуального окружения
create_venv() {
    log_step "Создание виртуального окружения"
    
    cd "$INSTALL_DIR"
    
    # Удаляем старое если есть
    [ -d "venv" ] && rm -rf venv
    
    log_info "Создание venv с Python ${PYTHON_VERSION}..."
    python${PYTHON_VERSION} -m venv venv
    
    log_success "Виртуальное окружение создано"
}

# Установка Python зависимостей
install_python_deps() {
    log_step "Установка Python зависимостей"
    
    cd "$INSTALL_DIR"
    
    # Активируем venv
    source venv/bin/activate
    
    # Обновляем pip
    log_info "Обновление pip..."
    pip install --upgrade pip -q
    
    # Устанавливаем зависимости
    if [ -f "requirements.txt" ]; then
        log_info "Установка зависимостей из requirements.txt..."
        pip install -r requirements.txt -q || {
            log_warning "Некоторые пакеты не установились, пробуем по одному..."
            while IFS= read -r package || [[ -n "$package" ]]; do
                [[ -z "$package" || "$package" =~ ^# ]] && continue
                pip install "$package" -q 2>/dev/null || log_warning "Не удалось: $package"
            done < requirements.txt
        }
    else
        log_warning "requirements.txt не найден!"
    fi
    
    deactivate
    log_success "Зависимости установлены"
}

# Создание скриптов запуска
create_launch_scripts() {
    log_step "Создание скриптов запуска"
    
    cd "$INSTALL_DIR"
    
    # start.sh
    cat > start.sh << 'SCRIPT'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
echo "🦭 Запуск SealPlayerok Bot..."
python bot.py
SCRIPT
    chmod +x start.sh
    
    # stop.sh
    cat > stop.sh << 'SCRIPT'
#!/bin/bash
echo "🛑 Остановка SealPlayerok Bot..."
pkill -f "python.*bot.py" 2>/dev/null && echo "✅ Бот остановлен" || echo "⚠️ Бот не запущен"
SCRIPT
    chmod +x stop.sh
    
    # restart.sh
    cat > restart.sh << 'SCRIPT'
#!/bin/bash
cd "$(dirname "$0")"
./stop.sh
sleep 2
./start.sh
SCRIPT
    chmod +x restart.sh
    
    # update.sh
    cat > update.sh << 'SCRIPT'
#!/bin/bash
cd "$(dirname "$0")"
echo "🔄 Обновление SealPlayerok Bot..."
./stop.sh 2>/dev/null
git pull origin main 2>/dev/null || git pull origin master
source venv/bin/activate
pip install -r requirements.txt -q
deactivate
echo "✅ Обновление завершено"
echo "🦭 Запустите: ./start.sh"
SCRIPT
    chmod +x update.sh
    
    log_success "Скрипты созданы: start.sh, stop.sh, restart.sh, update.sh"
}

# Создание systemd сервиса (автоматически с автозапуском)
create_systemd_service() {
    log_step "Настройка systemd сервиса"
    
    SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
    
    log_info "Создание systemd сервиса..."
    
    sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=SealPlayerok Bot - Playerok Helper
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    sudo systemctl enable "$SERVICE_NAME" 2>/dev/null
    
    log_success "Systemd сервис создан и автозапуск ВКЛЮЧЁН"
}

# Первоначальная настройка бота (интерактивно)
first_run_setup() {
    log_step "Первоначальная настройка"
    
    log_info "Сейчас бот запустится для настройки."
    log_info "Следуй инструкциям в боте."
    log_warning "После настройки нажми Ctrl+C для выхода!"
    echo ""
    read -p "Нажми Enter чтобы начать настройку..." -r
    echo ""
    
    cd "$INSTALL_DIR"
    source venv/bin/activate
    python bot.py || true
    deactivate
    
    echo ""
    log_success "Настройка завершена!"
    log_info "Запускаю бота как сервис..."
    
    sudo systemctl start "$SERVICE_NAME"
    sleep 2
    
    if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
        log_success "Бот успешно запущен в фоне!"
    else
        log_warning "Проверь логи: seal-pln logs"
    fi
}

# Создание алиасов для удобства
create_aliases() {
    log_step "Создание удобных команд"
    
    # Создаём скрипт с командами
    COMMANDS_FILE="$INSTALL_DIR/commands.sh"
    
    cat > "$COMMANDS_FILE" << 'CMDEOF'
#!/bin/bash
# 🦭 SealPlayerok Bot - Команды управления

SERVICE="seal-playerok-bot"
INSTALL_DIR="$HOME/SealPlayerokBot"

# Проверка статуса
is_running() {
    systemctl is-active --quiet $SERVICE
}

case "$1" in
    start)
        if is_running; then
            echo "⚠️  Бот уже запущен!"
            echo "   Используй: seal-pln status"
        else
            echo "🚀 Запуск бота..."
            sudo systemctl start $SERVICE
            sleep 1
            if is_running; then
                echo "✅ Бот запущен"
            else
                echo "❌ Ошибка запуска. Проверь логи: seal-pln logs"
            fi
        fi
        ;;
    stop)
        if ! is_running; then
            echo "⚠️  Бот уже остановлен!"
        else
            echo "🛑 Остановка бота..."
            sudo systemctl stop $SERVICE
            echo "✅ Бот остановлен"
        fi
        ;;
    restart)
        echo "🔄 Перезапуск бота..."
        sudo systemctl restart $SERVICE
        sleep 1
        if is_running; then
            echo "✅ Бот перезапущен"
        else
            echo "❌ Ошибка. Проверь логи: seal-pln logs"
        fi
        ;;
    status)
        if is_running; then
            echo "✅ Бот РАБОТАЕТ"
        else
            echo "❌ Бот ОСТАНОВЛЕН"
        fi
        echo ""
        sudo systemctl status $SERVICE --no-pager
        ;;
    logs)
        echo "📋 Логи бота (Ctrl+C для выхода):"
        journalctl -u $SERVICE -f --no-hostname
        ;;
    enable)
        echo "✅ Включение автозапуска..."
        sudo systemctl enable $SERVICE 2>/dev/null
        echo "✅ Автозапуск включён"
        ;;
    disable)
        echo "❌ Отключение автозапуска..."
        sudo systemctl disable $SERVICE 2>/dev/null
        echo "✅ Автозапуск отключён"
        ;;
    setup)
        # Интерактивная настройка (первый запуск)
        echo "🔧 Интерактивная настройка бота..."
        echo "   Введи токены когда бот попросит."
        echo "   После настройки нажми Ctrl+C и запусти: seal-pln start"
        echo ""
        cd "$INSTALL_DIR"
        source venv/bin/activate
        python bot.py
        ;;
    *)
        echo "🦭 SealPlayerok Bot - Команды:"
        echo ""
        echo "  seal-pln start    - 🚀 Запустить бота"
        echo "  seal-pln stop     - 🛑 Остановить бота"
        echo "  seal-pln restart  - 🔄 Перезапустить бота"
        echo "  seal-pln status   - 📊 Статус бота"
        echo "  seal-pln logs     - 📋 Просмотр логов"
        echo "  seal-pln enable   - ✅ Включить автозапуск"
        echo "  seal-pln disable  - ❌ Отключить автозапуск"
        echo "  seal-pln setup    - 🔧 Первоначальная настройка"
        echo ""
        if is_running; then
            echo "Статус: ✅ Бот работает"
        else
            echo "Статус: ❌ Бот остановлен"
        fi
        ;;
esac
CMDEOF
    
    chmod +x "$COMMANDS_FILE"
    
    # Создаём симлинк в /usr/local/bin для глобального доступа
    sudo ln -sf "$COMMANDS_FILE" /usr/local/bin/seal-pln 2>/dev/null || true
    
    log_success "Команда 'seal-pln' создана для управления ботом"
}

# Финальное сообщение
show_final_message() {
    echo -e "\n"
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                           ║${NC}"
    echo -e "${GREEN}║      🎉 SealPlayerok Bot успешно установлен! 🎉          ║${NC}"
    echo -e "${GREEN}║                                                           ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo -e ""
    echo -e "${CYAN}📂 Директория:${NC} $INSTALL_DIR"
    echo -e "${CYAN}🐍 Python:${NC} $(python${PYTHON_VERSION} --version)"
    echo -e "${CYAN}🔄 Автозапуск:${NC} ВКЛЮЧЁН"
    echo -e ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}🎮 КОМАНДЫ УПРАВЛЕНИЯ (скопируй и сохрани):${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e ""
    echo -e "  ${GREEN}seal-pln start${NC}      - 🚀 Запустить бота"
    echo -e "  ${GREEN}seal-pln stop${NC}       - 🛑 Остановить бота"
    echo -e "  ${GREEN}seal-pln restart${NC}    - 🔄 Перезапустить бота"
    echo -e "  ${GREEN}seal-pln status${NC}     - 📊 Статус бота"
    echo -e "  ${GREEN}seal-pln logs${NC}       - 📋 Просмотр логов (Ctrl+C выход)"
    echo -e ""
    echo -e "  ${CYAN}seal-pln enable${NC}     - ✅ Включить автозапуск"
    echo -e "  ${CYAN}seal-pln disable${NC}    - ❌ Отключить автозапуск"
    echo -e ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e ""
    echo -e "${CYAN}🔧 Первый запуск:${NC}"
    echo -e "   Бот уже запущен! Проверь логи командой: ${GREEN}seal-pln logs${NC}"
    echo -e "   При первом запуске введи токены в консоль бота."
    echo -e ""
    echo -e "${CYAN}📝 Альтернативные команды (systemctl):${NC}"
    echo -e "   sudo systemctl start|stop|restart|status ${SERVICE_NAME}"
    echo -e "   journalctl -u ${SERVICE_NAME} -f"
    echo -e ""
    echo -e "${GREEN}🦭 Приятного использования!${NC}"
    echo -e ""
}

# Основная функция
main() {
    show_banner
    check_not_root
    check_system
    install_dependencies
    install_python
    clone_repository
    create_venv
    install_python_deps
    create_launch_scripts
    create_systemd_service
    create_aliases
    first_run_setup
    show_final_message
}

# Запуск
main "$@"
