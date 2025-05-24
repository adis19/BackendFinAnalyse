import google.generativeai as genai
from datetime import date
import json
import re
from typing import Dict, Any, List, Optional
from .pdf_downloader import download_pdf, cleanup_pdf
import os
import time

# Конфигурация Google Gemini API
GOOGLE_API_KEY = 'AIzaSyDvsUFB83k9nq5vOdDPEb4-8iOfAtfvWu0'

# Промпт для анализа финансовой отчетности с выводом в JSON
ANALYSIS_PROMPT = """
ТЫ – АВТОМАТИЗИРОВАННЫЙ ФИНАНСОВЫЙ АНАЛИТИК для мобильного приложения. Твоя задача – извлечь ключевые финансовые данные и рассчитать показатели банка из приложенного документа (PDF или изображения финансового отчета). Представь результат в формате JSON.

**ВАЖНО: ИНСТРУКЦИИ ПО ЧТЕНИЮ ИСХОДНОГО ОТЧЕТА:**

В отчете есть три основных раздела:
1. "ОТЧЕТ О ФИНАНСОВОМ ПОЛОЖЕНИИ" (баланс)
2. "ОТЧЕТ О СОВОКУПНОМ ДОХОДЕ" (прибыли и убытки)
3. "СВЕДЕНИЯ О СОБЛЮДЕНИИ ЭКОНОМИЧЕСКИХ НОРМАТИВОВ"

**ОСОБОЕ ВНИМАНИЕ К РАЗДЕЛУ "СВЕДЕНИЯ О СОБЛЮДЕНИИ ЭКОНОМИЧЕСКИХ НОРМАТИВОВ":**
- Коэффициент достаточности (адекватности) суммарного капитала (К2.1) -> это CAR
- Коэффициент достаточности (адекватности) капитала Первого уровня (К2.2) -> это Tier1
- Леверидж (К2.4) -> это leverage
- Норматив (показатель) ликвидности банка (К3.1) -> это LCR
- Дополнительный запас капитала банка (индекс "буфер капитала") -> это capital_buffer

**РАСЧЕТ ПОКАЗАТЕЛЕЙ:**

1. **Коэффициенты из нормативов** - брать из раздела "СВЕДЕНИЯ О СОБЛЮДЕНИИ ЭКОНОМИЧЕСКИХ НОРМАТИВОВ" (если есть):
   - CAR (K2.1)
   - Tier1 (K2.2)
   - Leverage (K2.4)
   - LCR (K3.1)
   - Capital Buffer

2. **Расчетные показатели** (рассчитывать на основе данных баланса и отчета о прибылях и убытках):

   a) **ROA (Рентабельность активов)**:
      - Формула: (Чистая прибыль за период * 12/кол-во месяцев) / ((Активы на конец + Активы на начало периода) / 2) * 100%
      - Пример для квартального отчета: (Чистая прибыль * 4) / Средние активы * 100%
      - Пример для месячного отчета: (Чистая прибыль * 12) / Средние активы * 100%
      - Брать активы текущие и за аналогичный период прошлого года
   
   b) **ROE (Рентабельность капитала)**:
      - Формула: (Чистая прибыль за период * 12/кол-во месяцев) / ((Капитал на конец + Капитал на начало периода) / 2) * 100%
      - Пример для квартального отчета: (Чистая прибыль * 4) / Средний капитал * 100%
      - Пример для месячного отчета: (Чистая прибыль * 12) / Средний капитал * 100%
      - Брать капитал текущий и за аналогичный период прошлого года

   c) **CIR (Cost to Income Ratio)**:
      - Формула: Операционные расходы / (Чистый процентный доход + Чистый комиссионный доход + Прочие операционные доходы) * 100%
      - Операционные расходы берутся из отчета о прибылях и убытках
      - В знаменателе сумма всех операционных доходов до создания резервов

   d) **Loan to Deposit**:
      - Формула: Кредиты, выданные клиентам (за вычетом резервов) / Текущие счета и депозиты клиентов * 100%
      - Все данные берутся из баланса
      - Использовать чистую сумму кредитов (за вычетом резервов)

**ВАЖНО ПРИ РАСЧЕТЕ:**
1. Все расчеты должны производиться на основе фактических данных из отчетов
2. Если какие-то данные отсутствуют - показатель не рассчитывается (null)
3. Для годовых коэффициентов используется соответствующая аннуализация:
   - Для квартальных данных умножать на 4
   - Для месячных данных умножать на 12
4. Всегда проверять наличие отрицательных значений и их влияние на расчет
5. Округлять результаты до 2 знаков после запятой

**ВАЖНО ДЛЯ РАЗДЕЛА SUMMARY:**
1. Strengths (сильные стороны) - ОБЯЗАТЕЛЬНО указать минимум 2 пункта:
   - Рост активов (если есть)
   - Рост прибыли (если есть)
   - Улучшение нормативов (если есть)
   - Рост кредитного портфеля (если есть)

2. Attention points (области для внимания) - ОБЯЗАТЕЛЬНО указать минимум 1 пункт:
   - Снижение прибыли (если есть)
   - Снижение активов (если есть)
   - Ухудшение нормативов (если есть)
   - Рост резервов на потери (если есть)

3. Conclusion (итог) - ОБЯЗАТЕЛЬНО сформулировать подробный вывод, включающий:
   - Общая динамика:
     * Изменение активов (рост/снижение в %)
     * Изменение кредитного портфеля (рост/снижение в %)
     * Изменение депозитной базы (рост/снижение в %)
     * Динамика прибыли (рост/снижение в %)
   - Качество активов:
     * Уровень NPL (если доступно)
     * Уровень резервирования
   - Достаточность капитала:
     * Текущие значения всех коэффициентов
     * Сравнение с нормативными значениями
     * Запас прочности по каждому нормативу
   - Ликвидность:
     * Текущие показатели ликвидности
     * Соотношение кредитов и депозитов
   - Эффективность:
     * ROA и ROE (если рассчитаны)
     * CIR (если рассчитан)
   - Общий вывод:
     * Сильные стороны банка
     * Области для мониторинга
     * Прогноз развития

**ВАЖНЫЕ ПРАВИЛА:**
1. Все числовые значения должны быть числами, не строками
2. Используй null ТОЛЬКО если данных действительно нет или их невозможно рассчитать
3. Все проценты указывай как числа (например: 20.5, а не "20.5%")
4. Всегда проверяй расчеты дважды
5. Используй точные названия из отчета
6. Указывай единицы измерения (обычно "тыс. сом")
7. НИКОГДА не оставляй пустыми разделы summary

Результат должен быть в следующем формате JSON:
{
  "bank_name": "Точное название банка из документа",
  "current_period": "Дата в формате DD.MM.YYYY",
  "comparative_periods": ["31.12.2024", "31.03.2024"],
  "balance": {
    "assets": {
      "total": {
        "current": 1000000,
        "previous_year_end": 950000,
        "previous_period_same": 920000,
        "change_since_year_end": 50000,
        "change_since_year_end_percent": 5.26,
        "unit": "тыс. сом"
      },
      "components": [
        {
          "name": "Точное название из отчета",
          "current": 100000,
          "previous_year_end": 95000,
          "previous_period_same": 90000,
          "share_in_total": 10.0,
          "unit": "тыс. сом"
        }
      ]
    },
    "liabilities": {
      "total": {
        "current": 800000,
        "previous_year_end": 760000,
        "previous_period_same": 740000,
        "change_since_year_end": 40000,
        "change_since_year_end_percent": 5.26,
        "unit": "тыс. сом"
      },
      "components": []
    },
    "equity": {
      "total": {
        "current": 200000,
        "previous_year_end": 190000,
        "previous_period_same": 180000,
        "change_since_year_end": 10000,
        "change_since_year_end_percent": 5.26,
        "unit": "тыс. сом"
      },
      "components": []
    }
  },
  "income_statement": {
    "available": true,
    "net_profit": {
      "current": 15000,
      "previous_period_same": 14000,
      "change": 1000,
      "change_percent": 7.14,
      "unit": "тыс. сом"
    },
    "net_interest_income": {
      "current": 30000,
      "previous_period_same": 28000,
      "unit": "тыс. сом"
    },
    "net_fee_income": {
      "current": 5000,
      "previous_period_same": 4800,
      "unit": "тыс. сом"
    }
  },
  "ratios": {
    "liquidity": {
      "lcr": {
        "current": 68.8,
        "regulatory_minimum": 45.0
      },
      "loan_to_deposit": {
        "current": 55.9
      }
    },
    "capital_adequacy": {
      "car": {
        "current": 20.2,
        "regulatory_minimum": 12.0
      },
      "tier1": {
        "current": 20.0,
        "regulatory_minimum": 7.5
      },
      "leverage": {
        "current": 12.1,
        "regulatory_minimum": 6.0
      },
      "capital_buffer": {
        "current": 22.6,
        "regulatory_minimum": 20.0
      }
    },
    "profitability": {
      "roa": {
        "current": 3.5,
        "annualized": true
      },
      "roe": {
        "current": 23.4,
        "annualized": true
      }
    },
    "efficiency": {
      "cir": {
        "current": 53.5
      }
    }
  },
  "summary": {
    "strengths": [
      "Рост общих активов на X% по сравнению с концом предыдущего года (с Y до Z тыс. сом)",
      "Увеличение чистой прибыли на A% по сравнению с аналогичным периодом прошлого года"
    ],
    "attention_points": [
      "Снижение показателя X на Y%",
      "Ухудшение норматива Z до X%"
    ],
    "conclusion": "Банк демонстрирует [положительную/стабильную/неустойчивую] динамику. Все обязательные нормативы [соблюдаются/есть отклонения]. Общее финансовое состояние [устойчивое/требует внимания]."
  }
}"""

# Промпт для сравнительного анализа нескольких банков
COMPARATIVE_ANALYSIS_PROMPT = """
Ты получил результаты анализа финансовой отчетности нескольких банков. Теперь твоя задача - сравнить эти банки между собой и предоставить сравнительный анализ в формате JSON. Используй только те данные, которые есть у ВСЕХ анализируемых банков. Фокусируйся на сравнении ключевых показателей.

Результирующий JSON должен иметь следующую структуру:
```json
{
  "comparative_analysis": {
    "period": "Анализируемый период, например, 'Апрель 2025'",
    "banks_compared": ["Банк 1", "Банк 2", "Банк 3"], // Названия всех сравниваемых банков
    "assets_comparison": {
      "ranking": [
        {"bank": "Банк 2", "value": 1500000, "unit": "тыс. сом", "share_of_largest": 100},
        {"bank": "Банк 1", "value": 1000000, "unit": "тыс. сом", "share_of_largest": 66.67},
        {"bank": "Банк 3", "value": 800000, "unit": "тыс. сом", "share_of_largest": 53.33}
      ],
      "growth_rates": [
        {"bank": "Банк 3", "growth_percent": 7.5, "rank": 1},
        {"bank": "Банк 1", "growth_percent": 5.26, "rank": 2},
        {"bank": "Банк 2", "growth_percent": 3.1, "rank": 3}
      ]
    },
    "profitability_comparison": {
      "net_profit": {
        "ranking": [
          {"bank": "Банк 2", "value": 25000, "unit": "тыс. сом", "share_of_largest": 100},
          {"bank": "Банк 1", "value": 15000, "unit": "тыс. сом", "share_of_largest": 60},
          {"bank": "Банк 3", "value": 10000, "unit": "тыс. сом", "share_of_largest": 40}
        ]
      },
      "roa": {
        "ranking": [
          {"bank": "Банк 3", "value": 1.8, "rank": 1},
          {"bank": "Банк 2", "value": 1.7, "rank": 2},
          {"bank": "Банк 1", "value": 1.5, "rank": 3}
        ]
      },
      "roe": {
        "ranking": [
          {"bank": "Банк 3", "value": 9.2, "rank": 1},
          {"bank": "Банк 2", "value": 8.4, "rank": 2},
          {"bank": "Банк 1", "value": 7.5, "rank": 3}
        ]
      }
    },
    "capital_adequacy_comparison": {
      "car": {
        "ranking": [
          {"bank": "Банк 1", "value": 18.5, "rank": 1},
          {"bank": "Банк 3", "value": 17.2, "rank": 2},
          {"bank": "Банк 2", "value": 15.5, "rank": 3}
        ]
      }
    },
    "liquidity_comparison": {
      "loan_to_deposit": {
        "ranking": [
          {"bank": "Банк 3", "value": 65.5, "rank": 1, "note": "Более низкое значение обычно означает более высокую ликвидность"},
          {"bank": "Банк 1", "value": 75.4, "rank": 2},
          {"bank": "Банк 2", "value": 82.1, "rank": 3}
        ]
      }
    },
    "conclusions": {
      "market_position": {
        "by_assets": [
          {"bank": "Название", "share": 25.5, "rank": 1, "trend": "рост/снижение"}
        ],
        "by_loans": [
          {"bank": "Название", "share": 20.3, "rank": 2, "trend": "рост/снижение"}
        ],
        "by_deposits": [
          {"bank": "Название", "share": 22.1, "rank": 2, "trend": "рост/снижение"}
        ]
      },
      "efficiency_comparison": {
        "most_profitable": {
          "bank": "Название",
          "roa": 2.5,
          "roe": 15.2,
          "key_factors": ["Фактор 1", "Фактор 2"]
        },
        "most_efficient": {
          "bank": "Название",
          "cir": 45.2,
          "key_factors": ["Фактор 1", "Фактор 2"]
        }
      },
      "stability_comparison": {
        "capital_adequacy": {
          "strongest": "Название банка",
          "key_metrics": ["CAR: 20.2%", "Tier1: 18.5%"],
          "analysis": "Детальный анализ"
        },
        "liquidity": {
          "strongest": "Название банка",
          "key_metrics": ["LCR: 85.5%", "NSFR: 120.5%"],
          "analysis": "Детальный анализ"
        }
      },
      "growth_dynamics": {
        "fastest_growing": {
          "bank": "Название",
          "metrics": ["Активы: +15.2%", "Кредиты: +18.5%"],
          "sustainability_analysis": "Анализ устойчивости роста"
        },
        "most_stable": {
          "bank": "Название",
          "metrics": ["Низкая волатильность показателей", "Стабильная база фондирования"],
          "analysis": "Почему этот банк считается наиболее стабильным"
        }
      },
      "detailed_conclusion": {
        "market_overview": "Общий анализ состояния сравниваемых банков",
        "key_trends": [
          "Тренд 1 и его влияние на банки",
          "Тренд 2 и его влияние на банки"
        ],
        "recommendations": [
          "Рекомендация 1 с обоснованием",
          "Рекомендация 2 с обоснованием"
        ],
        "risk_factors": [
          "Риск-фактор 1 и его потенциальное влияние",
          "Риск-фактор 2 и его потенциальное влияние"
        ],
        "outlook": "Прогноз развития ситуации на ближайшую перспективу"
      }
    }
  }
}
```

**ВАЖНО!** 
1. Используй только те показатели, которые доступны для всех сравниваемых банков.
2. Если каких-то данных нет для сравнения, опусти соответствующий раздел.
3. Всегда используй числа, а не строки для числовых значений.
4. Всегда указывай единицы измерения для финансовых показателей.
5. Предоставь обоснованные выводы в разделе "conclusions".
6. Ранжируй банки от лучшего к худшему по каждому показателю.
"""

# Функция инициализации API
def init_gemini_api():
    """
    Инициализирует Google Gemini API с заданным ключом
    """
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        return True
    except Exception as e:
        print(f"Ошибка инициализации Gemini API: {e}")
        return False

# Функция для извлечения JSON из текстового ответа Gemini
def extract_json_from_response(response_text: str) -> Dict[str, Any]:
    """
    Извлекает JSON из текстового ответа Gemini API
    
    Args:
        response_text: Текстовый ответ от Gemini API
        
    Returns:
        Словарь с данными из JSON
    """
    try:
        # Если ответ уже валидный JSON
        if response_text.strip().startswith('{') and response_text.strip().endswith('}'):
            return json.loads(response_text)
            
        # Ищем содержимое между маркерами markdown кода
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, response_text)
        
        if match:
            json_str = match.group(1).strip()
            return json.loads(json_str)
        
        # Если не нашли маркеры, пробуем напрямую парсить как JSON
        return json.loads(response_text)
    except Exception as e:
        print(f"Ошибка при извлечении JSON: {e}")
        return {"error": f"Не удалось распарсить ответ как JSON: {str(e)}", "raw_response": response_text}

async def analyze_report_from_url(report_url: str, bank_name: str, is_json_output: bool = True) -> Dict[str, Any]:
    """
    Анализирует отчет по URL с помощью Gemini
    
    Args:
        report_url: URL отчета для анализа
        bank_name: Название банка для логирования
        is_json_output: Флаг для возврата результата в формате JSON
        
    Returns:
        Словарь с результатами анализа
    """
    try:
        # Инициализация API при вызове функции
        init_gemini_api()
        
        # Скачиваем PDF файл
        pdf_path = download_pdf(report_url)
        if not pdf_path:
            return {"error": f"Не удалось загрузить PDF файл по URL: {report_url}"}
        
        try:
            print(f"Загрузка файла: {pdf_path}...")
            # 1. Загрузка файла в File API
            # display_name - это опциональное имя для вашего удобства
            uploaded_file = genai.upload_file(path=pdf_path,
                                          display_name=os.path.basename(pdf_path))
            print(f"Файл загружен: {uploaded_file.name} (URI: {uploaded_file.uri})")

            # 2. Выбор модели Gemini
            model = genai.GenerativeModel('gemini-2.0-flash')

            # 3. Создание контента для запроса: файл + промпт
            prompt_text = ANALYSIS_PROMPT if is_json_output else ANALYSIS_PROMPT.replace("формате JSON", "формате MARKDOWN")
            request_content = [
                uploaded_file,  # Ссылка на загруженный файл
                prompt_text
            ]

            print(f'Отправка запроса в Gemini API банк "{bank_name}"')
            # 4. Отправка запроса
            response = model.generate_content(request_content)

            if is_json_output:
                # Преобразуем текстовый ответ в JSON
                result = extract_json_from_response(response.text)
                print(f"Получен ответ от Gemini API для банка {bank_name}")
            else:
                result = {"markdown": response.text}
                print(f"Получен markdown-ответ от Gemini API для банка {bank_name}")
            
            return result
            
        finally:
            # Удаляем PDF файл после использования
            cleanup_pdf(pdf_path)
        
    except Exception as e:
        print(f"Ошибка при анализе отчета для банка {bank_name}: {str(e)}")
        return {"error": f"Произошла ошибка: {str(e)}"}


async def compare_bank_analyses(bank_analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Сравнивает анализы нескольких банков
    
    Args:
        bank_analyses: Список словарей с анализами банков
        
    Returns:
        Словарь со сравнительным анализом
    """
    try:
        # Инициализация API при вызове функции
        init_gemini_api()
        
        # Выбор модели Gemini
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Создание запроса со всеми анализами
        full_prompt = f"""
        {COMPARATIVE_ANALYSIS_PROMPT}
        
        Вот анализы банков, которые нужно сравнить:
        
        {bank_analyses}
        """
        
        response = model.generate_content(full_prompt)
        
        # Преобразуем текстовый ответ в JSON
        return extract_json_from_response(response.text)
        
    except Exception as e:
        return {"error": f"Произошла ошибка при сравнении банков: {str(e)}"}


async def analyze_bank_reports(reports: List[Dict[str, Any]], is_comparative: bool = False) -> Dict[str, Any]:
    """
    Анализирует отчеты банков, фильтрует нерабочие и создает структурированный ответ
    
    Args:
        reports: Список отчетов банков
        is_comparative: Флаг необходимости сравнительного анализа
        
    Returns:
        Структурированный результат анализа
    """
    start_time = time.time()  # Начало отсчета времени
    print(f"\nНачало анализа отчетов: {time.strftime('%H:%M:%S')}")

    # Группировка отчетов по банкам и выбор последнего для каждого банка
    bank_to_reports = {}
    for report in reports:
        bank_name = report.get("bank_name")
        
        # Если банк еще не в словаре, добавляем
        if bank_name not in bank_to_reports:
            bank_to_reports[bank_name] = []
            
        # Добавляем отчет в список для этого банка
        bank_to_reports[bank_name].append(report)
    
    # Результаты анализа для каждого банка
    analyses = {}
    
    # Обработка отчетов для каждого банка
    for bank_name, bank_reports in bank_to_reports.items():
        bank_start_time = time.time()  # Время начала анализа банка
        print(f"\nНачало обработки банка {bank_name}: {time.strftime('%H:%M:%S')}")
        
        # Сортировка отчетов по дате (от новых к старым)
        sorted_reports = sorted(
            bank_reports, 
            key=lambda r: r.get("report_date", "1900-01-01"), 
            reverse=True
        )
        
        # Попытка анализа каждого отчета, пока не получим успешный результат
        for report in sorted_reports:
            report_url = report.get("report_url")
            if not report_url:
                print(f"Пропуск отчета без URL для банка {bank_name}")
                continue
                
            try:
                print(f"Анализ отчета {report_url} для банка {bank_name}")
                # Анализ отчета
                analysis_result = await analyze_report_from_url(report_url, bank_name, is_json_output=True)
                
                # Если анализ успешен (нет ошибок)
                if "error" not in analysis_result:
                    analyses[bank_name] = analysis_result
                    bank_end_time = time.time()  # Время завершения анализа банка
                    bank_duration = bank_end_time - bank_start_time
                    print(f"Успешный анализ для банка {bank_name}. Время обработки: {bank_duration:.2f} сек.")
                    break
                else:
                    print(f"Ошибка при анализе отчета для банка {bank_name}: {analysis_result['error']}")
                    
            except Exception as e:
                print(f"Исключение при анализе отчета для банка {bank_name}: {str(e)}")
                # В случае ошибки пробуем следующий отчет
                continue
    
    # Если нужно сравнение и у нас более одного банка
    comparative_analysis = None
    if is_comparative and len(analyses) > 1:
        compare_start_time = time.time()  # Время начала сравнительного анализа
        print("\nЗапуск сравнительного анализа для банков")
        comparative_analysis = await compare_bank_analyses(list(analyses.values()))
        compare_duration = time.time() - compare_start_time
        print(f"Завершен сравнительный анализ. Время: {compare_duration:.2f} сек.")
    
    # Формируем итоговый результат
    result = {
        "reports": reports,  # Исходные отчеты
        "analyses": analyses,  # Анализы по банкам
        "execution_time": time.time() - start_time  # Общее время выполнения в секундах
    }
    
    # Добавляем сравнительный анализ, если он есть
    if comparative_analysis:
        result["comparative_analysis"] = comparative_analysis
    
    end_time = time.time()
    total_duration = end_time - start_time
    print(f"\nЗавершение анализа: {time.strftime('%H:%M:%S')}")
    print(f"Общее время выполнения: {total_duration:.2f} секунд")
    
    return result 