from datetime import date, datetime
import re
from typing import List, Optional
import calendar

from app.parsers.base_parser import BaseParser
from app.parsers.models import BankReport, ReportType

class DemirbankParser(BaseParser):
    """Parser for DemirBank reports"""
    
    def __init__(self):
        super().__init__(
            bank_name="DemirBank",
            base_url="https://demirbank.kg"
        )
        self.reports_url = f"{self.base_url}/ru/about/about/financial-highlights"
    
    async def get_reports(self, start_date: date, end_date: date, report_type: str = "ALL") -> List[BankReport]:
        """
        Get reports from DemirBank within the specified date range.
        
        The DemirBank site has all reports on a single page in a table format,
        organized by year, quarter, and month.
        """
        all_reports = []
        
        # Fetch the main reports page
        soup = await self._fetch_page(self.reports_url)
        if not soup:
            return []
            
        # Russian month names in lowercase for matching
        month_names_ru = {
            "январь": 1, "февраль": 2, "март": 3, "апрель": 4, 
            "май": 5, "июнь": 6, "июль": 7, "август": 8,
            "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12
        }
        
        # English month names for report titles
        month_names_en = {
            1: "January", 2: "February", 3: "March", 4: "April",
            5: "May", 6: "June", 7: "July", 8: "August",
            9: "September", 10: "October", 11: "November", 12: "December"
        }
        
        # Quarter mappings
        quarter_mappings = {
            "i квартал": 1, "ii квартал": 2, "iii квартал": 3, "iv квартал": 4,
            "i": 1, "ii": 2, "iii": 3, "iv": 4,
            "1": 1, "2": 2, "3": 3, "4": 4,
            "q1": 1, "q2": 2, "q3": 3, "q4": 4
        }
        
        # English quarter names for report titles
        quarter_names_en = {
            1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"
        }
        
        # Find all tables with financial reports
        all_tables = soup.find_all('table')
        report_links = []
        
        # Process all tables
        for table in all_tables:
            # Try to find the year for this table
            year_text = None
            
            # Look for years in table rows (e.g. "2024" or "2025")
            for row in table.find_all('tr'):
                year_match = re.search(r'20(\d{2})', row.text)
                if year_match:
                    year_text = row.text
                    break
            
            if year_text is None:
                continue
                
            # Extract year from the year text
            year_match = re.search(r'20(\d{2})', year_text)
            if not year_match:
                continue
                
            year = int("20" + year_match.group(1))
            
            # Find all links in this table
            for link in table.find_all('a'):
                href = link.get('href', '')
                link_text = link.text.strip().lower()
                
                # Skip links that don't point to PDF reports
                if not href or ".pdf" not in href.lower():
                    continue
                
                # Add the link with its text and year for processing
                report_links.append({
                    "href": href,
                    "text": link_text,
                    "year": year
                })
        
        # Process all collected links for monthly and quarterly reports
        for link_info in report_links:
            href = link_info["href"]
            link_text = link_info["text"]
            year = link_info["year"]
            
            report_date = None
            report_title = None
            current_report_type = None
            
            # Check if this is a monthly report (only if needed)
            if report_type == "ALL" or report_type == "monthly":
                month_num = None
                for month_name, month_number in month_names_ru.items():
                    if month_name in link_text:
                        month_num = month_number
                        break
                
                # If no match in text, try URL patterns
                if month_num is None:
                    # Check for patterns like 'fsjanuary' or 'fsaugust' in URL
                    href_lower = href.lower()
                    
                    # Check Russian month names in URL
                    for month_name, month_number in month_names_ru.items():
                        if f"fs{month_name}" in href_lower or f"-{month_name}-" in href_lower:
                            month_num = month_number
                            break
                    
                    # Check English month names in URL
                    if month_num is None:
                        for en_month in ["january", "february", "march", "april", "may", "june", 
                                        "july", "august", "september", "october", "november", "december"]:
                            if en_month in href_lower:
                                for idx, month_name_en in month_names_en.items():
                                    if month_name_en.lower() == en_month:
                                        month_num = idx
                                        break
                                if month_num:
                                    break
                
                # If we found a month, this is a monthly report
                if month_num is not None:
                    report_date = date(year, month_num, 1)
                    report_title = f"Financial Report for {month_names_en[month_num]} {year}"
                    current_report_type = ReportType.MONTHLY
            
            # Check if this is a quarterly report (only if needed)
            if (report_type == "ALL" or report_type == "quarterly") and not report_date:
                quarter_num = None
                
                # Check quarter in text
                for quarter_text, quarter_number in quarter_mappings.items():
                    if quarter_text in link_text:
                        quarter_num = quarter_number
                        break
                
                # Check quarter in URL
                if quarter_num is None:
                    href_lower = href.lower()
                    for quarter_text, quarter_number in quarter_mappings.items():
                        if f"fs{quarter_text}" in href_lower or f"-{quarter_text}-" in href_lower or f"q{quarter_number}" in href_lower:
                            quarter_num = quarter_number
                            break
                
                # If we found a quarter, this is a quarterly report
                if quarter_num is not None:
                    # Convert quarter to month (Q1->Jan, Q2->Apr, Q3->Jul, Q4->Oct)
                    month = ((quarter_num - 1) * 3) + 1
                    report_date = date(year, month, 1)
                    report_title = f"Financial Report for {quarter_names_en[quarter_num]} {year}"
                    current_report_type = ReportType.QUARTERLY
            
            # If we successfully determined the report date and it's within the range
            if report_date is not None:
                # Format the URL
                report_url = href if href.startswith("http") else f"{self.base_url}{href}"
                
                # Create the report object
                report = BankReport(
                    bank_name=self.bank_name,
                    report_date=report_date,
                    report_url=report_url,
                    report_title=report_title,
                    report_type=current_report_type
                )
                all_reports.append(report)
        
        # Apply date range filter
        filtered_reports = self.filter_by_date_range(all_reports, start_date, end_date)
        
        return filtered_reports 