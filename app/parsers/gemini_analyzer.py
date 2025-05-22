import google.generativeai as genai
from datetime import date
import json
import re
from typing import Dict, Any, List, Optional

# Конфигурация Google Gemini API
GOOGLE_API_KEY = 'AIzaSyDvsUFB83k9nq5vOdDPEb4-8iOfAtfvWu0'

# Промпт для анализа финансовой отчетности с выводом в JSON
ANALYSIS_PROMPT = """
ТЫ – АВТОМАТИЗИРОВАННЫЙ ФИНАНСОВЫЙ АНАЛИТИК для мобильного приложения. Твоя задача – извлечь ключевые финансовые данные и рассчитать показатели банка из приложенного документа (PDF или изображения финансового отчета). Представь результат в формате JSON, строго соблюдая указанную структуру.

**ВАЖНО: ИНСТРУКЦИИ ПО ЧТЕНИЮ ИСХОДНОГО ОТЧЕТА (ОСОБЕННО С НЕСКОЛЬКИМИ КОЛОНКАМИ ДАННЫХ):**

Финансовый отчет, который ты анализируешь (например, "Отчет о финансовом положении"), содержит данные в табличном виде.
КЛЮЧЕВЫМ МОМЕНТОМ является то, что для большинства финансовых показателей значения приведены в **НЕСКОЛЬКИХ КОЛОНКАХ**, каждая из которых соответствует **РАЗНОЙ ОТЧЕТНОЙ ДАТЕ**.

Например, ты увидишь колонки с заголовками типа:
* '30 апреля 2025 г. тыс.сом' (текущая отчетная дата)
* '30 апреля 2024 г. тыс.сом' (аналогичная дата предыдущего года)
* '31 декабря 2024 г. тыс.сом' (конец предыдущего отчетного года)
*(Примечание: Точные даты и формулировки могут отличаться, твоя задача – их идентифицировать).*

**ТВОИ ДЕЙСТВИЯ ПРИ ИЗВЛЕЧЕНИИ ДАННЫХ ИЗ ЭТИХ КОЛОНОК:**
1.  **ИДЕНТИФИЦИРУЙ ВСЕ КОЛОНКИ С ДАТАМИ:** Внимательно изучи заголовки таблицы и точно определи, какие даты или периоды представляют данные в каждой числовой колонке.
2.  **ИЗВЛЕКАЙ ЗНАЧЕНИЯ ИЗ КАЖДОЙ КОЛОНКИ:** Для каждой финансовой статьи (например, "Денежные средства", "Кредиты и авансы", "Нераспределенная прибыль") извлеки числовые значения из **ВСЕХ** доступных колонок с данными за разные периоды. Не игнорируй данные за предыдущие периоды – они критически важны для анализа.
3.  **ИСПОЛЬЗУЙ ДАННЫЕ ДЛЯ СРАВНЕНИЯ И РАСЧЕТА ИЗМЕНЕНИЙ:**
   * Для раздела **"I. Ключевые показатели финансового положения (Баланс)"** (Активы, Обязательства, Капитал):
       * Поле **"Изменение"** (например, для "Общие активы") должно рассчитываться как разница между значением на **текущую отчетную дату** (например, '30 апреля 2025 г.') и значением на **конец предыдущего отчетного года** (например, '31 декабря 2024 г.').
   * Для раздела **"II. Ключевые показатели финансовых результатов (Отчет о прибылях и убытках)"**:
       * Поле **"Изменение к пред. периоду"** (например, для "Чистая прибыль") должно рассчитываться как разница между показателем за текущий отчетный период и показателем за **аналогичный период предыдущего года** (например, '30 апреля 2025 г.' к '30 апреля 2024 г.').
   * Для раздела **"III. Финансовые коэффициенты"**:
       * Поле **"Предыдущее значение"** для коэффициентов должно, по возможности, браться на **конец предыдущего отчетного года**. Если этих данных нет, используй данные на **аналогичную дату предыдущего года**. Четко указывай, какая дата используется для сравнения, если это возможно.

**ВАЖНО: ТВОЙ ОТВЕТ ДОЛЖЕН БЫТЬ ТОЛЬКО В ФОРМАТЕ JSON!**

Результирующий JSON должен иметь следующую структуру:
```json
{
  "bank_name": "Название банка из документа",
  "current_period": "Дата конца текущего периода, например, '30.04.2025'",
  "comparative_periods": ["31.12.2024", "30.04.2024"], // Массив всех сравнительных дат из отчета
  "balance": {
    "assets": {
      "total": {
        "current": 1000000, // числовое значение на текущую дату
        "previous_year_end": 950000, // числовое значение на конец предыдущего года
        "previous_period_same": 920000, // числовое значение на аналогичную дату пред. года
        "change_since_year_end": 50000, // абсолютное изменение к концу пред. года
        "change_since_year_end_percent": 5.26, // процентное изменение к концу пред. года
        "unit": "тыс. сом" // единица измерения
      },
      "components": [
        {
          "name": "Денежные средства и их эквиваленты",
          "current": 100000,
          "previous_year_end": 95000,
          "previous_period_same": 90000,
          "share_in_total": 10.0, // доля в общих активах (проценты)
          "unit": "тыс. сом"
        },
        // Другие компоненты активов
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
      "components": [
        // Аналогично компонентам активов
      ]
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
      "components": [
        // Аналогично компонентам активов
      ]
    }
  },
  "income_statement": {
    "available": true, // false если отчет о прибылях и убытках не представлен
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
        "current": 120.5,
        "previous": 115.2,
        "regulatory_minimum": 100.0
      },
      "loan_to_deposit": {
        "current": 75.4,
        "previous": 78.2
      }
    },
    "capital_adequacy": {
      "car": {
        "current": 18.5,
        "previous": 17.8,
        "regulatory_minimum": 12.0
      },
      "tier1": {
        "current": 15.2,
        "previous": 14.5,
        "regulatory_minimum": 6.0
      },
      "leverage": {
        "current": 9.5,
        "previous": 9.0,
        "regulatory_minimum": 8.0
      },
      "capital_buffer": {
        "current": 2.5,
        "previous": 2.5,
        "regulatory_minimum": 2.5
      }
    },
    "profitability": {
      "roa": {
        "current": 1.5,
        "previous": 1.4,
        "annualized": true // указать, является ли показатель аннуализированным или квартальным
      },
      "roe": {
        "current": 7.5,
        "previous": 7.2,
        "annualized": true
      }
    },
    "efficiency": {
      "cir": {
        "current": 45.2,
        "previous": 47.5
      }
    }
  },
  "summary": {
    "strengths": [
      "Рост общих активов на 5.26% по сравнению с концом предыдущего года (с 950000 до 1000000 тыс. сом)",
      "Увеличение чистой прибыли на 7.14% по сравнению с аналогичным периодом прошлого года"
      // 1-3 ключевых положительных момента с цифрами
    ],
    "attention_points": [
      "Снижение рентабельности капитала с 7.5% до 7.2%",
      "Рост доли проблемных кредитов с 2.1% до 2.3%"
      // 1-3 момента, требующих внимания, с цифрами
    ],
    "conclusion": "Банк заработал хорошо за рассматриваемый период по сравнению с аналогичным периодом прошлого года, финансовая 'подушка' крепкая с учетом динамики. Ключевой момент: рост общих активов и повышение эффективности операций."
  },
  "full_report": "Здесь весь оригинальный текстовый анализ в формате как раньше"
}
```

**ВАЖНО!** 
1. Всегда используй числа, а не строки для числовых значений.
2. Если данные отсутствуют, используй null вместо значения.
3. Всегда указывай единицы измерения для финансовых показателей.
4. Не пропускай разделы структуры JSON, даже если данных нет - в этом случае используй null или пустые массивы.
5. Все показатели изменения обязательно рассчитывай, если есть исходные данные.
"""

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
      "strongest_overall": "Банк 2", // банк с лучшими общими показателями
      "fastest_growing": "Банк 3", // банк с самым быстрым ростом
      "most_profitable": "Банк 3", // банк с лучшими показателями рентабельности
      "most_stable": "Банк 1", // банк с лучшими показателями устойчивости
      "insights": [
        "Банк 3 показывает наилучшие показатели рентабельности, несмотря на меньший размер активов",
        "Банк 1 имеет самые высокие показатели достаточности капитала, что указывает на его финансовую устойчивость",
        "Банк 2 демонстрирует наибольший объем активов, но более низкие темпы роста по сравнению с конкурентами"
      ]
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

async def analyze_report_from_url(report_url: str, is_json_output: bool = True) -> Dict[str, Any]:
    """
    Анализирует отчет по URL с помощью Gemini
    
    Args:
        report_url: URL отчета для анализа
        is_json_output: Флаг для возврата результата в формате JSON
        
    Returns:
        Словарь с результатами анализа
    """
    try:
        # Инициализация API при вызове функции
        init_gemini_api()
        
        # Выбор модели Gemini
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Выбор промпта в зависимости от требуемого формата вывода
        prompt_text = ANALYSIS_PROMPT if is_json_output else ANALYSIS_PROMPT.replace("формате JSON", "формате MARKDOWN")
        
        # Создание запроса с URL и промптом
        full_prompt = f"""
        Пожалуйста, прочитай и проанализируй отчет по ссылке:
        {report_url}
        
        {prompt_text}
        """
        
        response = model.generate_content(full_prompt)
        
        if is_json_output:
            # Преобразуем текстовый ответ в JSON
            return extract_json_from_response(response.text)
        else:
            return {"markdown": response.text}
        
    except Exception as e:
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
                continue
                
            try:
                # Анализ отчета
                analysis_result = await analyze_report_from_url(report_url, is_json_output=True)
                
                # Если анализ успешен (нет ошибок)
                if "error" not in analysis_result:
                    analyses[bank_name] = analysis_result
                    break
                    
            except Exception:
                # В случае ошибки пробуем следующий отчет
                continue
    
    # Если нужно сравнение и у нас более одного банка
    comparative_analysis = None
    if is_comparative and len(analyses) > 1:
        comparative_analysis = await compare_bank_analyses(list(analyses.values()))
    
    # Формируем итоговый результат
    result = {
        "reports": reports,  # Исходные отчеты
        "analyses": analyses  # Анализы по банкам (теперь это словари, а не строки)
    }
    
    # Добавляем сравнительный анализ, если он есть
    if comparative_analysis:
        result["comparative_analysis"] = comparative_analysis
    
    return result 