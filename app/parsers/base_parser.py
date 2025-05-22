from abc import ABC, abstractmethod
from datetime import date
from typing import List, Optional

import aiohttp
from bs4 import BeautifulSoup

from app.parsers.models import BankReport, ReportType

class BaseParser(ABC):
    """Base abstract class for bank parsers"""
    
    def __init__(self, bank_name: str, base_url: str):
        self.bank_name = bank_name
        self.base_url = base_url
        self.session = None
    
    async def _get_session(self):
        """Get or create an aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch a page and return BeautifulSoup object"""
        session = await self._get_session()
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    return BeautifulSoup(html, 'lxml')
                return None
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    @abstractmethod
    async def get_reports(self, start_date: date, end_date: date, report_type: str = "ALL") -> List[BankReport]:
        """
        Get reports from the bank within the specified date range
        
        Args:
            start_date: Starting date for reports
            end_date: Ending date for reports
            report_type: Type of reports to return (monthly, quarterly, or all)
            
        Returns:
            List of BankReport objects
        """
        pass
    
    def filter_by_date_range(self, reports: List[BankReport], start_date: date, end_date: date) -> List[BankReport]:
        """
        Filter reports by date range (inclusive of start_date, exclusive of end_date)
        
        Args:
            reports: List of reports to filter
            start_date: Start date (inclusive)
            end_date: End date (exclusive)
        
        Returns:
            Filtered list of reports
        """
        # For monthly reports, we need exact matching (month and year)
        # If searching for just one day, include only that month
        if start_date.day == 1 and start_date == end_date:
            # Exact match for month and year (e.g. 2025-01-01)
            return [r for r in reports if r.report_date.year == start_date.year and 
                                          r.report_date.month == start_date.month]
        
        # Otherwise use a half-open interval [start_date, end_date)
        return [r for r in reports if start_date <= r.report_date < end_date]
    
    def filter_by_report_type(self, reports: List[BankReport], report_type: str) -> List[BankReport]:
        """
        Filter reports by type
        
        Args:
            reports: List of reports to filter
            report_type: Type of reports to include
            
        Returns:
            Filtered list of reports
        """
        if report_type == "ALL":
            return reports
        
        return [r for r in reports if r.report_type == report_type]
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close() 