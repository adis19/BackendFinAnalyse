from datetime import date, datetime
import re
from typing import List, Optional
import calendar

from app.parsers.base_parser import BaseParser
from app.parsers.models import BankReport, ReportType

class RSKParser(BaseParser):
    """Parser for RSK Bank reports"""
    
    def __init__(self):
        super().__init__(
            bank_name="РСК Банк",
            base_url="https://www.rsk.kg"
        )
        # Основные URL для отчетов (два варианта)
        self.reports_urls = [
            f"{self.base_url}/ru/reports",
            f"{self.base_url}/ru/reports?type=2&for_who=individual&page=1"
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
        Get reports from RSK bank within the specified date range.
        """
        all_reports = []
        print(f"RSK Bank: Searching for reports from {start_date} to {end_date}, type={report_type}")
        
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
        
        # Сначала проверяем прямые URL для конкретных месяцев
        # (это надежнее, чем парсить всю страницу)
        for year, month in target_dates:
            # Форматы дат для поиска
            report_date_obj = date(year, month, 1)
            
            # Получаем последний день месяца (для форматов с датой "за XX.XX.XX")
            day_end = calendar.monthrange(year, month)[1]
            
            # Форматы URL на основе скриншота пользователя и общих шаблонов
            url_patterns = [
                # Формат из скриншота (ФО_за_30.04.25_по_НБКР_для_публикации.PDF)
                f"{self.base_url}/media/reports/ФО_за_30.{month:02d}.{year % 100:02d}_по_НБКР_для_публикации.PDF",
                f"{self.base_url}/media/reports/ФО_за_{day_end:02d}.{month:02d}.{year % 100:02d}_по_НБКР_для_публикации.PDF",
                f"{self.base_url}/media/reports/ФО_за_{month:02d}.{year % 100:02d}_по_НБКР_для_публикации.PDF",
                
                # Другие варианты
                f"{self.base_url}/media/reports/fin_report_{month:02d}_{year}.pdf",
                f"{self.base_url}/media/reports/financial_report_{month:02d}_{year}.pdf",
                f"{self.base_url}/media/reports/report_{month:02d}_{year}.pdf",
                f"{self.base_url}/ru/reports/download/{year}/{month:02d}"
            ]
            
            for url in url_patterns:
                print(f"Checking direct URL: {url}")
                if await self._check_url_exists(url):
                    # Нашли отчет, добавляем его
                    report = BankReport(
                        bank_name=self.bank_name,
                        report_date=report_date_obj,
                        report_url=url,
                        report_title=f"Financial Report for {calendar.month_name[month]} {year}",
                        report_type=ReportType.MONTHLY
                    )
                    all_reports.append(report)
                    print(f"✅ Found report via direct URL: {url}")
        
        # Если не нашли отчеты напрямую, ищем их на страницах отчетов
        if not all_reports:
            for reports_url in self.reports_urls:
                print(f"Fetching reports page: {reports_url}")
                soup = await self._fetch_page(reports_url)
                if not soup:
                    print(f"❌ Failed to load page: {reports_url}")
                    continue
                
                # Ищем все ссылки на отчеты
                # RSK Bank отображает отчеты в формате "Финансовая отчетность на 01.MM.YYYY"
                report_links = soup.find_all('a', href=lambda h: h and h.lower().endswith('.pdf'))
                report_headings = soup.find_all(string=lambda s: s and 'финансовая отчетность на' in s.lower())
                
                print(f"Found {len(report_links)} PDF links and {len(report_headings)} report headings")
                
                # Обрабатываем кнопки "Скачать файл"
                download_buttons = soup.find_all('a', string=lambda s: s and 'скачать файл' in s.lower())
                print(f"Found {len(download_buttons)} download buttons")
                
                # Обрабатываем сначала заголовки с датами
                processed_dates = set()
                
                for heading in report_headings:
                    # Извлекаем дату из заголовка (формат: "Финансовая отчетность на 01.MM.YYYY")
                    date_match = re.search(r'на\s+(\d{2})\.(\d{2})\.(\d{4})', heading.lower())
                    if not date_match:
                        continue
                    
                    try:
                        day = int(date_match.group(1))
                        month = int(date_match.group(2))
                        year = int(date_match.group(3))
                        report_date_obj = date(year, month, 1)  # Используем первое число месяца
                    except (ValueError, IndexError):
                        continue
                    
                    # Проверяем, входит ли дата в запрошенный диапазон
                    if start_date <= report_date_obj <= end_date:
                        # Ищем ближайшую кнопку "Скачать файл" или ссылку на PDF
                        parent = heading.parent
                        if not parent:
                            continue
                        
                        # Ищем кнопку в том же блоке
                        download_link = None
                        
                        # Ищем в родительском блоке
                        if parent:
                            download_link = parent.find('a', string=lambda s: s and 'скачать файл' in s.lower())
                            if not download_link:
                                # Ищем PDF-ссылку
                                download_link = parent.find('a', href=lambda h: h and h.lower().endswith('.pdf'))
                        
                        # Если не нашли, ищем в следующем блоке
                        if not download_link:
                            next_parent = parent.find_next('div') or parent.find_next('section')
                            if next_parent:
                                download_link = next_parent.find('a', string=lambda s: s and 'скачать файл' in s.lower())
                                if not download_link:
                                    download_link = next_parent.find('a', href=lambda h: h and h.lower().endswith('.pdf'))
                        
                        if download_link and 'href' in download_link.attrs:
                            href = download_link['href']
                            report_url = href if href.startswith('http') else f"{self.base_url}{href}"
                            
                            # Формируем отчет
                            report = BankReport(
                                bank_name=self.bank_name,
                                report_date=report_date_obj,
                                report_url=report_url,
                                report_title=f"Financial Report for {calendar.month_name[month]} {year}",
                                report_type=ReportType.MONTHLY
                            )
                            all_reports.append(report)
                            processed_dates.add(f"{month}-{year}")
                            print(f"✅ Found report from heading: {report_url}")
                
                # Если не нашли все отчеты через заголовки, ищем прямые ссылки
                for link in report_links:
                    href = link.get('href', '')
                    if not href:
                        continue
                    
                    # Извлекаем даты из URL или текста ссылки
                    link_text = link.text.strip()
                    combined_text = f"{href} {link_text}".lower()
                    
                    # Различные паттерны для извлечения даты
                    date_patterns = [
                        r'(\d{2})\.(\d{2})\.(\d{4})',  # DD.MM.YYYY
                        r'(\d{2})_(\d{2})_(\d{4})',    # DD_MM_YYYY
                        r'(\d{2})\.(\d{2})\.(\d{2})',  # DD.MM.YY
                        r'_(\d{2})\.(\d{2})\.(\d{2})'  # _DD.MM.YY
                    ]
                    
                    report_date_obj = None
                    
                    for pattern in date_patterns:
                        date_match = re.search(pattern, combined_text)
                        if date_match:
                            try:
                                day = int(date_match.group(1))
                                month = int(date_match.group(2))
                                year_str = date_match.group(3)
                                year = int(year_str) if len(year_str) == 4 else 2000 + int(year_str)
                                report_date_obj = date(year, month, 1)  # Используем первое число месяца
                                break
                            except (ValueError, IndexError):
                                continue
                    
                    # Если не нашли дату по паттернам, ищем в тексте месяц и год
                    if not report_date_obj:
                        # Месяца на русском
                        month_patterns = {
                            "январ": 1, "феврал": 2, "март": 3, "апрел": 4, "май": 5, "июн": 6,
                            "июл": 7, "август": 8, "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12
                        }
                        
                        for month_text, month_num in month_patterns.items():
                            if month_text in combined_text:
                                # Ищем год
                                year_match = re.search(r'20(\d{2})', combined_text)
                                if year_match:
                                    year = 2000 + int(year_match.group(1))
                                    report_date_obj = date(year, month_num, 1)
                                    break
                    
                    # Если нашли дату и она входит в запрошенный диапазон
                    if report_date_obj and start_date <= report_date_obj <= end_date:
                        # Проверяем, что мы еще не обработали эту дату
                        date_key = f"{report_date_obj.month}-{report_date_obj.year}"
                        if date_key in processed_dates:
                            continue
                        
                        report_url = href if href.startswith('http') else f"{self.base_url}{href}"
                        
                        # Формируем отчет
                        report = BankReport(
                            bank_name=self.bank_name,
                            report_date=report_date_obj,
                            report_url=report_url,
                            report_title=f"Financial Report for {calendar.month_name[report_date_obj.month]} {report_date_obj.year}",
                            report_type=ReportType.MONTHLY
                        )
                        all_reports.append(report)
                        processed_dates.add(date_key)
                        print(f"✅ Found report from link: {report_url}")
        
        # Удаляем дубликаты по URL
        unique_reports = {}
        for report in all_reports:
            url = report.report_url
            if url not in unique_reports:
                unique_reports[url] = report
        
        return list(unique_reports.values()) 