from datetime import date
from typing import List, Optional, Dict, Any, Union
from enum import Enum

from app.parsers.models import BankReport, ReportType
from app.parsers.bank_kicb import KICBParser
from app.parsers.bank_optima import OptimaParser
from app.parsers.bank_demirbank import DemirbankParser
from app.parsers.bank_mbank import MBankParser
from app.parsers.bank_rsk import RSKParser

# Определяем тип отчетов для API
class ServiceReportType(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ALL = "all"

async def get_bank_reports(
    start_date: date,
    end_date: Optional[date] = None,
    bank_ids: Optional[List[int]] = None,
    report_type: ServiceReportType = ServiceReportType.ALL
) -> List[Dict[str, Any]]:
    """
    Get financial reports from banks based on date range and bank ID
    
    Args:
        start_date: Starting date for report search
        end_date: Ending date for report search (defaults to start_date if not provided)
        bank_ids: List of bank IDs to search (1=KICB, 2=Optima, 3=Demirbank, 4=MBank, 5=RSK, None=All banks)
        report_type: Type of reports to return (monthly, quarterly, or all)
    
    Returns:
        List of reports found
    """
    # If end_date is not provided, use start_date (exactly the same day)
    if end_date is None:
        end_date = start_date
    
    parsers = []
    
    # If bank_ids is None or empty, include all banks
    if bank_ids is None or len(bank_ids) == 0:
        parsers = [
            KICBParser(),
            OptimaParser(),
            DemirbankParser(),
            MBankParser(),
            RSKParser()
        ]
    else:
        # Add parsers for each requested bank ID
        for bank_id in bank_ids:
            if bank_id == 1:
                parsers.append(KICBParser())
            elif bank_id == 2:
                parsers.append(OptimaParser())
            elif bank_id == 3:
                parsers.append(DemirbankParser())
            elif bank_id == 4:
                parsers.append(MBankParser())
            elif bank_id == 5:
                parsers.append(RSKParser())
    
    all_reports = []
    
    # Fetch reports from each selected parser
    for parser in parsers:
        reports = await parser.get_reports(start_date, end_date, report_type.value)
        all_reports.extend(reports)
    
    # Convert reports to dictionaries for API response
    return [report.to_dict() for report in all_reports] 