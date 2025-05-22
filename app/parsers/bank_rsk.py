from datetime import date, datetime
import re
from typing import List, Optional

from app.parsers.base_parser import BaseParser
from app.parsers.models import BankReport, ReportType

class RSKParser(BaseParser):
    """Parser for RSK Bank reports"""
    
    def __init__(self):
        super().__init__(
            bank_name="РСК Банк",
            base_url="https://www.rsk.kg"
        )
        self.reports_url = f"{self.base_url}/ru/reports"
    
    async def get_reports(self, start_date: date, end_date: date, report_type: str = "ALL") -> List[BankReport]:
        """
        Get reports from RSK bank within the specified date range.
        
        RSK bank has encoded links with date patterns embedded in them.
        """
        all_reports = []
        
        # Fetch the main reports page
        soup = await self._fetch_page(self.reports_url)
        if not soup:
            return []
        
        # Find all links on the page
        all_links = soup.find_all('a')
        
        # Regular expressions to extract dates from URLs and link text
        date_pattern_url = re.compile(r'_(\d{2})\.(\d{2})\.(\d{2})_')  # Format: _DD.MM.YY_
        date_pattern_text = re.compile(r'(\d{2})\.(\d{2})\.(\d{4})')   # Format: DD.MM.YYYY
        
        processed_urls = set()  # To avoid duplicate reports
        
        for link in all_links:
            href = link.get('href', '')
            if not href:
                continue
                
            # Skip if we've already processed this URL
            if href in processed_urls:
                continue
                
            processed_urls.add(href)
            
            # Try to extract date from the URL
            date_match = date_pattern_url.search(href)
            report_date = None
            
            if date_match:
                # Extract date from URL
                day = int(date_match.group(1))
                month = int(date_match.group(2))
                year = 2000 + int(date_match.group(3))  # Assuming 20XX format
                
                try:
                    report_date = date(year, month, day)
                except ValueError:
                    # Invalid date, try next link
                    continue
            else:
                # Try to extract date from link text
                link_text = link.text.strip()
                date_match = date_pattern_text.search(link_text)
                
                if date_match:
                    day = int(date_match.group(1))
                    month = int(date_match.group(2))
                    year = int(date_match.group(3))
                    
                    try:
                        report_date = date(year, month, day)
                    except ValueError:
                        continue
            
            # If we found a valid date and it falls within our range
            if report_date and start_date <= report_date < end_date:
                # Ensure we have an absolute URL
                report_url = href if href.startswith('http') else f"{self.base_url}{href}"
                
                # Determine if it's a monthly or quarterly report
                current_report_type = ReportType.MONTHLY
                
                # Check if it could be a quarterly report (based on month)
                if report_date.month in [3, 6, 9, 12]:
                    current_report_type = ReportType.QUARTERLY
                
                # Skip if it doesn't match the requested report type
                if report_type != "ALL" and \
                   ((report_type == "monthly" and current_report_type == ReportType.QUARTERLY) or \
                    (report_type == "quarterly" and current_report_type == ReportType.MONTHLY)):
                    continue
                
                # Create report title
                month_names = ["", "January", "February", "March", "April", "May", "June", 
                              "July", "August", "September", "October", "November", "December"]
                
                if current_report_type == ReportType.MONTHLY:
                    report_title = f"Financial Report for {month_names[report_date.month]} {report_date.year}"
                else:
                    quarter = (report_date.month // 3)
                    report_title = f"Financial Report for Q{quarter} {report_date.year}"
                
                # Create and add the report
                report = BankReport(
                    bank_name=self.bank_name,
                    report_date=report_date,
                    report_url=report_url,
                    report_title=report_title,
                    report_type=current_report_type
                )
                all_reports.append(report)
        
        # No need to apply date filter again as we already filtered during processing
        return all_reports 