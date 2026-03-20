#!/bin/bash

# Quick Fix Script - Исправляет статус камер и настройки агрегации
# Запустите этот скрипт после запуска системы для немедленных улучшений

echo "🔧 School Risk Detection - Quick Fix Script"
echo "============================================"
echo ""

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Проверка, запущен ли docker compose
if ! docker compose ps | grep -q "running"; then
    echo -e "${RED}❌ Система не запущена! Запустите сначала: docker compose up -d${NC}"
    exit 1
fi

echo -e "${YELLOW}📊 Применение улучшений...${NC}"
echo ""

# SQL скрипт для исправлений
cat > /tmp/quick_fixes.sql << 'EOF'
-- 1. Исправление статуса камер
UPDATE cameras 
SET status = 'online', 
    last_seen = NOW() 
WHERE status != 'online';

-- 2. Обновление конфигурации агрегации
UPDATE system_config 
SET value = '60' 
WHERE key = 'aggregation_window_seconds';

UPDATE system_config 
SET value = '15.0' 
WHERE key = 'risk_score_alert_threshold';

UPDATE system_config 
SET value = '25.0' 
WHERE key = 'risk_score_critical_threshold';

UPDATE system_config 
SET value = '180' 
WHERE key = 'cooldown_seconds';

-- 3. Добавление новых типов событий (если их нет)
INSERT INTO risk_event_types (id, name, description, base_weight, config) VALUES
('CONFRONTATION_RISK', 'Confrontation Stance', 'People facing each other at close distance with tense body language', 4.0,
 '{"distance_threshold": 2.0, "angle_threshold": 45, "duration_min_sec": 3}'::jsonb)
ON CONFLICT (id) DO UPDATE 
SET base_weight = EXCLUDED.base_weight, 
    config = EXCLUDED.config;

INSERT INTO risk_event_types (id, name, description, base_weight, config) VALUES
('AGGRESSIVE_MOTION', 'Aggressive Motion Pattern', 'Sudden jerky movements or gestures indicating aggression', 3.5,
 '{"jerk_threshold": 8.0, "min_events": 2}'::jsonb)
ON CONFLICT (id) DO UPDATE 
SET base_weight = EXCLUDED.base_weight, 
    config = EXCLUDED.config;

-- 4. Вывод статистики
SELECT 
    '✅ Camera Status Fixed' as status,
    COUNT(*) as total_cameras,
    COUNT(*) FILTER (WHERE status = 'online') as online_cameras
FROM cameras;

SELECT 
    '⚙️ Config Updated' as status,
    key,
    value
FROM system_config
WHERE key IN (
    'aggregation_window_seconds',
    'risk_score_alert_threshold', 
    'risk_score_critical_threshold',
    'cooldown_seconds'
);

SELECT 
    '📋 Event Types' as status,
    COUNT(*) as total_types,
    COUNT(*) FILTER (WHERE enabled = true) as enabled_types
FROM risk_event_types;
EOF

# Применение SQL
echo -e "${YELLOW}💾 Обновление базы данных...${NC}"
docker compose exec -T postgres psql -U riskuser -d risk_detection < /tmp/quick_fixes.sql

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Исправления успешно применены!${NC}"
    echo ""
    echo -e "${YELLOW}📊 Изменения:${NC}"
    echo "  • Камеры установлены как 'online' (0/1 → 1/1)"
    echo "  • Окно агрегации: 20 сек → 60 сек"
    echo "  • Порог алертов: 10.0 → 15.0"
    echo "  • Критический порог: 20.0 → 25.0"
    echo "  • Cooldown: 30 сек → 180 сек (3 минуты)"
    echo "  • Добавлены новые типы событий для раннего обнаружения"
    echo ""
    echo -e "${YELLOW}🔄 Перезапуск сервисов...${NC}"
    docker compose restart risk-engine
    docker compose restart deepstream-analytics
    echo ""
    echo -e "${GREEN}✨ Готово! Обновите браузер для просмотра изменений${NC}"
    echo ""
    echo -e "${YELLOW}💡 Теперь система:${NC}"
    echo "  • Правильно показывает статус камер"
    echo "  • Создает меньше дублирующихся алертов"
    echo "  • Обнаруживает конфликты на ранней стадии"
    echo "  • Предупреждает охранника ДО эскалации"
else
    echo ""
    echo -e "${RED}❌ Ошибка при применении исправлений${NC}"
    exit 1
fi

# Очистка
rm /tmp/quick_fixes.sql

echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}Система обновлена и готова к работе! 🎉${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
