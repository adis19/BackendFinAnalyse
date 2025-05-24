import google.generativeai as genai
from datetime import date
import json
import re
from typing import Dict, Any, List, Optional
from .pdf_downloader import download_pdf, cleanup_pdf
import os
import time
import tempfile

# Конфигурация Google Gemini API
GOOGLE_API_KEY = 'AIzaSyDvsUFB83k9nq5vOdDPEb4-8iOfAtfvWu0'  # Важно: этот ключ будет заменен позже

# Шаблон промпта для анализа финансовой отчетности
ANALYSIS_PROMPT_TEMPLATE = """
ТЫ – АВТОМАТИЗИРОВАННЫЙ ФИНАНСОВЫЙ АНАЛИТИК для мобильного приложения. Твоя задача – извлечь ключевые финансовые данные и рассчитать показатели банка из приложенного документа (PDF или изображения финансового отчета).
{LANGUAGE_INSTRUCTIONS}
Представь результат в формате JSON.

ВАЖНО: ИНСТРУКЦИИ ПО ЧТЕНИЮ ИСХОДНОГО ОТЧЕТА:
В отчете есть три основных раздела:
"ОТЧЕТ О ФИНАНСОВОМ ПОЛОЖЕНИИ" (баланс)
"ОТЧЕТ О СОВОКУПНОМ ДОХОДЕ" (прибыли и убытки)
"СВЕДЕНИЯ О СОБЛЮДЕНИИ ЭКОНОМИЧЕСКИХ НОРМАТИВОВ"

ОСОБОЕ ВНИМАНИЕ К РАЗДЕЛУ "СВЕДЕНИЯ О СОБЛЮДЕНИИ ЭКОНОМИЧЕСКИХ НОРМАТИВОВ":
Коэффициент достаточности (адекватности) суммарного капитала (К2.1) -> это CAR
Коэффициент достаточности (адекватности) капитала Первого уровня (К2.2) -> это Tier1
Леверидж (К2.4) -> это leverage
Норматив (показатель) ликвидности банка (К3.1) -> это LCR
Дополнительный запас капитала банка (индекс "буфер капитала") -> это capital_buffer

РАСЧЕТ ПОКАЗАТЕЛЕЙ:
Коэффициенты из нормативов - брать из раздела "СВЕДЕНИЯ О СОБЛЮДЕНИИ ЭКОНОМИЧЕСКИХ НОРМАТИВОВ" (если есть):
CAR (K2.1)
Tier1 (K2.2)
Leverage (K2.4)
LCR (K3.1)
Capital Buffer

Расчетные показатели (рассчитывать на основе данных баланса и отчета о прибылях и убытках):
a) ROA (Рентабельность активов):
Формула: (Чистая прибыль за период * 12/кол-во месяцев) / ((Активы на конец + Активы на начало периода) / 2) * 100%
Пример для квартального отчета: (Чистая прибыль * 4) / Средние активы * 100%
Пример для месячного отчета: (Чистая прибыль * 12) / Средние активы * 100%
Брать активы текущие и за аналогичный период прошлого года
b) ROE (Рентабельность капитала):
Формула: (Чистая прибыль за период * 12/кол-во месяцев) / ((Капитал на конец + Капитал на начало периода) / 2) * 100%
Пример для квартального отчета: (Чистая прибыль * 4) / Средний капитал * 100%
Пример для месячного отчета: (Чистая прибыль * 12) / Средний капитал * 100%
Брать капитал текущий и за аналогичный период прошлого года
c) CIR (Cost to Income Ratio):
Формула: Операционные расходы / (Чистый процентный доход + Чистый комиссионный доход + Прочие операционные доходы) * 100%
Операционные расходы берутся из отчета о прибылях и убытках
В знаменателе сумма всех операционных доходов до создания резервов
d) Loan to Deposit:
Формула: Кредиты, выданные клиентам (за вычетом резервов) / Текущие счета и депозиты клиентов * 100%
Все данные берутся из баланса
Использовать чистую сумму кредитов (за вычетом резервов)

ВАЖНО ПРИ РАСЧЕТЕ:
Все расчеты должны производиться на основе фактических данных из отчетов
Если какие-то данные отсутствуют - показатель не рассчитывается (null)
Для годовых коэффициентов используется соответствующая аннуализация:
Для квартальных данных умножать на 4
Для месячных данных умножать на 12
Всегда проверять наличие отрицательных значений и их влияние на расчет
Округлять результаты до 2 знаков после запятой

ВАЖНО ДЛЯ РАЗДЕЛА SUMMARY:
Strengths (сильные стороны) - ОБЯЗАТЕЛЬНО указать минимум 2 пункта:
Рост активов (если есть)
Рост прибыли (если есть)
Улучшение нормативов (если есть)
Рост кредитного портфеля (если есть)
Attention points (области для внимания) - ОБЯЗАТЕЛЬНО указать минимум 1 пункт:
Снижение прибыли (если есть)
Снижение активов (если есть)
Ухудшение нормативов (если есть)
Рост резервов на потери (если есть)
Conclusion (итог) - ОБЯЗАТЕЛЬНО сформулировать подробный вывод, включающий:
Общая динамика:
Изменение активов (рост/снижение в %)
Изменение кредитного портфеля (рост/снижение в %)
Изменение депозитной базы (рост/снижение в %)
Динамика прибыли (рост/снижение в %)
Качество активов:
Уровень NPL (если доступно)
Уровень резервирования
Достаточность капитала:
Текущие значения всех коэффициентов
Сравнение с нормативными значениями
Запас прочности по каждому нормативу
Ликвидность:
Текущие показатели ликвидности
Соотношение кредитов и депозитов
Эффективность:
ROA и ROE (если рассчитаны)
CIR (если рассчитан)
Общий вывод:
Сильные стороны банка
Области для мониторинга
Прогноз развития

ВАЖНЫЕ ПРАВИЛА:
Все числовые значения должны быть числами, не строками
Используй null ТОЛЬКО если данных действительно нет или их невозможно рассчитать
Все проценты указывай как числа (например: 20.5, а не "20.5%")
Всегда проверяй расчеты дважды
Используй точные названия из отчета
Указывай единицы измерения (обычно "тыс. сом")
НИКОГДА не оставляй пустыми разделы summary

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
"Рост общих активов на X% по сравнению с концом предыдущего года (с Y до Z тыс. сом). X, Y, Z - ЗАМЕНИТЬ РЕАЛЬНЫМИ ДАННЫМИ.",
"Увеличение чистой прибыли на A% по сравнению с аналогичным периодом прошлого года. A - ЗАМЕНИТЬ РЕАЛЬНЫМИ ДАННЫМИ."
],
"attention_points": [
"Снижение показателя X на Y%. X, Y - ЗАМЕНИТЬ РЕАЛЬНЫМИ ДАННЫМИ.",
"Ухудшение норматива Z до X%. Z, X - ЗАМЕНИТЬ РЕАЛЬНЫМИ ДАННЫМИ."
],
"conclusion": "Банк демонстрирует [положительную/стабильную/неустойчивую] динамику. Все обязательные нормативы [соблюдаются/есть отклонения]. Общее финансовое состояние [устойчивое/требует внимания]. ЗАПОЛНИ ЭТОТ РАЗДЕЛ ПОДРОБНЫМ АНАЛИЗОМ НА ОСНОВЕ ДАННЫХ, ВКЛЮЧАЯ ДИНАМИКУ КЛЮЧЕВЫХ ПОКАЗАТЕЛЕЙ."
}
}
"""

# Шаблон промпта для сравнительного анализа нескольких банков
COMPARATIVE_ANALYSIS_PROMPT_TEMPLATE = """
Ты получил результаты анализа финансовой отчетности нескольких банков. Теперь твоя задача - сравнить эти банки между собой и предоставить сравнительный анализ в формате JSON.
{LANGUAGE_INSTRUCTIONS}
Используй только те данные, которые есть у ВСЕХ анализируемых банков. Фокусируйся на сравнении ключевых показателей.

Результирующий JSON должен иметь следующую структуру:
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
          "key_factors": ["Фактор 1. ЗАМЕНИТЬ РЕАЛЬНЫМИ ДАННЫМИ.", "Фактор 2. ЗАМЕНИТЬ РЕАЛЬНЫМИ ДАННЫМИ."]
        },
        "most_efficient": {
          "bank": "Название",
          "cir": 45.2,
          "key_factors": ["Фактор 1. ЗАМЕНИТЬ РЕАЛЬНЫМИ ДАННЫМИ.", "Фактор 2. ЗАМЕНИТЬ РЕАЛЬНЫМИ ДАННЫМИ."]
        }
      },
      "stability_comparison": {
        "capital_adequacy": {
          "strongest": "Название банка",
          "key_metrics": ["CAR: 20.2%", "Tier1: 18.5%"],
          "analysis": "Детальный анализ. ЗАПОЛНИТЬ НА ОСНОВЕ КОНКРЕТНЫХ ДАННЫХ."
        },
        "liquidity": {
          "strongest": "Название банка",
          "key_metrics": ["LCR: 85.5%", "NSFR: 120.5%"],
          "analysis": "Детальный анализ. ЗАПОЛНИТЬ НА ОСНОВЕ КОНКРЕТНЫХ ДАННЫХ."
        }
      },
      "growth_dynamics": {
        "fastest_growing": {
          "bank": "Название",
          "metrics": ["Активы: +15.2%", "Кредиты: +18.5%"],
          "sustainability_analysis": "Анализ устойчивости роста. ЗАПОЛНИТЬ НА ОСНОВЕ КОНКРЕТНЫХ ДАННЫХ."
        },
        "most_stable": {
          "bank": "Название",
          "metrics": ["Низкая волатильность показателей", "Стабильная база фондирования"],
          "analysis": "Почему этот банк считается наиболее стабильным. ЗАПОЛНИТЬ НА ОСНОВЕ КОНКРЕТНЫХ ДАННЫХ."
        }
      },
      "detailed_conclusion": {
        "market_overview": "Общий анализ состояния сравниваемых банков. ЗАПОЛНИТЬ НА ОСНОВЕ КОНКРЕТНЫХ ДАННЫХ.",
        "key_trends": [
          "Тренд 1 и его влияние на банки. СФОРМУЛИРОВАТЬ И ОПИСАТЬ КОНКРЕТНЫЙ ТРЕНД.",
          "Тренд 2 и его влияние на банки. СФОРМУЛИРОВАТЬ И ОПИСАТЬ КОНКРЕТНЫЙ ТРЕНД."
        ],
        "recommendations": [
          "Рекомендация 1 с обоснованием. СФОРМУЛИРОВАТЬ КОНКРЕТНУЮ РЕКОМЕНДАЦИЮ.",
          "Рекомендация 2 с обоснованием. СФОРМУЛИРОВАТЬ КОНКРЕТНУЮ РЕКОМЕНДАЦИЮ."
        ],
        "risk_factors": [
          "Риск-фактор 1 и его потенциальное влияние. СФОРМУЛИРОВАТЬ И ОПИСАТЬ КОНКРЕТНЫЙ РИСК.",
          "Риск-фактор 2 и его потенциальное влияние. СФОРМУЛИРОВАТЬ И ОПИСАТЬ КОНКРЕТНЫЙ РИСК."
        ],
        "outlook": "Прогноз развития ситуации на ближайшую перспективу. ЗАПОЛНИТЬ НА ОСНОВЕ АНАЛИЗА."
      }
    }
  }
}

ВАЖНО!
Используй только те показатели, которые доступны для всех сравниваемых банков.
Если каких-то данных нет для сравнения, опусти соответствующий раздел.
Всегда используй числа, а не строки для числовых значений.
Всегда указывай единицы измерения для финансовых показателей.
Предоставь обоснованные выводы в разделе "conclusions".
Ранжируй банки от лучшего к худшему по каждому показателю.
"""


def _generate_language_instructions(lang: str) -> str:
    if lang == "ky":
        lang_name_locative = "КЫРГЫЗ ТИЛИНДЕ"
        lang_name_nominative = "Кыргыз тили"
        example_unit = "миң сом"
        example_assets = "Активдер"
        instruction_text = f"""
ИНСТРУКЦИЯЛАР ЧЫГАРУУ ТИЛИ БОЮНЧА:
ЧЫГАРУУ ТИЛИ: {lang_name_nominative.upper()} ({lang}).
СЕН ТҮЗГӨН жыйынтыктоочу JSON-жообундагы БАРДЫК ТЕКСТ {lang_name_locative} БОЛУШУ КЕРЕК.
Буга төмөнкүлөр кирет, бирок алар менен эле чектелбейт:
- "name" ачкычтары үчүн бардык маанилер (мисалы, баланстын статьяларынын аталыштары, кирешелер жана чыгашалар жөнүндө отчет).
- "summary" бөлүмүндөгү ("strengths", "attention_points", "conclusion") жана салыштырма анализдин "conclusions" бөлүмүндөгү ("market_overview", "key_trends", "recommendations", "risk_factors", "outlook" ж.б.) БАРДЫК тексттик мазмун.
  МААНИЛҮҮ: Үлгүдө көрсөтүлгөн "X%", "Y", "Z", "A%", "Тренд 1", "Рекомендация 1", "Фактор 1" сыяктуу ОРУН ТОЛТУРГУЧТАРДЫ (плейсхолдерлерди) документтен алынган ЧЫНЫГЫ, КОНКРЕТТҮҮ МААЛЫМАТТАР МЕНЕН АЛМАШТЫР. "ЗАПОЛНИ ЭТОТ РАЗДЕЛ..." же "СФОРМУЛИРОВАТЬ..." деген сыяктуу нускамалар да толук, маалыматка негизделген текст менен алмаштырылышы керек.
  Мисалы, "Рост общих активов на X% ..." дегендин ордуна, эгер активдер 5.26%га өскөн болсо: "Жалпы активдердин 5.26%га өсүшү (950000 миң сомдон 1000000 миң сомго чейин)." деп жаз.
  Пайыздык маанилерди САН түрүндө берип, '%га', '%дан', '%ын', '%түк' сыяктуу контекстке ылайыктуу кыргызча мүчөлөрдү пайыз белгисинен (%) КИЙИН кош. МИСАЛЫ: 5.26%га, 10%дан, 12%дык. 'X%га' ДЕП ЖАЗБА.
  "Тренд 1..." дегендин ордуна, аныкталган чыныгы тенденцияны жаз: "Банк секторунда санариптештирүүнүн күчөшү жана анын чакан банктарга тийгизген таасири."
- Өлчөө бирдиктери (мисалы, "unit" талаасы "{example_unit}" болушу керек).
- JSON структурасынын ичиндеги башка бардык сүрөттөмө тексттик саптар.
- "bank_name" талаасы да {lang_name_locative} болушу керек.

МААНИЛҮҮ: ЭГЕРДЕ БАШТАПКЫ ДОКУМЕНТТЕГИ (PDF) МААЛЫМАТ БАШКА ТИЛДЕ БЕРИЛСЕ (мисалы, орус тилинде), СЕН АНЫ JSONго КИРГИЗҮҮДӨН МУРУН {lang_name_locative} КОТОРУУГА МИЛДЕТТҮҮСҮҢ. Бул PDFтен алынган бардык цитаталарга же маалыматтарга тиешелүү.

Берилген JSON структурасынын үлгүсү талап кылынган форматты көрсөтөт. Бирок, ошол структуранын ичиндеги БАРДЫК тексттик маалыматтар, анын ичинде орун толтургучтардын ордуна коюлуучу маалыматтар да, тандалган {lang_name_locative} жазылышы керек.
Мисалы, кыргыз тили үчүн "summary":
  "summary": {{
    "strengths": ["Жалпы активдердин 5.26%га өсүшү (950000 миң сомдон 1000000 миң сомго чейин).", "Таза пайданын 7.14%га көбөйүшү (14000 миң сомдон 15000 миң сомго чейин)."],
    "attention_points": ["Кредиттик портфелдин 2.5%га азайышы (200000 миң сомдон 195000 миң сомго чейин)."],
    "conclusion": "Банк туруктуу өнүгүү динамикасын көрсөтүүдө. Негизги финансылык көрсөткүчтөр жакшырды, мисалы, активдердин өсүшү 5.26%га жетип, пайданын көбөйүшү 7.14%ды түздү. Капиталдын жетиштүүлүгү жана ликвиддүүлүк нормативдери сакталган. Көңүл бура турган жагдайлар катары операциондук чыгашалардын 3%га өсүшү белгиленсе болот."
  }}
Мисалы, кыргыз тили үчүн "detailed_conclusion" ичиндеги "key_trends":
  "key_trends": [
    "Санариптик банкинг кызматтарына суроо-талаптын өсүшү жана бул банктардын IT-инфраструктурасына инвестиция жасоо зарылдыгы.",
    "Кыргызстандагы экономикалык кырдаалдын кредиттик тобокелдиктерге тийгизген таасири жана провизиялардын 5%га көбөйүшү ыктымалдыгы."
  ]
"""
    else:  # Default to Russian (ru)
        lang_name_locative = "РУССКОМ ЯЗЫКЕ"
        lang_name_nominative = "Русский язык"
        example_unit = "тыс. сом"
        example_assets = "Активы"
        instruction_text = f"""
ИНСТРУКЦИИ ПО ЯЗЫКУ ВЫВОДА:
ЯЗЫК ВЫВОДА: {lang_name_nominative.upper()} ({lang}).
ВЕСЬ ТЕКСТ в итоговом JSON-ответе, который ты генерируешь, ДОЛЖЕН БЫТЬ НА {lang_name_locative}.
Это включает, но не ограничивается:
- Все значения для ключей "name" (например, названия статей баланса, отчета о прибылях и убытках).
- Весь текстовый контент в разделе "summary" ("strengths", "attention_points", "conclusion") и в разделе "conclusions" сравнительного анализа ("market_overview", "key_trends", "recommendations", "risk_factors", "outlook" и т.д.).
  ВАЖНО: Плейсхолдеры в примерах (такие как X, Y, Z, A, "Тренд 1", "Рекомендация 1", "Фактор 1") ДОЛЖНЫ БЫТЬ ЗАМЕНЕНЫ КОНКРЕТНЫМИ ДАННЫМИ из документа или анализа. Указания типа "ЗАПОЛНИ ЭТОТ РАЗДЕЛ..." или "СФОРМУЛИРОВАТЬ..." также должны быть заменены развернутым текстом на основе фактических данных.
- Единицы измерения (например, поле "unit" должно быть "{example_unit}").
- Любые другие описательные текстовые строки внутри JSON структуры.
- Поле "bank_name" также должно быть на {lang_name_locative}.

ВАЖНО: ЕСЛИ ИНФОРМАЦИЯ В ИСХОДНОМ ДОКУМЕНТЕ (PDF) ПРЕДОСТАВЛЕНА НА ДРУГОМ ЯЗЫКЕ (например, на кыргызском), ТЫ ОБЯЗАН ПЕРЕВЕСТИ ЕЕ НА {lang_name_locative} ПЕРЕД ВКЛЮЧЕНИЕМ В JSON. Это касается всех цитат или данных, извлеченных из PDF.

Приведенный пример JSON структуры показывает требуемый формат. Однако, ВСЕ текстовые данные внутри этой структуры должны быть на выбранном {lang_name_locative}.
Пример для русского языка "summary":
  "summary": {{
    "strengths": ["Рост общих активов на 5.26% (с 950000 до 1000000 тыс. сом).", "Увеличение чистой прибыли на 7.14% (с 14000 до 15000 тыс. сом)."],
    "attention_points": ["Снижение кредитного портфеля на 2.5% (с 200000 до 195000 тыс. сом)."],
    "conclusion": "Банк демонстрирует стабильную динамику развития. Ключевые финансовые показатели улучшились, включая рост активов на 5.26% и увеличение прибыли на 7.14%. Нормативы достаточности капитала и ликвидности соблюдаются. В качестве областей для внимания можно отметить рост операционных расходов на 3%."
  }}
Пример для русского языка "detailed_conclusion" внутри "key_trends":
  "key_trends": [
    "Рост спроса на цифровые банковские услуги и необходимость инвестиций в IT-инфраструктуру со стороны банков.",
    "Влияние экономической ситуации в Кыргызстане на кредитные риски и возможное увеличение провизий на 5%."
  ]
"""
    return instruction_text


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


async def analyze_report_from_url(report_url: str, bank_name: str, lang: str = "ru", is_json_output: bool = True) -> \
Dict[str, Any]:
    """
    Анализирует отчет по URL с помощью Gemini
    Args:
        report_url: URL отчета для анализа
        bank_name: Название банка для логирования
        lang: Язык для анализа ('ru' или 'ky')
        is_json_output: Флаг для возврата результата в формате JSON

    Returns:
        Словарь с результатами анализа
    """
    try:
        init_gemini_api()

        pdf_path = download_pdf(report_url)
        if not pdf_path:
            return {"error": f"Не удалось загрузить PDF файл по URL: {report_url}"}

        try:
            print(f"Загрузка файла: {pdf_path}...")
            uploaded_file = genai.upload_file(path=pdf_path,
                                              display_name=os.path.basename(pdf_path))
            print(f"Файл загружен: {uploaded_file.name} (URI: {uploaded_file.uri})")

            model = genai.GenerativeModel('gemini-2.0-flash')  # Не меняем модель

            language_instructions_str = _generate_language_instructions(lang)
            current_analysis_prompt = ANALYSIS_PROMPT_TEMPLATE.replace("{LANGUAGE_INSTRUCTIONS}",
                                                                       language_instructions_str)

            prompt_text = current_analysis_prompt
            if not is_json_output:
                prompt_text = prompt_text.replace("формате JSON", "формате MARKDOWN")

            request_content = [
                uploaded_file,
                prompt_text
            ]

            print(f'Отправка запроса в Gemini API банк "{bank_name}", язык: {lang}')
            response = model.generate_content(request_content)

            if is_json_output:
                result = extract_json_from_response(response.text)
                print(f"Получен ответ от Gemini API для банка {bank_name}")
            else:
                result = {"markdown": response.text}
                print(f"Получен markdown-ответ от Gemini API для банка {bank_name}")

            return result

        finally:
            cleanup_pdf(pdf_path)

    except Exception as e:
        print(f"Ошибка при анализе отчета для банка {bank_name}: {str(e)}")
        return {"error": f"Произошла ошибка: {str(e)}"}


async def analyze_report_from_bytes(pdf_bytes: bytes, bank_name: str = "Unknown Bank", lang: str = "ru",
                                    is_json_output: bool = True) -> Dict[str, Any]:
    """
    Анализирует PDF отчет из байтов с помощью Gemini
    Args:
        pdf_bytes: Байты PDF файла
        bank_name: Название банка для логирования
        lang: Язык для анализа ('ru' или 'ky')
        is_json_output: Флаг для возврата результата в формате JSON

    Returns:
        Словарь с результатами анализа
    """
    try:
        init_gemini_api()

        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"report_{os.urandom(8).hex()}.pdf")

        try:
            with open(temp_path, 'wb') as f:
                f.write(pdf_bytes)

            print(f"Временный файл сохранен: {temp_path}...")

            model = genai.GenerativeModel('gemini-2.0-flash')  # Не меняем модель

            language_instructions_str = _generate_language_instructions(lang)
            current_analysis_prompt = ANALYSIS_PROMPT_TEMPLATE.replace("{LANGUAGE_INSTRUCTIONS}",
                                                                       language_instructions_str)

            prompt_text = current_analysis_prompt
            if not is_json_output:
                prompt_text = prompt_text.replace("формате JSON", "формате MARKDOWN")

            with open(temp_path, 'rb') as f:
                file_data = f.read()

            request_content = [
                {"mime_type": "application/pdf", "data": file_data},
                prompt_text
            ]

            print(f'Отправка запроса в Gemini API банк "{bank_name}", язык: {lang}')
            response = model.generate_content(request_content)

            if is_json_output:
                result = extract_json_from_response(response.text)
                print(f"Получен ответ от Gemini API для банка {bank_name}")
            else:
                result = {"markdown": response.text}
                print(f"Получен markdown-ответ от Gemini API для банка {bank_name}")

            return result

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                print(f"Удален временный файл {temp_path}")

    except Exception as e:
        print(f"Ошибка при анализе отчета для банка {bank_name}: {str(e)}")
        return {"error": f"Произошла ошибка: {str(e)}"}


async def compare_bank_analyses(bank_analyses: List[Dict[str, Any]], lang: str = "ru") -> Dict[str, Any]:
    """
    Сравнивает анализы нескольких банков
    Args:
        bank_analyses: Список словарей с анализами банков
        lang: Язык для сравнительного анализа ('ru' или 'ky')

    Returns:
        Словарь со сравнительным анализом
    """
    try:
        init_gemini_api()

        model = genai.GenerativeModel('gemini-2.0-flash')  # Не меняем модель

        language_instructions_str = _generate_language_instructions(lang)
        current_comparative_prompt = COMPARATIVE_ANALYSIS_PROMPT_TEMPLATE.replace("{LANGUAGE_INSTRUCTIONS}",
                                                                                  language_instructions_str)

        full_prompt = f"""
        {current_comparative_prompt}

        Вот анализы банков, которые нужно сравнить (предполагается, что они уже на целевом языке, но модель должна генерировать сравнение на {lang}):

        {json.dumps(bank_analyses, ensure_ascii=False, indent=2)}
        """

        print(f"Отправка запроса на сравнительный анализ, язык: {lang}")
        response = model.generate_content(full_prompt)

        return extract_json_from_response(response.text)

    except Exception as e:
        print(f"Ошибка при сравнении банков: {str(e)}")
        return {"error": f"Произошла ошибка при сравнении банков: {str(e)}"}


async def analyze_bank_reports(reports: List[Dict[str, Any]], lang: str = "ru", is_comparative: bool = False) -> Dict[
    str, Any]:
    """
    Анализирует отчеты банков, фильтрует нерабочие и создает структурированный ответ
    Args:
        reports: Список отчетов банков
        lang: Язык для анализа ('ru' или 'ky')
        is_comparative: Флаг необходимости сравнительного анализа

    Returns:
        Структурированный результат анализа
    """
    start_time = time.time()
    print(f"\nНачало анализа отчетов ({lang}): {time.strftime('%H:%M:%S')}")

    bank_to_reports = {}
    for report in reports:
        bank_name = report.get("bank_name")
        if bank_name not in bank_to_reports:
            bank_to_reports[bank_name] = []
        bank_to_reports[bank_name].append(report)

    analyses = {}
    for bank_name, bank_reports in bank_to_reports.items():
        bank_start_time = time.time()
        print(f"\nНачало обработки банка {bank_name} ({lang}): {time.strftime('%H:%M:%S')}")

        sorted_reports = sorted(
            bank_reports,
            key=lambda r: r.get("report_date", "1900-01-01"),
            reverse=True
        )

        for report in sorted_reports:
            report_url = report.get("report_url")
            if not report_url:
                print(f"Пропуск отчета без URL для банка {bank_name}")
                continue

            try:
                print(f"Анализ отчета {report_url} для банка {bank_name} (язык: {lang})")
                analysis_result = await analyze_report_from_url(report_url, bank_name, lang=lang, is_json_output=True)

                if "error" not in analysis_result:
                    analyses[bank_name] = analysis_result
                    bank_end_time = time.time()
                    bank_duration = bank_end_time - bank_start_time
                    print(f"Успешный анализ для банка {bank_name}. Время обработки: {bank_duration:.2f} сек.")
                    break
                else:
                    print(f"Ошибка при анализе отчета для банка {bank_name}: {analysis_result['error']}")
            except Exception as e:
                print(f"Исключение при анализе отчета для банка {bank_name}: {str(e)}")
                continue

    comparative_analysis = None
    if is_comparative and len(analyses) > 1:
        compare_start_time = time.time()
        print(f"\nЗапуск сравнительного анализа для банков (язык: {lang})")
        comparative_analysis = await compare_bank_analyses(list(analyses.values()), lang=lang)
        compare_duration = time.time() - compare_start_time
        print(f"Завершен сравнительный анализ. Время: {compare_duration:.2f} сек.")

    result = {
        "reports": reports,
        "analyses": analyses,
        "execution_time": time.time() - start_time
    }

    if comparative_analysis:
        result["comparative_analysis"] = comparative_analysis

    end_time = time.time()
    total_duration = end_time - start_time
    print(f"\nЗавершение анализа ({lang}): {time.strftime('%H:%M:%S')}")
    print(f"Общее время выполнения: {total_duration:.2f} секунд")

    return result