from datetime import date, datetime, timedelta
import re
from typing import List, Optional
import calendar
import aiohttp

from app.parsers.base_parser import BaseParser
from app.parsers.models import BankReport, ReportType

class OptimaParser(BaseParser):
    """Parser for Optima Bank reports"""
    
    def __init__(self):
        super().__init__(
            bank_name="Optima Bank",
            base_url="https://www.optimabank.kg"
        )
        self.reports_base_url = f"{self.base_url}/images/files/financial-reports"
    
    async def _check_url_exists(self, url: str) -> bool:
        """Check if URL exists by sending HEAD request"""
        session = await self._get_session()
        try:
            async with session.head(url, allow_redirects=True) as response:
                return response.status == 200
        except Exception as e:
            print(f"Error checking URL {url}: {e}")
            return False
    
    async def get_reports(self, start_date: date, end_date: date, report_type: str = "ALL") -> List[BankReport]:
        """
        Get reports from Optima Bank within the specified date range by directly constructing URLs
        """
        all_reports = []
        print(f"Optima Bank: Searching for reports from {start_date} to {end_date}, type={report_type}")
        
        # Обработка случая, когда end_date == start_date (когда end_date не указан)
        # Если даты равны, используем конец текущего месяца как end_date
        adjusted_end_date = end_date
        if start_date == end_date:
            # Если конечная дата равна начальной, ищем отчеты только за этот месяц
            current_year, current_month = start_date.year, start_date.month
            
            # Проверяем URL для этого конкретного месяца
            short_year = current_year % 100
            report_found = False
            
            for day in [1, 15]:  # Пробуем разные дни, отчеты часто публикуются 1-го или 15-го
                if report_type == "ALL" or report_type == "monthly":
                    file_name = f"fo-{day:02d}-{current_month:02d}-{short_year:02d}-rus.pdf"
                    report_url = f"{self.reports_base_url}/{current_year}/{file_name}"
                    
                    # Проверяем, существует ли файл
                    if await self._check_url_exists(report_url):
                        month_names = ["", "January", "February", "March", "April", "May", "June", 
                                    "July", "August", "September", "October", "November", "December"]
                        
                        report_date = date(current_year, current_month, 1)
                        report_title = f"Financial Report for {month_names[current_month]} {current_year} (published {day:02d}.{current_month:02d}.{current_year})"
                        
                        report = BankReport(
                            bank_name=self.bank_name,
                            report_date=report_date,
                            report_url=report_url,
                            report_title=report_title,
                            report_type=ReportType.MONTHLY
                        )
                        all_reports.append(report)
                        report_found = True
            
            # Проверяем квартальный отчет если этот месяц - конец квартала
            if (current_month in [3, 6, 9, 12]) and (report_type == "ALL" or report_type == "quarterly"):
                quarter = (current_month // 3)
                file_name = f"fo-q{quarter}-{current_year}-rus.pdf"
                report_url = f"{self.reports_base_url}/{current_year}/{file_name}"
                
                if await self._check_url_exists(report_url):
                    report_date = date(current_year, current_month, 1)
                    report_title = f"Financial Report for Q{quarter} {current_year}"
                    
                    report = BankReport(
                        bank_name=self.bank_name,
                        report_date=report_date,
                        report_url=report_url,
                        report_title=report_title,
                        report_type=ReportType.QUARTERLY
                    )
                    all_reports.append(report)
                    report_found = True
            
            # Если не нашли отчет за этот месяц, поищем за последние несколько месяцев
            if not report_found:
                # Настраиваем дату для поиска за последние месяцы (до 4-х месяцев назад)
                month_offset = 1
                while month_offset <= 4 and not report_found:
                    # Вычисляем предыдущий месяц
                    if current_month > month_offset:
                        search_month = current_month - month_offset
                        search_year = current_year
                    else:
                        search_month = 12 - (month_offset - current_month)
                        search_year = current_year - 1
                    
                    short_year = search_year % 100
                    
                    for day in [1, 15]:
                        if report_type == "ALL" or report_type == "monthly":
                            file_name = f"fo-{day:02d}-{search_month:02d}-{short_year:02d}-rus.pdf"
                            report_url = f"{self.reports_base_url}/{search_year}/{file_name}"
                            
                            if await self._check_url_exists(report_url):
                                month_names = ["", "January", "February", "March", "April", "May", "June", 
                                            "July", "August", "September", "October", "November", "December"]
                                
                                report_date = date(search_year, search_month, 1)
                                report_title = f"Financial Report for {month_names[search_month]} {search_year} (published {day:02d}.{search_month:02d}.{search_year})"
                                
                                report = BankReport(
                                    bank_name=self.bank_name,
                                    report_date=report_date,
                                    report_url=report_url,
                                    report_title=report_title,
                                    report_type=ReportType.MONTHLY
                                )
                                all_reports.append(report)
                                report_found = True
                                break
                    
                    # Проверяем квартальный отчет если этот месяц - конец квартала
                    if (search_month in [3, 6, 9, 12]) and (report_type == "ALL" or report_type == "quarterly"):
                        quarter = (search_month // 3)
                        file_name = f"fo-q{quarter}-{search_year}-rus.pdf"
                        report_url = f"{self.reports_base_url}/{search_year}/{file_name}"
                        
                        if await self._check_url_exists(report_url):
                            report_date = date(search_year, search_month, 1)
                            report_title = f"Financial Report for Q{quarter} {search_year}"
                            
                            report = BankReport(
                                bank_name=self.bank_name,
                                report_date=report_date,
                                report_url=report_url,
                                report_title=report_title,
                                report_type=ReportType.QUARTERLY
                            )
                            all_reports.append(report)
                            report_found = True
                    
                    month_offset += 1
                    if report_found:
                        break
        else:
            # Стандартная логика поиска по диапазону дат
            # Iterate through all months in date range
            current_date = date(start_date.year, start_date.month, 1)
            
            while current_date <= end_date:
                year = current_date.year
                month = current_date.month
                
                # Skip monthly reports if not needed
                if report_type == "ALL" or report_type == "monthly":
                    # Format 1: monthly report with date in filename (example: fo-01-08-24-rus.pdf)
                    # day-month-year in 2-digit format
                    short_year = year % 100
                    for day in [1, 15]:  # Try different days, reports often published on 1st or 15th
                        file_name = f"fo-{day:02d}-{month:02d}-{short_year:02d}-rus.pdf"
                        report_url = f"{self.reports_base_url}/{year}/{file_name}"
                        
                        # Check if file exists before adding to results
                        if await self._check_url_exists(report_url):
                            month_names = ["", "January", "February", "March", "April", "May", "June", 
                                        "July", "August", "September", "October", "November", "December"]
                            
                            report_title = f"Financial Report for {month_names[month]} {year} (published {day:02d}.{month:02d}.{year})"
                            
                            report = BankReport(
                                bank_name=self.bank_name,
                                report_date=current_date,
                                report_url=report_url,
                                report_title=report_title,
                                report_type=ReportType.MONTHLY
                            )
                            all_reports.append(report)
                
                # Skip quarterly reports if not needed
                if report_type == "ALL" or report_type == "quarterly":
                    # Try quarterly report format if current month is quarter end
                    if month in [3, 6, 9, 12]:
                        quarter = (month // 3)
                        # Quarterly report format
                        file_name = f"fo-q{quarter}-{year}-rus.pdf"
                        report_url = f"{self.reports_base_url}/{year}/{file_name}"
                        
                        if await self._check_url_exists(report_url):
                            report_title = f"Financial Report for Q{quarter} {year}"
                            
                            report = BankReport(
                                bank_name=self.bank_name,
                                report_date=current_date,
                                report_url=report_url,
                                report_title=report_title,
                                report_type=ReportType.QUARTERLY
                            )
                            all_reports.append(report)
                
                # Move to next month
                if current_date.month == 12:
                    current_date = date(current_date.year + 1, 1, 1)
                else:
                    current_date = date(current_date.year, current_date.month + 1, 1)
        
        print(f"Optima Bank: Found {len(all_reports)} reports")
        return all_reports 