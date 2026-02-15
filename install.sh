#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# 🦭 SealPlayerok Bot - Установщик для Ubuntu/Linux
# ═══════════════════════════════════════════════════════════════════════════════
# Использование (запускать от root!):
#   wget https://raw.githubusercontent.com/leizov/Seal-Playerok-Bot/main/install.sh && sudo bash install.sh
#   или
#   curl -O https://raw.githubusercontent.com/leizov/Seal-Playerok-Bot/main/install.sh && sudo bash install.sh
# ═══════════════════════════════════════════════════════════════════════════════

# НЕ используем set -e - оно мешает интерактивному вводу
# set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Надёжный apt update с ретраями
apt_update_retry() {
    local tries=3
    local delay=3
    local i
    for i in $(seq 1 "$tries"); do
        log_info "apt update (попытка ${i}/${tries})..."
        if apt update -y; then
            return 0
        fi
        log_warning "apt update неуспешен, ждём ${delay} сек и пробуем снова..."
        sleep "$delay"
    done
    return 1
}

# Установка Python через pyenv (фолбэк, если пакеты недоступны), системно в /opt/pyenv
install_python_pyenv() {
    local PYENV_VERSION="${1:-3.12.7}"  # точная версия для сборки
    log_warning "Устанавливаем Python ${PYENV_VERSION} через pyenv (системная установка)..."

    # 1. Зависимости для сборки
    apt update && apt install -y make build-essential libssl-dev zlib1g-dev \
        libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
        libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev \
        libffi-dev liblzma-dev || {
        log_error "Не удалось установить зависимости для pyenv"
        return 1
    }

    # 2. Системная установка pyenv в /opt/pyenv
    export PYENV_ROOT="/opt/pyenv"
    if [ ! -d "$PYENV_ROOT" ]; then
        curl https://pyenv.run | PYENV_ROOT="$PYENV_ROOT" bash || {
            log_error "Не удалось установить pyenv"
            return 1
        }
        chmod -R 755 "$PYENV_ROOT"
    fi

    # 3. Добавляем в системный профиль
    cat > /etc/profile.d/pyenv.sh << 'EOF'
export PYENV_ROOT="/opt/pyenv"
export PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
EOF
    chmod +x /etc/profile.d/pyenv.sh

    # 4. Активируем в текущей сессии
    export PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"
    eval "$($PYENV_ROOT/bin/pyenv init --path)"
    eval "$($PYENV_ROOT/bin/pyenv init -)"
    hash -r

    # 5. Устанавливаем Python
    if ! "$PYENV_ROOT/bin/pyenv" versions | grep -q "$PYENV_VERSION"; then
        "$PYENV_ROOT/bin/pyenv" install "$PYENV_VERSION" || {
            log_error "pyenv не смог установить Python $PYENV_VERSION"
            return 1
        }
    fi

    "$PYENV_ROOT/bin/pyenv" global "$PYENV_VERSION"
    "$PYENV_ROOT/bin/pyenv" rehash || true

    # 6. Ссылки для удобства
    ln -sf "$PYENV_ROOT/shims/python" /usr/local/bin/python3.12 2>/dev/null || true
    ln -sf "$PYENV_ROOT/shims/pip"    /usr/local/bin/pip3.12 2>/dev/null || true
    ln -sf "$PYENV_ROOT/shims/python" /usr/local/bin/python 2>/dev/null || true
    ln -sf "$PYENV_ROOT/shims/pip"    /usr/local/bin/pip 2>/dev/null || true

    log_success "Python $PYENV_VERSION установлен через pyenv (системно)"
    log_warning "Перезайдите в оболочку или выполните: source /etc/profile.d/pyenv.sh"
    return 0
}

# Конфигурация
GH_REPO="leizov/Seal-Playerok-Bot"
PYTHON_VERSION="3.12"
SERVICE_NAME=""
BOT_USERNAME=""
INSTALL_DIR=""
COMMAND_NAME=""
SKIP_USER_CREATE=false

# URL для переустановки
INSTALL_COMMAND="bash <(curl -sL https://raw.githubusercontent.com/leizov/Seal-Playerok-Bot/main/install.sh)"

# Обработка прерывания установки (Ctrl+C, разрыв сессии и т.д.)
cleanup_on_interrupt() {
    echo ""
    echo -e "\n${YELLOW}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}⚠️  Установка прервана!${NC}"
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${CYAN}📌 Для повторной установки выполни:${NC}"
    echo -e "   ${GREEN}${INSTALL_COMMAND}${NC}"
    echo ""
    if [ -n "$COMMAND_NAME" ]; then
        echo -e "${CYAN}📌 Если бот уже установлен, используй:${NC}"
        echo -e "   ${GREEN}${COMMAND_NAME} setup${NC}  — повторная настройка"
        echo -e "   ${GREEN}${COMMAND_NAME} start${NC}  — запуск бота"
        echo ""
    fi
    exit 1
}

# Устанавливаем trap для сигналов прерывания
trap cleanup_on_interrupt SIGINT SIGTERM SIGHUP

# Проверка на команды выхода
check_exit_command() {
    local input="$1"
    local lower_input=$(echo "$input" | tr '[:upper:]' '[:lower:]')
    
    case "$lower_input" in
        stop|стоп|exit|quit|выход|отмена|cancel|q)
            echo ""
            echo -e "${YELLOW}🛑 Установка отменена по запросу пользователя${NC}"
            echo ""
            echo -e "${CYAN}📌 Для повторной установки выполни:${NC}"
            echo -e "   ${GREEN}${INSTALL_COMMAND}${NC}"
            echo ""
            exit 0
            ;;
    esac
}

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
        log_info "Используй: sudo bash install.sh"
        exit 1
    fi
}

# Запрос имени пользователя для бота
ask_username() {
    log_step "Шаг 1/7: Имя пользователя"
    
    echo -e "${YELLOW}┌─────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${YELLOW}│  📝 СОЗДАНИЕ ПОЛЬЗОВАТЕЛЯ                                   │${NC}"
    echo -e "${YELLOW}├─────────────────────────────────────────────────────────────┤${NC}"
    echo -e "${YELLOW}│  Бот будет работать от отдельного пользователя Linux.       │${NC}"
    echo -e "${YELLOW}│  Это нужно для безопасности и изоляции.                     │${NC}"
    echo -e "${YELLOW}│                                                             │${NC}"
    echo -e "${YELLOW}│  💡 Просто нажми ENTER чтобы использовать 'sealbot'         │${NC}"
    echo -e "${YELLOW}│  💡 Или введи своё имя (латиницей, например: mybot)         │${NC}"
    echo -e "${YELLOW}└─────────────────────────────────────────────────────────────┘${NC}"
    echo ""
    
    echo -e "${BLUE}💡 Введи 'stop' или 'стоп' для отмены установки${NC}"
    echo ""
    echo -ne "${CYAN}👤 Имя пользователя [sealbot]: ${NC}"
    while true; do
        # Читаем из /dev/tty чтобы работало даже когда stdin занят (curl | bash)
        read -r BOT_USERNAME < /dev/tty || BOT_USERNAME=""
        
        # Проверяем на команду выхода
        check_exit_command "$BOT_USERNAME"
        
        # Если пустое - используем значение по умолчанию
        if [[ -z "$BOT_USERNAME" ]]; then
            BOT_USERNAME="sealbot"
            log_info "Используем имя по умолчанию: ${BOT_USERNAME}"
        fi
        
        # Проверяем валидность имени
        if [[ ! "$BOT_USERNAME" =~ ^[a-zA-Z][a-zA-Z0-9_-]*$ ]]; then
            echo -ne "\n${RED}Недопустимые символы! ${CYAN}Имя должно начинаться с буквы (или 'stop' для отмены): ${NC}"
            continue
        fi
        
        # Проверяем существует ли пользователь
        if id "$BOT_USERNAME" &>/dev/null; then
            INSTALL_DIR="/home/${BOT_USERNAME}/SealPlayerokBot"
            
            echo ""
            log_warning "Пользователь '${BOT_USERNAME}' уже существует!"
            
            if [ -d "$INSTALL_DIR" ]; then
                log_info "Директория бота уже есть: ${INSTALL_DIR}"
                echo ""
                echo -ne "${YELLOW}Что делать? [1] Переустановить / [2] Другое имя / [3] Выход: ${NC}"
                read -r choice < /dev/tty || choice="3"
                
                case "$choice" in
                    1)
                        log_info "Переустановка в существующую директорию..."
                        SKIP_USER_CREATE=true
                        break
                        ;;
                    2)
                        echo -ne "${CYAN}Введи другое имя: ${NC}"
                        continue
                        ;;
                    *)
                        log_info "Отмена установки"
                        exit 0
                        ;;
                esac
            else
                log_info "Используем существующего пользователя '${BOT_USERNAME}'"
                SKIP_USER_CREATE=true
                break
            fi
        else
            SKIP_USER_CREATE=false
            break
        fi
    done
    
    INSTALL_DIR="/home/${BOT_USERNAME}/SealPlayerokBot"
    # Уникальные имена для каждого бота (поддержка нескольких ботов)
    COMMAND_NAME="seal-${BOT_USERNAME}"
    SERVICE_NAME="seal-${BOT_USERNAME}"
    
    log_success "Имя пользователя: ${BOT_USERNAME}"
    log_success "Директория установки: ${INSTALL_DIR}"
    log_success "Команда управления: ${COMMAND_NAME}"
    log_success "Имя сервиса: ${SERVICE_NAME}"
}

# Проверка системы
check_system() {
    log_step "Шаг 2/7: Проверка системы"
    
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

# Установка Python 3.12 (ТОЛЬКО эта версия поддерживается)
install_python() {
    log_step "Шаг 3/7: Установка Python ${PYTHON_VERSION}"
    
    # Получаем версию дистрибутива
    DISTRO_VERSION=$(lsb_release -rs 2>/dev/null || echo "20.04")
    
    # Проверяем есть ли уже Python НУЖНОЙ версии 3.12
    if command -v python${PYTHON_VERSION} &> /dev/null; then
        CURRENT_VERSION=$(python${PYTHON_VERSION} --version 2>&1 | cut -d' ' -f2)
        # Проверяем что это именно 3.12, а не другая версия
        if [[ "$CURRENT_VERSION" == 3.12* ]]; then
            log_success "Python ${CURRENT_VERSION} уже установлен"
            return 0
        else
            log_warning "Найден Python ${CURRENT_VERSION}, но требуется ТОЛЬКО Python 3.12"
            log_info "Будет установлен Python 3.12..."
        fi
    fi
    
    # Установка Python в зависимости от версии дистрибутива
    case $DISTRO_VERSION in
        "24.04" | "24.10")
            # Ubuntu 24.04+ - Python 3.12 уже есть
            log_info "Установка Python ${PYTHON_VERSION} из стандартного репозитория..."
            apt install -y python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python${PYTHON_VERSION}-dev python${PYTHON_VERSION}-gdbm || {
                log_error "Не удалось установить Python ${PYTHON_VERSION}"
                exit 1
            }
            ;;
        "22.04")
            # Ubuntu 22.04 - нужен PPA
            log_info "Добавление репозитория deadsnakes для Ubuntu 22.04..."
            apt install -y software-properties-common 2>/dev/null || true
            add-apt-repository -y ppa:deadsnakes/ppa
            apt update
            apt install -y python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python${PYTHON_VERSION}-dev python${PYTHON_VERSION}-gdbm || {
                log_error "Не удалось установить Python ${PYTHON_VERSION}"
                exit 1
            }
            ;;
        "20.04")
            # Ubuntu 20.04 - нужен PPA с предварительным update
            log_info "Добавление репозитория deadsnakes для Ubuntu 20.04..."
            apt install -y software-properties-common 2>/dev/null || true
            add-apt-repository -y ppa:deadsnakes/ppa
            apt update
            log_info "Установка Python ${PYTHON_VERSION}..."
            log_info "Проверяем доступность пакетов (apt-cache policy python${PYTHON_VERSION})..."
            apt-cache policy python${PYTHON_VERSION} || true
            apt install -y python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python${PYTHON_VERSION}-dev python${PYTHON_VERSION}-distutils || {
                log_warning "Не удалось установить Python ${PYTHON_VERSION} пакетами. Пробуем pyenv..."
                if install_python_pyenv; then
                    return 0
                fi
                log_error "Не удалось установить Python ${PYTHON_VERSION}"
                log_info "Диагностика (apt-cache policy python${PYTHON_VERSION}):"
                apt-cache policy python${PYTHON_VERSION} || true
                exit 1
            }
            ;;
        "11" | "12")
            # Debian 11/12 - используем deadsnakes через Ubuntu
            log_info "Настройка репозитория для Debian..."
            apt install -y gnupg curl 2>/dev/null || true
            
            # Добавляем ключ
            curl -fsSL "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0xBA6932366A755776" | gpg --dearmor -o /etc/apt/trusted.gpg.d/deadsnakes.gpg 2>/dev/null || true
            
            # Добавляем репозиторий (focal для совместимости)
            echo "deb https://ppa.launchpadcontent.net/deadsnakes/ppa/ubuntu focal main" > /etc/apt/sources.list.d/deadsnakes.list
            apt update
            
            apt install -y python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python${PYTHON_VERSION}-dev || {
                log_error "Не удалось установить Python ${PYTHON_VERSION}"
                exit 1
            }
            ;;
        *)
            # Другие версии - пробуем PPA
            log_info "Добавление репозитория deadsnakes..."
            apt install -y software-properties-common 2>/dev/null || true
            add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || {
                log_warning "Не удалось добавить PPA"
            }
            apt update
            
            log_info "Установка Python ${PYTHON_VERSION}..."
            apt install -y python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python${PYTHON_VERSION}-dev 2>/dev/null || {
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
    
    if [ "$SKIP_USER_CREATE" = true ]; then
        log_info "Используем существующего пользователя ${BOT_USERNAME}"
        log_success "Домашняя директория: /home/${BOT_USERNAME}"
        return 0
    fi
    
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
    log_step "Шаг 4/7: Загрузка SealPlayerok Bot"
    
    # Создаём временную директорию для загрузки
    TEMP_DIR="/home/${BOT_USERNAME}/seal-install"
    sudo -u "$BOT_USERNAME" mkdir -p "$TEMP_DIR"
    
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
        sudo -u "$BOT_USERNAME" mkdir -p "$INSTALL_DIR"
        mv ${TEMP_DIR}/*/* "$INSTALL_DIR/" 2>/dev/null || mv ${TEMP_DIR}/*/.* "$INSTALL_DIR/" 2>/dev/null || true
        
        # Удаляем временные файлы
        rm -rf "$TEMP_DIR"
    fi
    
    # Устанавливаем правильного владельца и права доступа
    chown -R "${BOT_USERNAME}:${BOT_USERNAME}" "$INSTALL_DIR"
    # Даем права на запись для владельца всех файлов
    chmod -R u+w "$INSTALL_DIR"
    # Для скриптов добавляем право на выполнение
    find "$INSTALL_DIR" -name "*.sh" -exec chmod +x {} \;
    find "$INSTALL_DIR" -name "*.py" -exec chmod u+w {} \;
    
    log_success "Бот загружен в ${INSTALL_DIR}"
}

# Создание виртуального окружения
create_venv() {
    log_step "Шаг 5/7: Создание виртуального окружения"
    
    VENV_DIR="/home/${BOT_USERNAME}/venv"
    USER_HOME="/home/${BOT_USERNAME}"
    
    # Определяем путь к Python 3.12
    # pyenv устанавливает полные версии (3.12.7), поэтому ищем по шаблону
    PYENV_PYTHON=""
    if [ -d "/opt/pyenv/versions" ]; then
        # Ищем версию, начинающуюся с 3.12
        for version_dir in /opt/pyenv/versions/3.12*; do
            if [ -x "${version_dir}/bin/python3" ]; then
                PYENV_PYTHON="${version_dir}/bin/python3"
                break
            fi
        done
    fi
    
    if [ -n "$PYENV_PYTHON" ] && [ -x "$PYENV_PYTHON" ]; then
        # Python установлен через pyenv - используем прямой путь (не shim!)
        PYTHON_BIN="$PYENV_PYTHON"
        log_info "Используем pyenv Python: ${PYTHON_BIN}"
    elif command -v "python${PYTHON_VERSION}" &>/dev/null; then
        PYTHON_BIN="python${PYTHON_VERSION}"
    elif command -v python3.12 &>/dev/null; then
        PYTHON_BIN="python3.12"
    else
        log_error "Python ${PYTHON_VERSION} не найден"
        exit 1
    fi
    
    log_info "Создание venv с Python ${PYTHON_VERSION}..."
    # Используем прямой путь к python бинарнику, чтобы избежать проблем с pyenv shims и HOME
    sudo -u "$BOT_USERNAME" env "HOME=${USER_HOME}" "${PYTHON_BIN}" -m venv "$VENV_DIR" || {
        log_error "Не удалось создать виртуальное окружение"
        exit 1
    }
    
    # Устанавливаем pip (важно запускать от root для некоторых версий ОС)
    log_info "Настройка pip..."
    "${VENV_DIR}/bin/python" -m ensurepip --upgrade 2>/dev/null || true
    
    # Обновляем pip от имени пользователя
    sudo -u "$BOT_USERNAME" env "HOME=/home/${BOT_USERNAME}" "${VENV_DIR}/bin/python" -m pip install --upgrade pip -q || true
    
    # Устанавливаем правильного владельца
    chown -R "${BOT_USERNAME}:${BOT_USERNAME}" "$VENV_DIR"
    
    log_success "Виртуальное окружение создано: ${VENV_DIR}"
}

# Установка Python зависимостей
install_python_deps() {
    log_step "Шаг 6/7: Установка зависимостей"
    
    VENV_DIR="/home/${BOT_USERNAME}/venv"
    
    if [ -f "${INSTALL_DIR}/requirements.txt" ]; then
        log_info "Установка зависимостей из requirements.txt..."
        sudo -u "$BOT_USERNAME" env "HOME=/home/${BOT_USERNAME}" "${VENV_DIR}/bin/pip" install -U -r "${INSTALL_DIR}/requirements.txt" || {
            log_warning "Некоторые пакеты не установились, пробуем по одному..."
            while IFS= read -r package || [[ -n "$package" ]]; do
                [[ -z "$package" || "$package" =~ ^# ]] && continue
                sudo -u "$BOT_USERNAME" env "HOME=/home/${BOT_USERNAME}" "${VENV_DIR}/bin/pip" install -U "$package" 2>/dev/null || log_warning "Не удалось: $package"
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
echo "🦭 Запусти: ${COMMAND_NAME} start"
SCRIPT
    chmod +x "${INSTALL_DIR}/update.sh"
    
    # Устанавливаем владельца и права
    chown -R "${BOT_USERNAME}:${BOT_USERNAME}" "${INSTALL_DIR}"
    # Убеждаемся что все файлы доступны для записи владельцу
    chmod -R u+w "${INSTALL_DIR}"
    
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
    log_step "Шаг 7/7: Первоначальная настройка"
    
    VENV_DIR="/home/${BOT_USERNAME}/venv"
    CONFIG_FILE="${INSTALL_DIR}/bot_settings/config.json"
    
    # Проверяем, настроен ли бот уже
    if [ -f "$CONFIG_FILE" ]; then
        # Проверяем есть ли токены в конфиге
        if grep -q '"token": "[^"]*[a-zA-Z0-9]' "$CONFIG_FILE" 2>/dev/null; then
            log_info "Обнаружен существующий конфиг. Пропускаем первичную настройку."
            log_info "Для повторной настройки: ${COMMAND_NAME} setup"
            return 0
        fi
    fi
    
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║           🎉 УСТАНОВКА ПОЧТИ ЗАВЕРШЕНА! 🎉                    ║${NC}"
    echo -e "${GREEN}╠═══════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}║  Сейчас бот запросит у тебя ТОКЕНЫ для работы:                ║${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}║  1️⃣  ТОКЕН PLAYEROK                                            ║${NC}"
    echo -e "${GREEN}║      Где взять: Playerok → Настройки → API токен              ║${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}║  2️⃣  ТОКЕН TELEGRAM БОТА                                       ║${NC}"
    echo -e "${GREEN}║      Где взять: Напиши @BotFather в Telegram → /newbot        ║${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}║  3️⃣  ПАРОЛЬ ОТ TG БОТА                                         ║${NC}"
    echo -e "${GREEN}║      Придумай надёжный пароль для доступа к боту              ║${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}╠═══════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${GREEN}║  ⚠️  ВАЖНО: После ввода токенов бот ЗАПУСТИТСЯ!                ║${NC}"
    echo -e "${GREEN}║  Когда увидишь логи работы — нажми Ctrl+C для выхода.         ║${NC}"
    echo -e "${GREEN}║  Бот продолжит работать в фоне автоматически!                 ║${NC}"
    echo -e "${GREEN}║  ОБЯЗАТЕЛЬНО ПРОПИШИ /restart в тг боте после его запуска     ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -ne "${CYAN}Нажми Enter когда будешь готов ввести токены...${NC}"
    read -r < /dev/tty || true
    
    echo ""
    log_info "Запуск бота от имени пользователя ${BOT_USERNAME}..."
    echo ""
    
    # Запускаем бота для интерактивной настройки
    # Важно: нужен TTY для работы input() в Python
    # Перенаправляем /dev/tty на stdin чтобы Python input() работал
    
    su - "$BOT_USERNAME" -c "cd '${INSTALL_DIR}' && LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 PYTHONUNBUFFERED=1 '${VENV_DIR}/bin/python' -u bot.py" < /dev/tty || true
    
    echo ""
    
    # Проверяем что конфиг создался и содержит данные
    if [ -f "$CONFIG_FILE" ]; then
        if grep -q '"token": "[^"]*[a-zA-Z0-9]' "$CONFIG_FILE" 2>/dev/null; then
            log_success "Первичная настройка завершена успешно!"
        else
            log_warning "Конфиг создан, но токены не обнаружены."
            log_info "Запусти настройку заново: ${COMMAND_NAME} setup"
        fi
    else
        log_warning "Конфиг не создан."
        log_info "Запусти настройку: ${COMMAND_NAME} setup"
    fi
    
    echo ""
    echo -e "${CYAN}┌─────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${CYAN}│  📝 ЗАПОМНИ КОМАНДУ ДЛЯ УПРАВЛЕНИЯ БОТОМ:                   │${NC}"
    echo -e "${CYAN}│                                                             │${NC}"
    echo -e "${CYAN}│     ${GREEN}${COMMAND_NAME}${CYAN}                                         │${NC}"
    echo -e "${CYAN}│                                                             │${NC}"
    echo -e "${CYAN}│  Примеры:                                                   │${NC}"
    echo -e "${CYAN}│    ${COMMAND_NAME} start   — запустить                      │${NC}"
    echo -e "${CYAN}│    ${COMMAND_NAME} stop    — остановить                     │${NC}"
    echo -e "${CYAN}│    ${COMMAND_NAME} logs    — посмотреть логи                │${NC}"
    echo -e "${CYAN}│    ${COMMAND_NAME} setup   — настроить заново               │${NC}"
    echo -e "${CYAN}└─────────────────────────────────────────────────────────────┘${NC}"
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
        log_warning "Бот не запустился. Проверь логи: ${COMMAND_NAME} logs"
        log_info "Возможно нужно повторить настройку: ${COMMAND_NAME} setup"
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
BOT_HOME="/home/${BOT_USERNAME}"
COMMAND_NAME="${COMMAND_NAME}"
PYENV_ROOT="/opt/pyenv"
PYENV_PATH="/opt/pyenv/bin:/opt/pyenv/shims"

# Проверка статуса
is_running() {
    systemctl is-active --quiet \$SERVICE
}

case "\$1" in
    start)
        if is_running; then
            echo "⚠️  Бот уже запущен!"
            echo "   Используй: ${COMMAND_NAME} status"
        else
            echo "🚀 Запуск бота..."
            sudo systemctl start \$SERVICE
            sleep 2
            if is_running; then
                echo "✅ Бот запущен"
            else
                echo "❌ Ошибка запуска. Проверь логи: ${COMMAND_NAME} logs"
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
            echo "❌ Ошибка. Проверь логи: ${COMMAND_NAME} logs"
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
    logs500)
        echo "📋 Последние 500 строк логов:"
        sudo journalctl -u \$SERVICE -n 500 --no-hostname
        ;;
    logs1000)
        echo "📋 Последние 1000 строк логов:"
        sudo journalctl -u \$SERVICE -n 1000 --no-hostname
        ;;
    error)
        echo "📋 Последние ошибки из логов:"
        sudo journalctl -u \$SERVICE --priority=err --since "6 hours ago" -n 50 --no-hostname
        echo ""
        echo "📋 Последние критические ошибки:"
        sudo journalctl -u \$SERVICE --priority=crit --since "6 hours ago" -n 20 --no-hostname
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
        echo "   После настройки нажми Ctrl+C и запусти: ${COMMAND_NAME} start"
        echo ""
        # Останавливаем сервис если запущен
        sudo systemctl stop \$SERVICE 2>/dev/null || true
        # Запускаем от имени пользователя бота С ПЕРЕХОДОМ В ДИРЕКТОРИЮ БОТА
        cd "\$INSTALL_DIR" && sudo -u \$BOT_USER env "HOME=\$BOT_HOME" "PYENV_ROOT=\$PYENV_ROOT" "PATH=\$PYENV_PATH:\$PATH" LANG=en_US.UTF-8 \${VENV_DIR}/bin/python \${INSTALL_DIR}/bot.py
        ;;
    update)
        echo "🔄 Обновление бота..."
        sudo systemctl stop \$SERVICE 2>/dev/null || true
        sudo -u \$BOT_USER env "HOME=\$BOT_HOME" git -C \$INSTALL_DIR pull origin main 2>/dev/null || sudo -u \$BOT_USER env "HOME=\$BOT_HOME" git -C \$INSTALL_DIR pull origin master
        sudo -u \$BOT_USER env "HOME=\$BOT_HOME" "PYENV_ROOT=\$PYENV_ROOT" "PATH=\$PYENV_PATH:\$PATH" \${VENV_DIR}/bin/pip install -U -r \${INSTALL_DIR}/requirements.txt -q
        echo "✅ Обновление завершено"
        echo "   Запусти: ${COMMAND_NAME} start"
        ;;
    *)
        echo "🦭 SealPlayerok Bot - Команды:"
        echo ""
        echo "  ${COMMAND_NAME} start     - 🚀 Запустить бота"
        echo "  ${COMMAND_NAME} stop      - 🛑 Остановить бота"
        echo "  ${COMMAND_NAME} restart   - 🔄 Перезапустить бота"
        echo "  ${COMMAND_NAME} status    - 📊 Статус бота"
        echo "  ${COMMAND_NAME} logs      - 📋 Логи в реальном времени"
        echo "  ${COMMAND_NAME} logs100   - 📋 Последние 100 строк логов"
        echo "  ${COMMAND_NAME} logs500   - 📋 Последние 500 строк логов"
        echo "  ${COMMAND_NAME} logs1000  - 📋 Последние 1000 строк логов"
        echo "  ${COMMAND_NAME} error     - 📋 Показать последние ошибки"
        echo "  ${COMMAND_NAME} enable    - ✅ Включить автозапуск"
        echo "  ${COMMAND_NAME} disable   - ❌ Отключить автозапуск"
        echo "  ${COMMAND_NAME} setup     - 🔧 Первоначальная настройка"
        echo "  ${COMMAND_NAME} update    - 🔄 Обновить бота"
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
    
    # Создаём симлинк в /usr/local/bin для глобального доступа (уникальное имя)
    ln -sf "$COMMANDS_FILE" "/usr/local/bin/${COMMAND_NAME}" 2>/dev/null || true
    
    log_success "Команда '${COMMAND_NAME}' создана для управления ботом"
}

# Создание глобальной команды 'seal'
create_global_seal_command() {
    SEAL_GLOBAL="/usr/local/bin/seal"
    
    cat > "$SEAL_GLOBAL" << 'SEALEOF'
#!/bin/bash
# 🦭 SealPlayerok Bot - Глобальная команда управления

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

INSTALL_URL="https://raw.githubusercontent.com/leizov/Seal-Playerok-Bot/main/install.sh"

case "$1" in
    install|new)
        echo -e "${CYAN}🦭 Запуск установщика SealPlayerok Bot...${NC}"
        echo ""
        bash <(curl -sL "$INSTALL_URL")
        ;;
    setup)
        echo -e "${YELLOW}⚠️  Команда 'seal setup' требует имя бота!${NC}"
        echo ""
        echo -e "Правильное использование:"
        echo -e "  ${GREEN}seal <имя> setup${NC}  — настройка конкретного бота"
        echo -e "  ${GREEN}seal-<имя> setup${NC}  — альтернативный формат"
        echo ""
        echo -e "Пример: ${GREEN}seal sealbot setup${NC}"
        echo ""
        echo -e "${CYAN}Установленные боты:${NC}"
        for cmd in /usr/local/bin/seal-*; do
            [ -x "$cmd" ] && [ -f "$cmd" ] && echo -e "  - $(basename $cmd)"
        done
        echo ""
        ;;
    list|ls)
        echo -e "${CYAN}🦭 Установленные боты SealPlayerok:${NC}"
        echo ""
        found=0
        for cmd in /usr/local/bin/seal-*; do
            if [ -x "$cmd" ] && [ -f "$cmd" ]; then
                name=$(basename "$cmd")
                if systemctl is-active --quiet "${name}" 2>/dev/null; then
                    status="${GREEN}✅ работает${NC}"
                else
                    status="${RED}❌ остановлен${NC}"
                fi
                echo -e "  ${GREEN}${name}${NC} - ${status}"
                found=1
            fi
        done
        if [ $found -eq 0 ]; then
            echo -e "  ${YELLOW}Боты не найдены${NC}"
            echo ""
            echo -e "  Для установки: ${GREEN}seal install${NC}"
        fi
        echo ""
        ;;
    help|--help|-h|"")
        echo -e "${CYAN}🦭 SealPlayerok Bot - Глобальные команды${NC}"
        echo ""
        echo -e "  ${GREEN}seal install${NC}      - 🚀 Установить нового бота"
        echo -e "  ${GREEN}seal list${NC}         - 📋 Список установленных ботов"
        echo ""
        echo -e "${YELLOW}Для управления конкретным ботом (два формата):${NC}"
        echo -e "  ${GREEN}seal <имя> start${NC}    или  ${GREEN}seal-<имя> start${NC}"
        echo -e "  ${GREEN}seal <имя> stop${NC}     или  ${GREEN}seal-<имя> stop${NC}"
        echo -e "  ${GREEN}seal <имя> setup${NC}    или  ${GREEN}seal-<имя> setup${NC}   - настроить"
        echo -e "  ${GREEN}seal <имя> logs${NC}     или  ${GREEN}seal-<имя> logs${NC}"
        echo ""
        echo -e "${CYAN}Установленные боты:${NC}"
        for cmd in /usr/local/bin/seal-*; do
            [ -x "$cmd" ] && [ -f "$cmd" ] && echo -e "  - $(basename $cmd)"
        done
        echo ""
        ;;
    *)
        # Попробуем найти бота с таким именем
        if [ -x "/usr/local/bin/seal-$1" ]; then
            shift_cmd="$1"
            shift
            "/usr/local/bin/seal-${shift_cmd}" "$@"
        else
            echo -e "${RED}Неизвестная команда: $1${NC}"
            echo -e "Используй ${GREEN}seal help${NC} для справки"
        fi
        ;;
esac
SEALEOF
    
    chmod +x "$SEAL_GLOBAL"
    log_success "Глобальная команда 'seal' создана"
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
    echo -e "  ${GREEN}${COMMAND_NAME} start${NC}      - 🚀 Запустить бота"
    echo -e "  ${GREEN}${COMMAND_NAME} stop${NC}       - 🛑 Остановить бота"
    echo -e "  ${GREEN}${COMMAND_NAME} restart${NC}    - 🔄 Перезапустить бота"
    echo -e "  ${GREEN}${COMMAND_NAME} status${NC}     - 📊 Статус бота"
    echo -e "  ${GREEN}${COMMAND_NAME} logs${NC}       - 📋 Логи в реальном времени"
    echo -e "  ${GREEN}${COMMAND_NAME} logs100${NC}    - 📋 Последние 100 строк логов"
    echo -e "  ${GREEN}${COMMAND_NAME} logs500${NC}    - 📋 Последние 500 строк логов"
    echo -e "  ${GREEN}${COMMAND_NAME} logs1000${NC}   - 📋 Последние 1000 строк логов"
    echo -e "  ${GREEN}${COMMAND_NAME} error${NC}     - 📋 Показать последние ошибки"
    echo -e ""
    echo -e "  ${CYAN}${COMMAND_NAME} setup${NC}      - 🔧 Повторная настройка"
    echo -e "  ${CYAN}${COMMAND_NAME} update${NC}     - 🔄 Обновить бота"
    echo -e "  ${CYAN}${COMMAND_NAME} enable${NC}     - ✅ Включить автозапуск"
    echo -e "  ${CYAN}${COMMAND_NAME} disable${NC}    - ❌ Отключить автозапуск"
    echo -e ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}📝 АЛЬТЕРНАТИВНЫЕ КОМАНДЫ (systemctl):${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e ""
    echo -e "  sudo systemctl start|stop|restart|status ${SERVICE_NAME}"
    echo -e "  sudo journalctl -u ${SERVICE_NAME} -f"
    echo -e ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}🌐 ГЛОБАЛЬНЫЕ КОМАНДЫ:${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e ""
    echo -e "  ${GREEN}seal${NC}            - 📋 Справка по всем ботам"
    echo -e "  ${GREEN}seal list${NC}       - 📋 Список установленных ботов"
    echo -e "  ${GREEN}seal install${NC}    - 🚀 Установить ещё одного бота"
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
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}❓ ЧТО ДЕЛАТЬ ДАЛЬШЕ:${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e ""
    echo -e "  ${GREEN}1.${NC} Открой Telegram и найди своего бота"
    echo -e "  ${GREEN}2.${NC} Напиши ему /start"
    echo -e "  ${GREEN}3.${NC} Управляй ботом через меню Telegram!"
    echo -e ""
    echo -e "  ${CYAN}💡 Если бот не отвечает — проверь логи:${NC}"
    echo -e "     ${GREEN}${COMMAND_NAME} logs${NC}"
    echo -e ""
    echo -e "  ${CYAN}💡 Если нужно перенастроить токены:${NC}"
    echo -e "     ${GREEN}${COMMAND_NAME} setup${NC}"
    echo -e ""
    echo -e "${GREEN}🦭 Приятного использования!${NC}"
    echo -e ""
    
    # Показываем статус бота
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║  ✅ БОТ УСПЕШНО РАБОТАЕТ В ФОНЕ!                          ║${NC}"
        echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
        echo -e ""
        echo -e "   Команда для логов: ${GREEN}${COMMAND_NAME} logs${NC}"
    else
        echo -e "${YELLOW}╔═══════════════════════════════════════════════════════════╗${NC}"
        echo -e "${YELLOW}║  ⚠️  БОТ НЕ ЗАПУЩЕН                                        ║${NC}"
        echo -e "${YELLOW}╚═══════════════════════════════════════════════════════════╝${NC}"
        echo -e ""
        echo -e "   Запусти бота: ${GREEN}${COMMAND_NAME} start${NC}"
        echo -e "   Или настрой заново: ${GREEN}${COMMAND_NAME} setup${NC}"
    fi
    echo -e ""
}

# Основная функция
main() {
    # Показываем баннер
    show_banner
    
    # Проверяем что запущено от root
    check_root
    
    # Создаём глобальную команду seal сразу (чтобы работала даже при прерывании)
    create_global_seal_command
    
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
    
    # Создание команды управления
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
