#!/bin/bash

PROJECT_DIR="/var/www/html/vr/clients"

echo "======================================"
echo "Обновление Clients VR"
echo "======================================"

cd "$PROJECT_DIR" || {
    echo "Ошибка: не удалось перейти в каталог $PROJECT_DIR"
    exit 1
}

echo ""
echo "1. Проверка текущей версии Git..."
git status

echo ""
echo "2. Получение обновлений из GitHub..."
git pull

if [ $? -ne 0 ]; then
    echo "Ошибка при выполнении git pull"
    exit 1
fi

echo ""
echo "3. Проверка файла .env..."

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "Файл .env отсутствовал."
        echo "Создан новый .env из .env.example."
        echo "При необходимости заполните параметры FTP."
    else
        echo "Ошибка: отсутствуют .env и .env.example."
        exit 1
    fi
else
    echo "Файл .env найден."
fi

echo ""
echo "4. Остановка контейнеров..."
docker compose down

echo ""
echo "5. Пересборка и запуск контейнеров..."
docker compose up -d --build

if [ $? -ne 0 ]; then
    echo "Ошибка запуска Docker"
    echo ""
    echo "Последние логи:"
    docker compose logs --tail=100
    exit 1
fi

echo ""
echo "6. Проверка состояния контейнеров..."
docker compose ps

echo ""
echo "7. Последние логи приложения..."
docker compose logs app --tail=30

echo ""
echo "======================================"
echo "Обновление завершено"
echo "======================================"
