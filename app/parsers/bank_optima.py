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
        
        # Iterate through all months in date range
        current_date = date(start_date.year, start_date.month, 1)
        
        while current_date < end_date:
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
        
        # Apply date range filter
        filtered_reports = self.filter_by_date_range(all_reports, start_date, end_date)
        
        return filtered_reports 