#Как использовать AI-Compare_Service:
###  AI-Compare_Service предназначен для парсинга поставщиков услуг:

# config.py
BASE_URL = "https://www.example-el-service.com"
CSS_SELECTOR = ".provider-card"
SCRAPER_INSTRUCTIONS = "Extract electricity providers: name, price per kWh, monthly fee, contract duration, bonuses, website, phone"

###  Для парсинга мобильных операторов:

BASE_URL = "https://www.example-mobile-service.com"
CSS_SELECTOR = ".plan-card"
SCRAPER_INSTRUCTIONS = "Extract mobile providers: name, data limit (GB), price per month, contract duration, bonuses, website, phone, call/SMS details"

###  Для парсинга банковских услуг:

BASE_URL = "https://www.example-finans-service.com"
CSS_SELECTOR = ".loan-offer"
SCRAPER_INSTRUCTIONS = "Extract bank loan offers: bank name, interest rate, loan term, monthly fee, website, phone"

### Система автоматически определит тип сервиса по URL и адаптирует парсинг. Для запуска: main.py
python main.py

## Для mobile-service
python main.py --model mobile_service_provider

## Для бизнес-справочника
python main.py --model business

## Ключевые дополнения:
# Полноценный инструмент для диагностики структуры сайтов с интеллектуальным анализом паттернов

# several_site_analyzer.py
Утилита представляет собой полноценный инструмент для диагностики структуры сайтов с интеллектуальным анализом паттернов, рекомендациями по оптимизации парсинга и гибкими опциями экспорта данных.
# 1. Система рекомендаций (print_recommendations)

Анализ cookie баннеров и JavaScript зависимостей
Поиск универсальных селекторов, работающих на нескольких сайтах
Детальный анализ контейнеров планов
Выявление больших страниц и потенциальных проблем с производительностью
Анализ паттернов в заголовках страниц

# 2. Экспорт результатов (export_results)

Сохранение данных анализа в JSON формате
Обработка ошибок при сохранении

# 3. Гибкая конфигурация (add_custom_url)

Возможность добавления пользовательских URL для анализа

# 4. Продвинутый CLI (main)

Поддержка аргументов командной строки
Экспорт результатов: --export filename.json
Добавление пользовательских URL: --url sitename https://example.com
Тихий режим: --silent

# 5. Улучшенная обработка ошибок

Graceful handling прерывания (Ctrl+C)
Детальное логирование критических ошибок
Статистика успешности выполнения

## Практические возможности:
# Запуск базового анализа:

python single_site_analyzer.py

# Добавление своего сайта:
python single_site_analyzer.py --url "mysite" "https://adstable.com"

# Минимальный вывод:
python single_site_analyzer.py --silent --export results.json

# Расширееный анализ нескольких сайтов
python several_site_analyzer.py

# Полный парсинг всех операторов
python unified_parser.py

# Анализ структуры конкретного оператора
python unified_parser.py --operator telia --analyze-only

# Парсинг с сохранением в custom файл
python unified_parser.py --output my_results.json

# Тихий режим для автоматизации
python unified_parser.py --silent

