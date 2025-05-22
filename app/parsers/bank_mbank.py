from datetime import date, datetime
import re
from typing import List, Optional
import calendar

from app.parsers.base_parser import BaseParser
from app.parsers.models import BankReport, ReportType

class MBankParser(BaseParser):
    """Parser for MBank reports"""
    
    def __init__(self):
        super().__init__(
            bank_name="MBank",
            base_url="https://mbank.kg"
        )
    
    async def get_reports(self, start_date: date, end_date: date, report_type: str = "ALL") -> List[BankReport]:
        """
        Get reports from MBank within the specified date range.
        
        MBank organizes reports by year, and then by months within each year.
        The URL pattern is: https://mbank.kg/reports?year=YYYY
        """
        all_reports = []
        
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
            "1квартал": 1, "2квартал": 2, "3квартал": 3, "4квартал": 4,
            "квартал1": 1, "квартал2": 2, "квартал3": 3, "квартал4": 4,
            "q1": 1, "q2": 2, "q3": 3, "q4": 4
        }
        
        # English quarter names for report titles
        quarter_names_en = {
            1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"
        }
        
        # Get unique years in the date range
        years = set()
        current_date = date(start_date.year, start_date.month, 1)
        while current_date < end_date:
            years.add(current_date.year)
            # Move to next month
            if current_date.month == 12:
                current_date = date(current_date.year + 1, 1, 1)
            else:
                current_date = date(current_date.year, current_date.month + 1, 1)
        
        # Process each year
        for year in sorted(years):
            # Construct URL for the yearly reports page
            reports_url = f"{self.base_url}/reports?year={year}"
            
            # Fetch the yearly reports page
            soup = await self._fetch_page(reports_url)
            if not soup:
                continue
            
            # Find all month links on this page
            # Look for sections that contain month names
            found_links = []
            
            # Strategy 1: Find links with month names in them
            if report_type == "ALL" or report_type == "monthly":
                for month_name_ru, month_num in month_names_ru.items():
                    # Look for month names in links
                    month_elements = soup.find_all(lambda tag: tag.name == 'a' and month_name_ru.lower() in tag.text.lower())
                    
                    for element in month_elements:
                        href = element.get('href', '')
                        if href and '.pdf' in href.lower():  # Ensure it's a PDF link
                            found_links.append({
                                'month_num': month_num,
                                'href': href,
                                'text': element.text.strip(),
                                'report_type': ReportType.MONTHLY
                            })
                
                # Strategy 2: Find links in a section with months
                if not found_links:
                    # Look for a div with "Финансовые отчеты" heading
                    reports_section = soup.find(lambda tag: tag.name and "финансовые отчеты" in tag.text.lower())
                    if reports_section:
                        # Get the parent or next container
                        container = reports_section.parent
                        
                        # Find all links in this container
                        for link in container.find_all('a'):
                            href = link.get('href', '')
                            link_text = link.text.strip().lower()
                            
                            # Check if this link corresponds to a month
                            for month_name_ru, month_num in month_names_ru.items():
                                if month_name_ru.lower() in link_text:
                                    if href and '.pdf' in href.lower():  # Ensure it's a PDF link
                                        found_links.append({
                                            'month_num': month_num,
                                            'href': href,
                                            'text': link.text.strip(),
                                            'report_type': ReportType.MONTHLY
                                        })
                                        break
            
            # Strategy 3: Look for quarterly reports (if needed)
            if report_type == "ALL" or report_type == "quarterly":
                # Find elements that might contain quarterly reports
                quarter_section = soup.find(lambda tag: tag.name and "квартал" in tag.text.lower())
                
                if quarter_section:
                    # Find all links in this section
                    for link in quarter_section.find_all('a'):
                        href = link.get('href', '')
                        link_text = link.text.strip().lower()
                        
                        if href and '.pdf' in href.lower():
                            # Try to extract quarter information
                            quarter_num = None
                            
                            # Try to find quarter number in link text
                            for quarter_text, quarter_number in quarter_mappings.items():
                                if quarter_text.lower() in link_text.lower() or quarter_text.lower() in href.lower():
                                    quarter_num = quarter_number
                                    break
                            
                            # If we found a quarter number
                            if quarter_num:
                                # Convert quarter to first month in quarter
                                month_num = ((quarter_num - 1) * 3) + 1
                                
                                found_links.append({
                                    'month_num': month_num,
                                    'href': href,
                                    'text': link.text.strip(),
                                    'report_type': ReportType.QUARTERLY,
                                    'quarter_num': quarter_num
                                })
            
            # Strategy 4: Try direct PDF URLs for each month if we still have no links
            if not found_links:
                # MBank might have a predictable URL pattern for monthly reports
                for month_num, month_name_en in month_names_en.items():
                    # Skip if we're looking only for quarterly reports
                    if report_type == "quarterly":
                        continue
                        
                    # Try common URL patterns
                    possible_urls = [
                        f"{self.base_url}/uploads/reports/{year}/{month_num:02d}_{month_name_en.lower()}.pdf",
                        f"{self.base_url}/uploads/reports/{year}/report_{month_name_en.lower()}.pdf",
                        f"{self.base_url}/uploads/reports/{year}/report_{month_num:02d}.pdf",
                    ]
                    
                    for url in possible_urls:
                        # Check if the file exists using HEAD request
                        if await self._check_url_exists(url):
                            found_links.append({
                                'month_num': month_num,
                                'href': url,
                                'text': f"{month_name_en} {year}",
                                'report_type': ReportType.MONTHLY
                            })
                            break  # Skip other URL patterns if one is found
                
                # Try direct URL patterns for quarterly reports
                if report_type == "ALL" or report_type == "quarterly":
                    for quarter_num, quarter_name_en in quarter_names_en.items():
                        month_num = ((quarter_num - 1) * 3) + 1
                        
                        # Try common URL patterns for quarterly reports
                        possible_urls = [
                            f"{self.base_url}/uploads/reports/{year}/q{quarter_num}_{year}.pdf",
                            f"{self.base_url}/uploads/reports/{year}/{quarter_name_en.lower()}_{year}.pdf",
                            f"{self.base_url}/uploads/reports/{year}/quarter{quarter_num}.pdf",
                        ]
                        
                        for url in possible_urls:
                            if await self._check_url_exists(url):
                                found_links.append({
                                    'month_num': month_num,
                                    'href': url,
                                    'text': f"{quarter_name_en} {year}",
                                    'report_type': ReportType.QUARTERLY,
                                    'quarter_num': quarter_num
                                })
                                break
            
            # Process all found links
            for link_info in found_links:
                month_num = link_info['month_num']
                href = link_info['href']
                link_text = link_info['text']
                current_report_type = link_info['report_type']
                
                # Create report date for this month
                report_date = date(year, month_num, 1)
                
                # Format the URL
                report_url = href if href.startswith("http") else f"{self.base_url}{href}"
                
                # Create a title based on report type
                if current_report_type == ReportType.QUARTERLY:
                    quarter_num = link_info.get('quarter_num', (month_num - 1) // 3 + 1)
                    quarter_name = quarter_names_en[quarter_num]
                    report_title = f"Financial Report for {quarter_name} {year}"
                else:
                    month_name = month_names_en[month_num]
                    report_title = f"Financial Report for {month_name} {year}"
                
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
    
    async def _check_url_exists(self, url: str) -> bool:
        """Check if URL exists by sending HEAD request"""
        session = await self._get_session()
        try:
            async with session.head(url, allow_redirects=True) as response:
                return response.status == 200
        except Exception as e:
            print(f"Error checking URL {url}: {e}")
            return False 