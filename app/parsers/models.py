from datetime import date
from typing import Dict, Any
from enum import Enum

class ReportType(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    OTHER = "other"

class BankReport:
    def __init__(self, bank_name: str, report_date: date, report_url: str, report_title: str, report_type: ReportType = ReportType.MONTHLY):
        self.bank_name = bank_name
        self.report_date = report_date
        self.report_url = report_url
        self.report_title = report_title
        self.report_type = report_type
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "bank_name": self.bank_name,
            "report_date": self.report_date,
            "report_url": self.report_url,
            "report_title": self.report_title,
            "report_type": self.report_type
        } 