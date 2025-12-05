#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# 🦭 SealPlayerok Bot - Установщик для Ubuntu/Linux
# ═══════════════════════════════════════════════════════════════════════════════
# Использование (запускать от root!):
#   wget https://raw.githubusercontent.com/leizov/Seal-Playerok-Bot/main/install.sh && sudo bash install.sh
#   или
#   curl -O https://raw.githubusercontent.com/leizov/Seal-Playerok-Bot/main/install.sh && sudo bash install.sh
# ═══════════════════════════════════════════════════════════════════════════════

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Конфигурация
GH_REPO="leizov/Seal-Playerok-Bot"
PYTHON_VERSION="3.12"
SERVICE_NAME="seal-playerok-bot"
BOT_USERNAME=""
INSTALL_DIR=""

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
    clear
    echo -e "${CYAN}"
    cat << 'EOF'
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║    🦭  SealPlayerok Bot - Installer for Ubuntu/Linux 🦭     ║
    ║                                                           ║
    ║              Милый бот-помощник для Playerok              ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
    echo -e "${CYAN}📢 Канал:${NC}  https://t.me/SealPlayerok"
    echo -e "${CYAN}💬 Чат:${NC}    https://t.me/SealPlayerokChat"
    echo -e "${CYAN}📦 GitHub:${NC} https://github.com/${GH_REPO}"
    echo -e ""
}

# Проверка что запущено от root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "Установщик должен быть запущен от root!"
        log_info "Используй: curl -sSL https://raw.githubusercontent.com/leizov/Seal-Playerok-Bot/main/install.sh | sudo bash"
        exit 1
    fi
}

# Запрос имени пользователя для бота
ask_username() {
    log_step "Создание пользователя для бота"
    
    log_info "Бот будет работать от отдельного пользователя (не root)."
    log_info "Это безопаснее и правильнее для продакшена."
    echo ""
    
    echo -ne "${CYAN}Введи имя пользователя для бота (например: sealbot, seal, playerok): ${NC}"
    while true; do
        read BOT_USERNAME
        
        # Если пустое - используем значение по умолчанию
        if [[ -z "$BOT_USERNAME" ]]; then
            BOT_USERNAME="sealbot"
            log_info "Используем имя по умолчанию: ${BOT_USERNAME}"
            break
        fi
        
        # Проверяем валидность имени
        if [[ "$BOT_USERNAME" =~ ^[a-zA-Z][a-zA-Z0-9_-]+$ ]]; then
            # Проверяем что пользователь не существует
            if id "$BOT_USERNAME" &>/dev/null; then
                echo -ne "\n${RED}Пользователь уже существует! ${CYAN}Введи другое имя: ${NC}"
            else
                break
            fi
        else
            echo -ne "\n${RED}Недопустимые символы! ${CYAN}Имя должно начинаться с буквы и содержать только буквы, цифры, '_' или '-': ${NC}"
        fi
    done
    
    INSTALL_DIR="/home/${BOT_USERNAME}/SealPlayerokBot"
    log_success "Имя пользователя: ${BOT_USERNAME}"
    log_success "Директория установки: ${INSTALL_DIR}"
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
    
    # Получаем версию дистрибутива
    DISTRO_VERSION=$(lsb_release -rs 2>/dev/null || echo "unknown")
    DISTRO_NAME=$(lsb_release -is 2>/dev/null || echo "unknown")
    
    log_success "Система: ${DISTRO_NAME} ${DISTRO_VERSION}"
    log_success "Архитектура: $(uname -m)"
}

# Базовая подготовка системы (для свежего VPS)
prepare_fresh_system() {
    log_step "Подготовка системы"
    
    log_info "Обновление списка пакетов..."
    apt update -qq || {
        log_error "Не удалось обновить список пакетов"
        exit 1
    }
    
    log_info "Установка базовых утилит..."
    apt install -y -qq \
        ca-certificates \
        gnupg \
        lsb-release \
        apt-transport-https \
        2>/dev/null || true
    
    log_success "Базовая подготовка завершена"
}

# Установка системных зависимостей
install_dependencies() {
    log_step "Установка системных зависимостей"
    
    log_info "Установка необходимых пакетов..."
    apt install -y -qq \
        software-properties-common \
        git \
        curl \
        wget \
        unzip \
        build-essential \
        libssl-dev \
        libffi-dev \
        python3-dev \
        python3-pip \
        python3-venv \
        2>/dev/null || {
            log_error "Не удалось установить зависимости"
            exit 1
        }
    
    log_success "Системные зависимости установлены"
}

# Настройка локализации (для пустого VPS)
setup_locale() {
    log_step "Настройка локализации"
    
    DISTRO_VERSION=$(lsb_release -rs 2>/dev/null || echo "20.04")
    
    case $DISTRO_VERSION in
        "11" | "12")
            # Debian
            log_info "Установка локалей для Debian..."
            apt install -y -qq locales locales-all 2>/dev/null || true
            ;;
        *)
            # Ubuntu и другие
            log_info "Установка языковых пакетов..."
            apt install -y -qq language-pack-en language-pack-ru 2>/dev/null || true
            ;;
    esac
    
    # Устанавливаем UTF-8 локаль
    if command -v locale-gen &> /dev/null; then
        locale-gen en_US.UTF-8 2>/dev/null || true
        locale-gen ru_RU.UTF-8 2>/dev/null || true
    fi
    
    # Устанавливаем переменные окружения для текущей сессии
    export LANG=en_US.UTF-8
    export LC_ALL=en_US.UTF-8
    
    log_success "Локализация настроена"
}

# Установка Python 3.12
install_python() {
    log_step "Установка Python ${PYTHON_VERSION}"
    
    # Получаем версию дистрибутива
    DISTRO_VERSION=$(lsb_release -rs 2>/dev/null || echo "20.04")
    
    # Проверяем есть ли уже Python нужной версии
    if command -v python${PYTHON_VERSION} &> /dev/null; then
        CURRENT_VERSION=$(python${PYTHON_VERSION} --version 2>&1 | cut -d' ' -f2)
        log_success "Python ${CURRENT_VERSION} уже установлен"
        return 0
    fi
    
    # Для Ubuntu 24.04+ Python 3.12 уже есть в репозитории
    case $DISTRO_VERSION in
        "24.04" | "24.10")
            log_info "Установка Python ${PYTHON_VERSION} из стандартного репозитория..."
            apt install -y python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python${PYTHON_VERSION}-dev python${PYTHON_VERSION}-gdbm || {
                log_error "Не удалось установить Python ${PYTHON_VERSION}"
                exit 1
            }
            ;;
        "11")
            # Debian 11 - используем deadsnakes через Ubuntu focal
            log_info "Настройка репозитория для Debian 11..."
            apt install -y gnupg 2>/dev/null || true
            apt-key adv --keyserver keyserver.ubuntu.com --recv-keys BA6932366A755776 2>/dev/null || true
            add-apt-repository -s "deb https://ppa.launchpadcontent.net/deadsnakes/ppa/ubuntu focal main" 2>/dev/null || true
            apt update -qq
            apt install -y python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python${PYTHON_VERSION}-dev python${PYTHON_VERSION}-gdbm || {
                log_error "Не удалось установить Python ${PYTHON_VERSION}"
                exit 1
            }
            ;;
        *)
            # Ubuntu и остальные - используем PPA deadsnakes
            log_info "Добавление репозитория deadsnakes..."
            add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || {
                log_warning "Не удалось добавить PPA, пробуем установить стандартный Python..."
            }
            apt update -qq
            
            log_info "Установка Python ${PYTHON_VERSION}..."
            apt install -y python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python${PYTHON_VERSION}-dev python${PYTHON_VERSION}-gdbm 2>/dev/null || {
                log_error "Не удалось установить Python ${PYTHON_VERSION}"
                log_info "Попробуй установить вручную: apt install python3.12"
                exit 1
            }
            ;;
    esac
    
    # Проверяем установку
    if command -v python${PYTHON_VERSION} &> /dev/null; then
        log_success "Python $(python${PYTHON_VERSION} --version) установлен"
    else
        log_error "Python ${PYTHON_VERSION} не установлен!"
        exit 1
    fi
}

# Создание пользователя для бота
create_bot_user() {
    log_step "Создание системного пользователя"
    
    log_info "Создание пользователя ${BOT_USERNAME}..."
    useradd -m -s /bin/bash "$BOT_USERNAME" || {
        log_error "Не удалось создать пользователя ${BOT_USERNAME}"
        exit 1
    }
    
    log_success "Пользователь ${BOT_USERNAME} создан"
    log_success "Домашняя директория: /home/${BOT_USERNAME}"
}

# Скачивание бота с GitHub
download_bot() {
    log_step "Загрузка SealPlayerok Bot"
    
    # Создаём временную директорию для загрузки
    TEMP_DIR="/home/${BOT_USERNAME}/seal-install"
    mkdir -p "$TEMP_DIR"
    
    # Получаем URL последнего релиза
    log_info "Получение последней версии с GitHub..."
    RELEASE_URL=$(curl -sS "https://api.github.com/repos/${GH_REPO}/releases/latest" 2>/dev/null | grep "zipball_url" | awk '{ print $2 }' | sed 's/,$//' | sed 's/"//g')
    
    if [[ -z "$RELEASE_URL" ]]; then
        # Если релизов нет, клонируем через git
        log_warning "Релизы не найдены, клонируем репозиторий..."
        sudo -u "$BOT_USERNAME" git clone "https://github.com/${GH_REPO}.git" "$INSTALL_DIR" 2>/dev/null || {
            log_error "Не удалось загрузить бота"
            exit 1
        }
    else
        # Скачиваем архив релиза
        log_info "Скачивание архива..."
        curl -L "$RELEASE_URL" -o "${TEMP_DIR}/bot.zip" || {
            log_error "Не удалось скачать архив"
            exit 1
        }
        
        log_info "Распаковка..."
        unzip -q "${TEMP_DIR}/bot.zip" -d "$TEMP_DIR" || {
            log_error "Не удалось распаковать архив"
            exit 1
        }
        
        # Создаём директорию и перемещаем файлы
        mkdir -p "$INSTALL_DIR"
        mv ${TEMP_DIR}/*/* "$INSTALL_DIR/" 2>/dev/null || mv ${TEMP_DIR}/*/.* "$INSTALL_DIR/" 2>/dev/null || true
        
        # Удаляем временные файлы
        rm -rf "$TEMP_DIR"
    fi
    
    # Устанавливаем правильного владельца
    chown -R "${BOT_USERNAME}:${BOT_USERNAME}" "$INSTALL_DIR"
    
    log_success "Бот загружен в ${INSTALL_DIR}"
}

# Создание виртуального окружения
create_venv() {
    log_step "Создание виртуального окружения"
    
    VENV_DIR="/home/${BOT_USERNAME}/venv"
    
    log_info "Создание venv с Python ${PYTHON_VERSION}..."
    sudo -u "$BOT_USERNAME" python${PYTHON_VERSION} -m venv "$VENV_DIR" || {
        log_error "Не удалось создать виртуальное окружение"
        exit 1
    }
    
    # Устанавливаем pip (важно запускать от root для некоторых версий ОС)
    log_info "Настройка pip..."
    "${VENV_DIR}/bin/python" -m ensurepip --upgrade 2>/dev/null || true
    
    # Обновляем pip от имени пользователя
    sudo -u "$BOT_USERNAME" "${VENV_DIR}/bin/python" -m pip install --upgrade pip -q || true
    
    # Устанавливаем правильного владельца
    chown -R "${BOT_USERNAME}:${BOT_USERNAME}" "$VENV_DIR"
    
    log_success "Виртуальное окружение создано: ${VENV_DIR}"
}

# Установка Python зависимостей
install_python_deps() {
    log_step "Установка Python зависимостей"
    
    VENV_DIR="/home/${BOT_USERNAME}/venv"
    
    if [ -f "${INSTALL_DIR}/requirements.txt" ]; then
        log_info "Установка зависимостей из requirements.txt..."
        sudo -u "$BOT_USERNAME" "${VENV_DIR}/bin/pip" install -U -r "${INSTALL_DIR}/requirements.txt" || {
            log_warning "Некоторые пакеты не установились, пробуем по одному..."
            while IFS= read -r package || [[ -n "$package" ]]; do
                [[ -z "$package" || "$package" =~ ^# ]] && continue
                sudo -u "$BOT_USERNAME" "${VENV_DIR}/bin/pip" install -U "$package" 2>/dev/null || log_warning "Не удалось: $package"
            done < "${INSTALL_DIR}/requirements.txt"
        }
    else
        log_warning "requirements.txt не найден!"
    fi
    
    log_success "Зависимости установлены"
}

# Создание скриптов запуска
create_launch_scripts() {
    log_step "Создание скриптов запуска"
    
    VENV_DIR="/home/${BOT_USERNAME}/venv"
    
    # start.sh
    cat > "${INSTALL_DIR}/start.sh" << SCRIPT
#!/bin/bash
cd "${INSTALL_DIR}"
source "${VENV_DIR}/bin/activate"
echo "🦭 Запуск SealPlayerok Bot..."
LANG=en_US.UTF-8 python bot.py
SCRIPT
    chmod +x "${INSTALL_DIR}/start.sh"
    
    # stop.sh
    cat > "${INSTALL_DIR}/stop.sh" << 'SCRIPT'
#!/bin/bash
echo "🛑 Остановка SealPlayerok Bot..."
pkill -f "python.*bot.py" 2>/dev/null && echo "✅ Бот остановлен" || echo "⚠️ Бот не запущен"
SCRIPT
    chmod +x "${INSTALL_DIR}/stop.sh"
    
    # restart.sh
    cat > "${INSTALL_DIR}/restart.sh" << SCRIPT
#!/bin/bash
cd "${INSTALL_DIR}"
./stop.sh
sleep 2
./start.sh
SCRIPT
    chmod +x "${INSTALL_DIR}/restart.sh"
    
    # update.sh
    cat > "${INSTALL_DIR}/update.sh" << SCRIPT
#!/bin/bash
cd "${INSTALL_DIR}"
echo "🔄 Обновление SealPlayerok Bot..."
./stop.sh 2>/dev/null
git pull origin main 2>/dev/null || git pull origin master
source "${VENV_DIR}/bin/activate"
pip install -r requirements.txt -q
deactivate
echo "✅ Обновление завершено"
echo "🦭 Запусти: seal-pln start"
SCRIPT
    chmod +x "${INSTALL_DIR}/update.sh"
    
    # Устанавливаем владельца
    chown -R "${BOT_USERNAME}:${BOT_USERNAME}" "${INSTALL_DIR}"
    
    log_success "Скрипты созданы: start.sh, stop.sh, restart.sh, update.sh"
}

# Создание systemd сервиса
create_systemd_service() {
    log_step "Настройка systemd сервиса"
    
    VENV_DIR="/home/${BOT_USERNAME}/venv"
    SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
    
    log_info "Создание systemd сервиса..."
    
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=SealPlayerok Bot - Playerok Helper
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${BOT_USERNAME}
Group=${BOT_USERNAME}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${VENV_DIR}/bin/python ${INSTALL_DIR}/bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1
Environment=LANG=en_US.UTF-8
Environment=LC_ALL=en_US.UTF-8

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    
    log_success "Systemd сервис создан"
    log_info "Автозапуск будет включён после первичной настройки"
}

# Первоначальная настройка бота (интерактивно)
first_run_setup() {
    log_step "Первоначальная настройка"
    
    VENV_DIR="/home/${BOT_USERNAME}/venv"
    
    log_info "Сейчас бот запустится для первичной настройки."
    log_info "Следуй инструкциям в боте (введи токены и т.д.)"
    log_warning "После настройки нажми Ctrl+C для выхода!"
    echo ""
    
    echo -ne "${CYAN}Нажми Enter чтобы начать настройку...${NC}"
    read -r
    
    echo ""
    log_info "Запуск бота от имени пользователя ${BOT_USERNAME}..."
    echo ""
    
    # Запускаем бота для интерактивной настройки
    sudo -u "$BOT_USERNAME" LANG=en_US.UTF-8 "${VENV_DIR}/bin/python" "${INSTALL_DIR}/bot.py" || true
    
    echo ""
    log_success "Первичная настройка завершена!"
}

# Запуск бота как сервиса
start_bot_service() {
    log_step "Запуск бота"
    
    log_info "Запускаю бота как фоновый сервис..."
    systemctl start "$SERVICE_NAME"
    sleep 3
    
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log_success "Бот успешно запущен!"
        
        # Включаем автозапуск
        systemctl enable "$SERVICE_NAME" 2>/dev/null
        log_success "Автозапуск включён"
    else
        log_warning "Бот не запустился. Проверь логи: seal-pln logs"
        log_info "Возможно нужно повторить настройку: seal-pln setup"
    fi
}

# Создание алиасов для удобства
create_aliases() {
    log_step "Создание удобных команд"
    
    VENV_DIR="/home/${BOT_USERNAME}/venv"
    
    # Создаём скрипт с командами
    COMMANDS_FILE="${INSTALL_DIR}/commands.sh"
    
    cat > "$COMMANDS_FILE" << EOF
#!/bin/bash
# 🦭 SealPlayerok Bot - Команды управления

SERVICE="${SERVICE_NAME}"
INSTALL_DIR="${INSTALL_DIR}"
VENV_DIR="${VENV_DIR}"
BOT_USER="${BOT_USERNAME}"

# Проверка статуса
is_running() {
    systemctl is-active --quiet \$SERVICE
}

case "\$1" in
    start)
        if is_running; then
            echo "⚠️  Бот уже запущен!"
            echo "   Используй: seal-pln status"
        else
            echo "🚀 Запуск бота..."
            sudo systemctl start \$SERVICE
            sleep 2
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
            sudo systemctl stop \$SERVICE
            echo "✅ Бот остановлен"
        fi
        ;;
    restart)
        echo "🔄 Перезапуск бота..."
        sudo systemctl restart \$SERVICE
        sleep 2
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
        sudo systemctl status \$SERVICE --no-pager -l
        ;;
    logs)
        echo "📋 Логи бота (Ctrl+C для выхода):"
        sudo journalctl -u \$SERVICE -f --no-hostname
        ;;
    logs100)
        echo "📋 Последние 100 строк логов:"
        sudo journalctl -u \$SERVICE -n 100 --no-hostname
        ;;
    enable)
        echo "✅ Включение автозапуска..."
        sudo systemctl enable \$SERVICE 2>/dev/null
        echo "✅ Автозапуск включён"
        ;;
    disable)
        echo "❌ Отключение автозапуска..."
        sudo systemctl disable \$SERVICE 2>/dev/null
        echo "✅ Автозапуск отключён"
        ;;
    setup)
        # Интерактивная настройка (первый запуск)
        echo "🔧 Интерактивная настройка бота..."
        echo "   Введи токены когда бот попросит."
        echo "   После настройки нажми Ctrl+C и запусти: seal-pln start"
        echo ""
        # Останавливаем сервис если запущен
        sudo systemctl stop \$SERVICE 2>/dev/null || true
        # Запускаем от имени пользователя бота
        sudo -u \$BOT_USER LANG=en_US.UTF-8 \${VENV_DIR}/bin/python \${INSTALL_DIR}/bot.py
        ;;
    update)
        echo "🔄 Обновление бота..."
        sudo systemctl stop \$SERVICE 2>/dev/null || true
        cd \$INSTALL_DIR
        sudo -u \$BOT_USER git pull origin main 2>/dev/null || sudo -u \$BOT_USER git pull origin master
        sudo -u \$BOT_USER \${VENV_DIR}/bin/pip install -U -r \${INSTALL_DIR}/requirements.txt -q
        echo "✅ Обновление завершено"
        echo "   Запусти: seal-pln start"
        ;;
    *)
        echo "🦭 SealPlayerok Bot - Команды:"
        echo ""
        echo "  seal-pln start     - 🚀 Запустить бота"
        echo "  seal-pln stop      - 🛑 Остановить бота"
        echo "  seal-pln restart   - 🔄 Перезапустить бота"
        echo "  seal-pln status    - 📊 Статус бота"
        echo "  seal-pln logs      - 📋 Логи в реальном времени"
        echo "  seal-pln logs100   - 📋 Последние 100 строк логов"
        echo "  seal-pln enable    - ✅ Включить автозапуск"
        echo "  seal-pln disable   - ❌ Отключить автозапуск"
        echo "  seal-pln setup     - 🔧 Первоначальная настройка"
        echo "  seal-pln update    - 🔄 Обновить бота"
        echo ""
        echo "Пользователь бота: \$BOT_USER"
        echo "Директория: \$INSTALL_DIR"
        echo ""
        if is_running; then
            echo "Статус: ✅ Бот работает"
        else
            echo "Статус: ❌ Бот остановлен"
        fi
        ;;
esac
EOF
    
    chmod +x "$COMMANDS_FILE"
    chown "${BOT_USERNAME}:${BOT_USERNAME}" "$COMMANDS_FILE"
    
    # Создаём симлинк в /usr/local/bin для глобального доступа
    ln -sf "$COMMANDS_FILE" /usr/local/bin/seal-pln 2>/dev/null || true
    
    log_success "Команда 'seal-pln' создана для управления ботом"
}

# Финальное сообщение
show_final_message() {
    clear
    echo -e "\n"
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                           ║${NC}"
    echo -e "${GREEN}║      🎉 SealPlayerok Bot успешно установлен! 🎉          ║${NC}"
    echo -e "${GREEN}║                                                           ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo -e ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}📋 ИНФОРМАЦИЯ ОБ УСТАНОВКЕ:${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e ""
    echo -e "  ${CYAN}👤 Пользователь:${NC}  ${BOT_USERNAME}"
    echo -e "  ${CYAN} Директория:${NC}    ${INSTALL_DIR}"
    echo -e "  ${CYAN}🐍 Python:${NC}        $(python${PYTHON_VERSION} --version 2>&1)"
    echo -e "  ${CYAN}⚙️  Сервис:${NC}        ${SERVICE_NAME}"
    echo -e ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}🎮 КОМАНДЫ УПРАВЛЕНИЯ (скопируй и сохрани!):${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e ""
    echo -e "  ${GREEN}seal-pln start${NC}      - 🚀 Запустить бота"
    echo -e "  ${GREEN}seal-pln stop${NC}       - 🛑 Остановить бота"
    echo -e "  ${GREEN}seal-pln restart${NC}    - 🔄 Перезапустить бота"
    echo -e "  ${GREEN}seal-pln status${NC}     - 📊 Статус бота"
    echo -e "  ${GREEN}seal-pln logs${NC}       - 📋 Логи в реальном времени"
    echo -e "  ${GREEN}seal-pln logs100${NC}    - 📋 Последние 100 строк логов"
    echo -e ""
    echo -e "  ${CYAN}seal-pln setup${NC}      - 🔧 Повторная настройка"
    echo -e "  ${CYAN}seal-pln update${NC}     - 🔄 Обновить бота"
    echo -e "  ${CYAN}seal-pln enable${NC}     - ✅ Включить автозапуск"
    echo -e "  ${CYAN}seal-pln disable${NC}    - ❌ Отключить автозапуск"
    echo -e ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}📝 АЛЬТЕРНАТИВНЫЕ КОМАНДЫ (systemctl):${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e ""
    echo -e "  sudo systemctl start|stop|restart|status ${SERVICE_NAME}"
    echo -e "  sudo journalctl -u ${SERVICE_NAME} -f"
    echo -e ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}🦭 ССЫЛКИ:${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e ""
    echo -e "  ${CYAN}📢 Канал:${NC}   https://t.me/SealPlayerok"
    echo -e "  ${CYAN}💬 Чат:${NC}     https://t.me/SealPlayerokChat"
    echo -e "  ${CYAN}🤖 Бот:${NC}     https://t.me/SealPlayerokBot"
    echo -e "  ${CYAN}📦 GitHub:${NC}  https://github.com/${GH_REPO}"
    echo -e "  ${CYAN}👨‍💻 Автор:${NC}   @leizov"
    echo -e ""
    echo -e "${GREEN}🦭 Приятного использования!${NC}"
    echo -e ""
    
    # Показываем статус бота
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo -e "${GREEN}✅ Бот успешно работает в фоне!${NC}"
        echo -e "   Проверь логи: ${GREEN}seal-pln logs${NC}"
    else
        echo -e "${YELLOW}⚠️  Бот не запущен. Запусти: ${GREEN}seal-pln start${NC}"
    fi
    echo -e ""
}

# Основная функция
main() {
    # Показываем баннер
    show_banner
    
    # Проверяем что запущено от root
    check_root
    
    # Запрашиваем имя пользователя для бота
    ask_username
    
    # Проверяем систему
    check_system
    
    # Подготовка свежего VPS
    prepare_fresh_system
    
    # Установка зависимостей
    install_dependencies
    
    # Настройка локализации
    setup_locale
    
    # Установка Python
    install_python
    
    # Создание пользователя
    create_bot_user
    
    # Скачивание бота
    download_bot
    
    # Создание venv
    create_venv
    
    # Установка Python зависимостей
    install_python_deps
    
    # Создание скриптов
    create_launch_scripts
    
    # Создание systemd сервиса
    create_systemd_service
    
    # Создание команды seal-pln
    create_aliases
    
    # Первичная настройка
    first_run_setup
    
    # Запуск бота как сервиса
    start_bot_service
    
    # Финальное сообщение
    show_final_message
}

# Запуск
main "$@"
