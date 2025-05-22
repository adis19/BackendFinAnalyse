from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import date, datetime
import uvicorn
from pydantic import BaseModel
from enum import Enum

from app.parsers.parser_service import get_bank_reports, ServiceReportType
from app.parsers.gemini_analyzer import analyze_bank_reports

app = FastAPI(
    title="Bank Reports API",
    description="API for collecting financial reports from Kyrgyz banks",
    version="1.0.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ReportResponse(BaseModel):
    bank_name: str
    report_date: date
    report_url: str
    report_title: str
    report_type: str

@app.get("/")
async def root():
    # Простой ответ без внешних зависимостей
    return {"message": "Welcome to Bank Reports API", "status": "ok"}

@app.get("/reports", response_model=list[ReportResponse])
async def get_reports(
    start_date: date = Query(..., description="Start date for report search (YYYY-MM-DD)"),
    end_date: date = Query(None, description="End date for report search (YYYY-MM-DD)"),
    bank_id: int = Query(None, description="Bank ID (1=KICB, 2=Optima, 3=DemirBank, 4=MBank, 5=RSK, None=All banks)"),
    report_type: ServiceReportType = Query(ServiceReportType.ALL, description="Type of reports to return (monthly, quarterly, or all)")
):
    """
    Get bank financial reports between specified dates.
    """
    try:
        reports = await get_bank_reports(start_date, end_date, bank_id, report_type)
        return reports
    except Exception as e:
        # Добавляем обработку ошибок
        raise HTTPException(status_code=500, detail=f"Error fetching reports: {str(e)}")

@app.get("/analyze")
async def analyze_reports(
    start_date: date = Query(..., description="Start date for report search (YYYY-MM-DD)"),
    end_date: date = Query(None, description="End date for report search (YYYY-MM-DD)"),
    bank_id: int = Query(None, description="Bank ID (1=KICB, 2=Optima, 3=DemirBank, 4=MBank, 5=RSK, None=All banks)"),
    report_type: ServiceReportType = Query(ServiceReportType.ALL, description="Type of reports to return (monthly, quarterly, or all)")
):
    """
    Analyze bank financial reports between specified dates using Gemini API.
    
    Returns a structured JSON with financial analysis for one or multiple banks.
    If one bank is selected, returns detailed analysis.
    If multiple banks are selected, returns analysis for each bank and comparative analysis.
    """
    try:
        # Получение отчетов, как в эндпоинте /reports
        reports = await get_bank_reports(start_date, end_date, bank_id, report_type)
        
        # Если отчетов нет - вернем пустой результат
        if not reports:
            return {"error": "No reports found", "reports": []}
        
        # Проверяем, нужно ли делать сравнительный анализ (если выбрано несколько банков)
        banks = set(report["bank_name"] for report in reports)
        is_comparative = len(banks) > 1
        
        # Анализ отчетов
        analysis_result = await analyze_bank_reports(reports, is_comparative=is_comparative)
        
        return analysis_result
    except Exception as e:
        # Добавляем обработку ошибок
        raise HTTPException(status_code=500, detail=f"Error analyzing reports: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
