# Bank Reports API

API-сервис на базе FastAPI для сбора и анализа финансовых отчетов банков Кыргызстана с использованием Google Gemini AI.

## Основные возможности

- Сбор финансовых отчетов с официальных сайтов банков:
  - KICB Bank
  - Optima Bank
  - DemirBank
  - MBank
  - RSK Bank
- Поиск отчетов по диапазону дат
- Автоматический анализ финансовых отчетов с помощью Google Gemini AI
- Сравнительный анализ показателей нескольких банков
- RESTful API для получения отчетов и результатов анализа
- Легко расширяемая архитектура для добавления новых банков

## Установка

1. Клонируйте репозиторий
2. Создайте виртуальное окружение:
```
python -m venv venv
```
3. Активируйте виртуальное окружение:
```
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```
4. Установите зависимости:
```
pip install -r requirements.txt
```

## Запуск приложения

```
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

API будет доступно по адресу http://localhost:8000

Для доступа из локальной сети используйте IP-адрес вашего компьютера вместо localhost, например: http://192.168.88.176:8000

## Документация API

После запуска приложения вы можете получить доступ к:
- Документации API: http://localhost:8000/docs
- Спецификации OpenAPI: http://localhost:8000/openapi.json

## Основные эндпоинты

### GET /reports

Получить финансовые отчеты банков за указанный период.

**Параметры:**
- `start_date`: Начальная дата поиска отчетов (YYYY-MM-DD)
- `end_date`: (Опционально) Конечная дата поиска отчетов (YYYY-MM-DD)
- `bank_id`: (Опционально) ID банка (1=KICB, 2=Optima, 3=DemirBank, 4=MBank, 5=RSK, None=Все банки)
- `report_type`: (Опционально) Тип отчетов (monthly, quarterly, all)

**Пример:**
```
GET /reports?start_date=2023-01-01&end_date=2023-12-31&bank_id=1
```

### GET /analyze

Анализ финансовых отчетов банков с использованием Google Gemini AI.

**Параметры:**
- `start_date`: Начальная дата поиска отчетов (YYYY-MM-DD)
- `end_date`: (Опционально) Конечная дата поиска отчетов (YYYY-MM-DD)
- `bank_id`: (Опционально) ID банка (1=KICB, 2=Optima, 3=DemirBank, 4=MBank, 5=RSK, None=Все банки)
- `report_type`: (Опционально) Тип отчетов (monthly, quarterly, all)

**Пример:**
```
GET /analyze?start_date=2023-01-01&end_date=2023-12-31&bank_id=1
```

## Структура проекта

```
.
├── app/
│   ├── __init__.py
│   └── parsers/
│       ├── __init__.py
│       ├── base_parser.py
│       ├── models.py
│       ├── parser_service.py
│       ├── bank_kicb.py
│       ├── bank_optima.py
│       ├── bank_demirbank.py
│       ├── bank_mbank.py
│       ├── bank_rsk.py
│       └── gemini_analyzer.py
├── main.py
├── requirements.txt
└── README.md
``` 