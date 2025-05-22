from datetime import date, datetime
import re
from typing import List, Optional

from app.parsers.base_parser import BaseParser
from app.parsers.models import BankReport, ReportType

class KICBParser(BaseParser):
    """Parser for Kyrgyz Investment and Credit Bank (KICB) reports"""
    
    def __init__(self):
        super().__init__(
            bank_name="KICB Bank",
            base_url="https://kicb.net"
        )
        self.reports_base_url = f"{self.base_url}/about/financial-reporting"
    
    async def get_reports(self, start_date: date, end_date: date, report_type: str = "ALL") -> List[BankReport]:
        """
        Get reports from KICB bank within the specified date range
        
        Algorithm:
        1. For each year in the date range, visit the yearly reports page
        2. On the yearly page, find links for monthly or quarterly reports
        3. If the date falls within requested range, get reports
        """
        all_reports = []
        
        # Get unique years in the date range
        years = set()
        current_date = date(start_date.year, start_date.month, 1)
        while current_date <= end_date:
            years.add(current_date.year)
            # Move to next month
            if current_date.month == 12:
                current_date = date(current_date.year + 1, 1, 1)
            else:
                current_date = date(current_date.year, current_date.month + 1, 1)
        
        # Russian month names mapping for search
        month_names_ru = {
            1: "Январь",
            2: "Февраль",
            3: "Март",
            4: "Апрель",
            5: "Май",
            6: "Июнь",
            7: "Июль",
            8: "Август",
            9: "Сентябрь",
            10: "Октябрь",
            11: "Ноябрь",
            12: "Декабрь",
        }
        
        # English month names for report titles
        month_names_en = {
            1: "January",
            2: "February",
            3: "March",
            4: "April",
            5: "May",
            6: "June",
            7: "July",
            8: "August",
            9: "September",
            10: "October",
            11: "November",
            12: "December",
        }
        
        # Russian quarter names for search
        quarter_names_ru = {
            1: "I квартал",
            2: "II квартал",
            3: "III квартал",
            4: "IV квартал",
        }
        
        # English quarter names for report titles
        quarter_names_en = {
            1: "Q1",
            2: "Q2",
            3: "Q3",
            4: "Q4",
        }
        
        # Process each year
        for year in sorted(years):
            # Construct URL for the yearly reports page
            year_url = f"{self.reports_base_url}/{year}/"
            
            # Fetch the yearly reports page
            soup = await self._fetch_page(year_url)
            if not soup:
                continue
                
            # Skip monthly reports if not needed
            if report_type == "ALL" or report_type == "monthly":
                # Find monthly reports
                monthly_section = soup.find(lambda tag: tag.name and tag.text.strip() == "Ежемесячная финансовая отчетность")
                if monthly_section:
                    # Find month items in this section - looking at parent, siblings or next elements
                    monthly_items = []
                    
                    # Try different strategies to find month links
                    # Strategy 1: Find all links after the section header
                    section_container = monthly_section.parent
                    if section_container:
                        monthly_items = section_container.find_all('a')
                        
                    # If no items found, try another approach
                    if not monthly_items:
                        # Strategy 2: Look for h2 and find all links after it
                        monthly_h2 = soup.find('h2', text=re.compile("Ежемесячная финансовая отчетность"))
                        if monthly_h2:
                            current = monthly_h2.next_sibling
                            while current and not (current.name == 'h2' and 'квартал' in current.text.lower()):
                                if current.name == 'a' or (hasattr(current, 'find_all') and current.find_all('a')):
                                    if current.name == 'a':
                                        monthly_items.append(current)
                                    else:
                                        monthly_items.extend(current.find_all('a'))
                                current = current.next_sibling
                    
                    # Process each monthly item
                    for item in monthly_items:
                        item_text = item.text.strip()
                        # Check if this is a month name with year
                        for month_num, month_name_ru in month_names_ru.items():
                            if month_name_ru in item_text and str(year) in item_text:
                                # This is a monthly report
                                report_date = date(year, month_num, 1)
                                month_name_en = month_names_en[month_num]
                                
                                # Check if this date is in the requested range
                                if start_date <= report_date < date(report_date.year + (1 if report_date.month == 12 else 0), 
                                                                   (report_date.month % 12) + 1, 1):
                                    # Get the href link
                                    href = item.get('href', '')
                                    report_url = ""
                                    
                                    # If this is already a PDF link, use it directly
                                    if href.endswith('.pdf'):
                                        report_url = href if href.startswith('http') else f"{self.base_url}{href}"
                                    else:
                                        # Otherwise, we need to visit this page to find PDF links
                                        monthly_url = href if href.startswith('http') else f"{self.base_url}{href}"
                                        monthly_soup = await self._fetch_page(monthly_url)
                                        if monthly_soup:
                                            # Find PDF links on the monthly page
                                            pdf_link = monthly_soup.find('a', href=re.compile(r'\.pdf$'))
                                            if pdf_link:
                                                pdf_href = pdf_link.get('href', '')
                                                report_url = pdf_href if pdf_href.startswith('http') else f"{self.base_url}{pdf_href}"
                                    
                                    if report_url:
                                        # Create and add the report
                                        report = BankReport(
                                            bank_name=self.bank_name,
                                            report_date=report_date,
                                            report_url=report_url,
                                            report_title=f"Financial Report for {month_name_en} {year}",
                                            report_type=ReportType.MONTHLY
                                        )
                                        all_reports.append(report)
            
            # Skip quarterly reports if not needed
            if report_type == "ALL" or report_type == "quarterly":
                # Find quarterly reports
                quarterly_section = soup.find(lambda tag: tag.name and tag.text.strip() == "Квартальная финансовая отчетность")
                if quarterly_section:
                    # Find quarter items - similar approach as with monthly
                    quarterly_items = []
                    
                    # Strategy 1: Find all links after the section header
                    section_container = quarterly_section.parent
                    if section_container:
                        quarterly_items = section_container.find_all('a')
                    
                    # If no items found, try another approach
                    if not quarterly_items:
                        # Strategy 2: Look for h2 and find all links after it
                        quarterly_h2 = soup.find('h2', text=re.compile("Квартальная финансовая отчетность"))
                        if quarterly_h2:
                            current = quarterly_h2.next_sibling
                            while current and not (current.name == 'h2' and 'месячная' in current.text.lower()):
                                if current.name == 'a' or (hasattr(current, 'find_all') and current.find_all('a')):
                                    if current.name == 'a':
                                        quarterly_items.append(current)
                                    else:
                                        quarterly_items.extend(current.find_all('a'))
                                current = current.next_sibling
                    
                    # Process each quarterly item
                    for item in quarterly_items:
                        item_text = item.text.strip()
                        # Check if this is a quarter with year
                        for quarter_num, quarter_name_ru in quarter_names_ru.items():
                            if quarter_name_ru in item_text and str(year) in item_text:
                                # This is a quarterly report
                                month = (quarter_num - 1) * 3 + 1  # Convert quarter to starting month
                                report_date = date(year, month, 1)
                                quarter_name_en = quarter_names_en[quarter_num]
                                
                                # Check if this date is in the requested range
                                if start_date <= report_date < date(report_date.year + (0 if month < 10 else 1), 
                                                                  (month + 2) % 12 + 1, 1):
                                    # Get the href link
                                    href = item.get('href', '')
                                    report_url = ""
                                    
                                    # If this is already a PDF link, use it directly
                                    if href.endswith('.pdf'):
                                        report_url = href if href.startswith('http') else f"{self.base_url}{href}"
                                    else:
                                        # Otherwise, we need to visit this page to find PDF links
                                        quarterly_url = href if href.startswith('http') else f"{self.base_url}{href}"
                                        quarterly_soup = await self._fetch_page(quarterly_url)
                                        if quarterly_soup:
                                            # Find PDF links on the quarterly page
                                            pdf_link = quarterly_soup.find('a', href=re.compile(r'\.pdf$'))
                                            if pdf_link:
                                                pdf_href = pdf_link.get('href', '')
                                                report_url = pdf_href if pdf_href.startswith('http') else f"{self.base_url}{pdf_href}"
                                    
                                    if report_url:
                                        # Create and add the report
                                        report = BankReport(
                                            bank_name=self.bank_name,
                                            report_date=report_date,
                                            report_url=report_url,
                                            report_title=f"Financial Report for {quarter_name_en} {year}",
                                            report_type=ReportType.QUARTERLY
                                        )
                                        all_reports.append(report)
        
        # Apply date range filter (check for exact day if start_date == end_date)
        filtered_reports = self.filter_by_date_range(all_reports, start_date, end_date)
        
        return filtered_reports 