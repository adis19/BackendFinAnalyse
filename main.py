from fastapi import FastAPI, Query, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from datetime import date, datetime
import uvicorn
from pydantic import BaseModel
from enum import Enum
from typing import List, Optional, Dict, Any
import time
import os

from app.parsers.parser_service import get_bank_reports, ServiceReportType
from app.parsers.gemini_analyzer import analyze_bank_reports, analyze_report_from_bytes, compare_bank_analyses

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

class PDFAnalysisResponse(BaseModel):
    """Response model for PDF analysis endpoint"""
    analyses: Dict[str, Any]
    comparative_analysis: Optional[Dict[str, Any]] = None
    execution_time: float

@app.get("/")
async def root():
    # Простой ответ без внешних зависимостей
    return {"message": "Welcome to Bank Reports API", "status": "ok"}

@app.get("/reports", response_model=list[ReportResponse])
async def get_reports(
    start_date: date = Query(..., description="Start date for report search (YYYY-MM-DD)"),
    end_date: date = Query(None, description="End date for report search (YYYY-MM-DD)"),
    bank_ids: Optional[str] = Query(None, description="Bank IDs separated by commas (1=KICB, 2=Optima, 3=DemirBank, 4=MBank, 5=RSK, None=All banks). Example: 1,3,5"),
    report_type: ServiceReportType = Query(ServiceReportType.ALL, description="Type of reports to return (monthly, quarterly, or all)")
):
    """
    Get bank financial reports between specified dates.
    """
    try:
        # Parse bank_ids from comma-separated string to list of integers
        parsed_bank_ids = None
        if bank_ids:
            try:
                parsed_bank_ids = [int(id.strip()) for id in bank_ids.split(",")]
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid bank_ids format. Must be comma-separated integers.")

        reports = await get_bank_reports(start_date, end_date, parsed_bank_ids, report_type)
        return reports
    except Exception as e:
        # Добавляем обработку ошибок
        raise HTTPException(status_code=500, detail=f"Error fetching reports: {str(e)}")

@app.get("/analyze")
async def analyze_reports(
    start_date: date = Query(..., description="Start date for report search (YYYY-MM-DD)"),
    end_date: date = Query(None, description="End date for report search (YYYY-MM-DD)"),
    bank_ids: Optional[str] = Query(None, description="Bank IDs separated by commas (1=KICB, 2=Optima, 3=DemirBank, 4=MBank, 5=RSK, None=All banks). Example: 1,3,5"),
    report_type: ServiceReportType = Query(ServiceReportType.ALL, description="Type of reports to return (monthly, quarterly, or all)")
):
    """
    Analyze bank financial reports between specified dates using Gemini API.
    
    Returns a structured JSON with financial analysis for one or multiple banks.
    If one bank is selected, returns detailed analysis.
    If multiple banks are selected, returns analysis for each bank and comparative analysis.
    """
    try:
        # Parse bank_ids from comma-separated string to list of integers
        parsed_bank_ids = None
        if bank_ids:
            try:
                parsed_bank_ids = [int(id.strip()) for id in bank_ids.split(",")]
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid bank_ids format. Must be comma-separated integers.")

        # Получение отчетов, как в эндпоинте /reports
        reports = await get_bank_reports(start_date, end_date, parsed_bank_ids, report_type)
        
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

@app.post("/analyze_by_pdf", response_model=PDFAnalysisResponse)
async def analyze_pdfs(files: List[UploadFile] = File(...)):
    """
    Analyze bank financial reports from uploaded PDF files.

    If one PDF is uploaded, returns detailed analysis for that bank.
    If multiple PDFs are uploaded, returns analysis for each bank and comparative analysis.
    """
    try:
        start_time = time.time()

        # Анализ каждого загруженного PDF
        analyses = {}
        for file in files:
            try:
                # Читаем содержимое PDF файла
                pdf_bytes = await file.read()

                # Получаем имя банка из имени файла (без расширения)
                bank_name = os.path.splitext(file.filename)[0]

                # Анализируем PDF
                analysis_result = await analyze_report_from_bytes(pdf_bytes, bank_name=bank_name)

                # Если анализ успешен (нет ошибок)
                if "error" not in analysis_result:
                    analyses[bank_name] = analysis_result
                else:
                    print(f"Ошибка при анализе PDF для банка {bank_name}: {analysis_result['error']}")

            except Exception as e:
                print(f"Ошибка при обработке файла {file.filename}: {str(e)}")
                continue

        # Если нет успешных анализов
        if not analyses:
            raise HTTPException(status_code=400, detail="Не удалось проанализировать ни один PDF файл")

        # Проверяем, нужно ли делать сравнительный анализ
        comparative_analysis = None
        if len(analyses) > 1:
            try:
                comparative_analysis = await compare_bank_analyses(list(analyses.values()))
            except Exception as e:
                print(f"Ошибка при сравнительном анализе: {str(e)}")
                # Не прерываем выполнение, просто логируем ошибку

        execution_time = time.time() - start_time

        return PDFAnalysisResponse(
            analyses=analyses,
            comparative_analysis=comparative_analysis,
            execution_time=execution_time
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при анализе PDF файлов: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
