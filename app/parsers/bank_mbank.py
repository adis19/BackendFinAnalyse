from datetime import date, datetime
import re
from typing import List, Optional
import calendar
import aiohttp

from app.parsers.base_parser import BaseParser
from app.parsers.models import BankReport, ReportType

class MBankParser(BaseParser):
    """Parser for MBank reports"""
    
    def __init__(self):
        super().__init__(
            bank_name="MBank",
            base_url="https://mbank.kg"
        )
        # Используем оба URL для поиска
        self.reports_base_urls = [
            f"{self.base_url}/ru/reports",
            f"{self.base_url}/reports"
        ]
    
    async def _check_url_exists(self, url: str) -> bool:
        """Check if URL exists by sending HEAD request"""
        session = await self._get_session()
        try:
            async with session.head(url, allow_redirects=True, timeout=10) as response:
                return response.status == 200
        except Exception as e:
            print(f"Error checking URL {url}: {e}")
            return False
    
    async def get_reports(self, start_date: date, end_date: date, report_type: str = "ALL") -> List[BankReport]:
        """
        Get reports from MBank within the specified date range.
        """
        # ВАЖНО: Возвращаем только отчеты, относящиеся к запрошенному диапазону дат
        all_reports = []
        print(f"MBank: Searching for reports from {start_date} to {end_date}, type={report_type}")
        
        # Генерируем список конкретных месяцев для поиска
        target_dates = []
        current_date = date(start_date.year, start_date.month, 1)
        while current_date <= end_date:
            target_dates.append((current_date.year, current_date.month))
            # Move to next month
            if current_date.month == 12:
                current_date = date(current_date.year + 1, 1, 1)
            else:
                current_date = date(current_date.year, current_date.month + 1, 1)
        
        print(f"Target dates for search: {target_dates}")
        
        # Группируем даты по годам
        dates_by_year = {}
        for year, month in target_dates:
            if year not in dates_by_year:
                dates_by_year[year] = []
            dates_by_year[year].append(month)
        
        # Месяцы на русском (важно для поиска на сайте)
        month_names_ru = {
            1: ["январь", "янв"],
            2: ["февраль", "фев"],
            3: ["март", "мар"],
            4: ["апрель", "апр"],
            5: ["май", "май"],
            6: ["июнь", "июн"],
            7: ["июль", "июл"],
            8: ["август", "авг"],
            9: ["сентябрь", "сен"],
            10: ["октябрь", "окт"],
            11: ["ноябрь", "ноя"],
            12: ["декабрь", "дек"]
        }
        
        # English month names (for report titles)
        month_names_en = {
            1: "January", 2: "February", 3: "March", 4: "April",
            5: "May", 6: "June", 7: "July", 8: "August",
            9: "September", 10: "October", 11: "November", 12: "December"
        }
        
        # ПРЯМОЙ ПОИСК: Попробуем прямые URL для каждого месяца, который нужно найти
        # Это наиболее надежный способ для конкретных месяцев
        for year, month in target_dates:
            print(f"Directly searching for year={year}, month={month}")
            month_name_en = month_names_en[month]
            month_name_ru = month_names_ru[month][0]
            
            # Попробуем распространенные шаблоны URL для МБанка
            url_patterns = [
                # Форматы видимые в скриншоте пользователя
                f"{self.base_url}/media/about/finance/{month:02d}_{year}.pdf", 
                f"{self.base_url}/media/about/finance/report_{month:02d}_{year}.pdf",
                f"{self.base_url}/media/about/finance/ФО_{month:02d}кв_{year}.pdf",
                
                # Варианты с названиями месяцев
                f"{self.base_url}/media/about/finance/{month_name_en.lower()}_{year}.pdf",
                f"{self.base_url}/media/about/finance/{month_name_ru.lower()}_{year}.pdf",
                
                # Стандартные форматы
                f"{self.base_url}/reports/{year}/{month:02d}.pdf",
                f"{self.base_url}/reports/{month:02d}_{year}.pdf",
                f"{self.base_url}/uploads/reports/{year}/{month:02d}.pdf",
                f"{self.base_url}/ru/reports/{year}/{month:02d}.pdf",
                
                # Дополнительные форматы
                f"{self.base_url}/ru/about/finance/report_{month:02d}_{year}.pdf",
                f"{self.base_url}/about/finance/report_{month:02d}_{year}.pdf",
                f"{self.base_url}/media/reports/{year}/{month:02d}.pdf",
                f"{self.base_url}/media/reports/{month:02d}_{year}.pdf"
            ]
            
            for url in url_patterns:
                print(f"Checking direct URL: {url}")
                if await self._check_url_exists(url):
                    report_date = date(year, month, 1)
                    report = BankReport(
                        bank_name=self.bank_name,
                        report_date=report_date,
                        report_url=url,
                        report_title=f"Financial Report for {month_name_en} {year}",
                        report_type=ReportType.MONTHLY
                    )
                    all_reports.append(report)
                    print(f"✅ Found report via direct URL: {url}")
        
        # Если не нашли отчеты прямым путем, ищем через веб-страницы
        if len(all_reports) == 0:
            for year, target_months in dates_by_year.items():
                for base_url in self.reports_base_urls:
                    # Пробуем загрузить страницу с отчетами за год
                    year_url = f"{base_url}?year={year}"
                    print(f"Loading page: {year_url}")
                    
                    year_soup = await self._fetch_page(year_url)
                    if not year_soup:
                        print(f"❌ Failed to load page: {year_url}")
                        continue
                    
                    # Ищем все PDF-ссылки на странице
                    pdf_links = year_soup.find_all('a', href=lambda h: h and h.lower().endswith('.pdf'))
                    print(f"Found {len(pdf_links)} PDF links on the page")
                    
                    # Проверяем каждую ссылку
                    for link in pdf_links:
                        href = link.get('href', '')
                        link_text = link.text.strip().lower()
                        
                        # Пропускаем пустые или неправильные ссылки
                        if not href or not href.lower().endswith('.pdf'):
                            continue
                        
                        # Полный URL для отчета
                        report_url = href if href.startswith('http') else f"{self.base_url}{href}"
                        
                        # Определяем дату отчета (месяц и год)
                        # Сначала проверяем текст ссылки и URL на наличие месяца
                        detected_month = None
                        detected_year = year  # По умолчанию используем текущий год
                        
                        # Проверяем наличие года в ссылке
                        year_match = re.search(r'20(\d{2})', href + ' ' + link_text)
                        if year_match:
                            detected_year = 2000 + int(year_match.group(1))
                        
                        # Ищем месяц в тексте ссылки и URL
                        combined_text = (href + ' ' + link_text).lower()
                        for month_num, month_variants in month_names_ru.items():
                            for month_variant in month_variants:
                                if month_variant.lower() in combined_text:
                                    detected_month = month_num
                                    break
                            if detected_month:
                                break
                                
                        # Ищем месяц по английским названиям
                        if not detected_month:
                            for month_num, month_name in month_names_en.items():
                                if month_name.lower() in combined_text:
                                    detected_month = month_num
                                    break
                        
                        # Ищем месяц по числовому формату (например, "04_2024" или "2024_04")
                        if not detected_month:
                            month_pattern = re.search(r'(?:^|[_\-/])(\d{1,2})(?:[_\-/])|(\d{1,2})(?:[_\-/])(?:20\d{2})', combined_text)
                            if month_pattern:
                                month_num = int(month_pattern.group(1) or month_pattern.group(2))
                                if 1 <= month_num <= 12:
                                    detected_month = month_num
                        
                        # Если нашли и месяц, и год, и они соответствуют запрошенному диапазону
                        if detected_month and detected_month in target_months and detected_year == year:
                            # Создаем дату отчета
                            report_date = date(detected_year, detected_month, 1)
                            
                            # Проверяем, что дата входит в запрошенный диапазон
                            if start_date <= report_date <= end_date:
                                # Создаем отчет
                                month_name_en = month_names_en[detected_month]
                                report = BankReport(
                                    bank_name=self.bank_name,
                                    report_date=report_date,
                                    report_url=report_url,
                                    report_title=f"Financial Report for {month_name_en} {detected_year}",
                                    report_type=ReportType.MONTHLY
                                )
                                all_reports.append(report)
                                print(f"✅ Found report from page: {report_url} for {month_name_en} {detected_year}")
        
        # Удаляем дубликаты (по URL)
        unique_reports = {}
        for report in all_reports:
            # Проверяем, что дата отчета входит в запрошенный диапазон
            if start_date <= report.report_date <= end_date:
                url = report.report_url
                if url not in unique_reports:
                    unique_reports[url] = report
        
        filtered_reports = list(unique_reports.values())
        print(f"Found total of {len(filtered_reports)} unique reports in requested date range")
        
        return filtered_reports 