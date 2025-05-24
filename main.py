from fastapi import FastAPI, Query, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from datetime import date, datetime
import uvicorn
from pydantic import BaseModel
from enum import Enum
from typing import List, Optional, Dict, Any
import time
import os

# Предполагается, что эти импорты корректны для вашей структуры проекта
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
    allow_origins=["*"],  # Изменено для примера, настройте по необходимости
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
    return {"message": "Welcome to Bank Reports API", "status": "ok"}


@app.get("/reports", response_model=List[ReportResponse])
async def get_reports_endpoint(  # Переименовано, чтобы не конфликтовать с импортированной функцией
        start_date: date = Query(..., description="Start date for report search (YYYY-MM-DD)"),
        end_date: date = Query(None, description="End date for report search (YYYY-MM-DD)"),
        bank_ids: Optional[str] = Query(None,
                                        description="Bank IDs separated by commas (1=KICB, 2=Optima, 3=DemirBank, 4=MBank, 5=RSK, None=All banks). Example: 1,3,5"),
        report_type: ServiceReportType = Query(ServiceReportType.ALL,
                                               description="Type of reports to return (monthly, quarterly, or all)")
):
    """
    Get bank financial reports between specified dates.
    """
    try:
        parsed_bank_ids = None
        if bank_ids:
            try:
                parsed_bank_ids = [int(id_str.strip()) for id_str in bank_ids.split(",")]
            except ValueError:
                raise HTTPException(status_code=400,
                                    detail="Invalid bank_ids format. Must be comma-separated integers.")

        reports_data = await get_bank_reports(start_date, end_date, parsed_bank_ids, report_type)
        return reports_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching reports: {str(e)}")


@app.get("/analyze")
async def analyze_reports_endpoint(  # Переименовано
        start_date: date = Query(..., description="Start date for report search (YYYY-MM-DD)"),
        end_date: date = Query(None, description="End date for report search (YYYY-MM-DD)"),
        bank_ids: Optional[str] = Query(None,
                                        description="Bank IDs separated by commas (1=KICB, 2=Optima, 3=DemirBank, 4=MBank, 5=RSK, None=All banks). Example: 1,3,5"),
        report_type: ServiceReportType = Query(ServiceReportType.ALL,
                                               description="Type of reports to return (monthly, quarterly, or all)"),
        lang: str = Query("ru", description="Language for the analysis output (ru or ky). Default is 'ru'.",
                          pattern="^(ru|ky)$")
):
    """
    Analyze bank financial reports between specified dates using Gemini API.
    Returns a structured JSON with financial analysis.
    Language of the output can be 'ru' (Russian) or 'ky' (Kyrgyz).
    """
    try:
        parsed_bank_ids = None
        if bank_ids:
            try:
                parsed_bank_ids = [int(id_str.strip()) for id_str in bank_ids.split(",")]
            except ValueError:
                raise HTTPException(status_code=400,
                                    detail="Invalid bank_ids format. Must be comma-separated integers.")

        reports_data = await get_bank_reports(start_date, end_date, parsed_bank_ids, report_type)

        if not reports_data:
            return {"message": "No reports found for the given criteria.", "reports": [], "analyses": {},
                    "execution_time": 0.0}

        banks = set(report["bank_name"] for report in reports_data)
        is_comparative = len(banks) > 1

        analysis_result = await analyze_bank_reports(reports_data, lang=lang, is_comparative=is_comparative)

        return analysis_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing reports: {str(e)}")


@app.post("/analyze_by_pdf", response_model=PDFAnalysisResponse)
async def analyze_pdfs_endpoint(  # Переименовано
        files: List[UploadFile] = File(...),
        lang: str = Query("ru", description="Language for the analysis output (ru or ky). Default is 'ru'.",
                          pattern="^(ru|ky)$")
):
    """
    Analyze bank financial reports from uploaded PDF files.
    Language of the output can be 'ru' (Russian) or 'ky' (Kyrgyz).
    """
    try:
        start_time_analysis = time.time()

        analyses_dict = {}
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded.")

        for file in files:
            try:
                pdf_bytes = await file.read()
                # Получаем имя банка из имени файла (без расширения)
                bank_name_from_file = os.path.splitext(file.filename)[
                    0] if file.filename else f"unknown_bank_{len(analyses_dict)}"

                # Анализируем PDF
                analysis_result_single = await analyze_report_from_bytes(pdf_bytes, bank_name=bank_name_from_file,
                                                                         lang=lang)

                if "error" not in analysis_result_single:
                    analyses_dict[bank_name_from_file] = analysis_result_single
                else:
                    print(
                        f"Ошибка при анализе PDF для банка {bank_name_from_file} (язык: {lang}): {analysis_result_single['error']}")
                    # Можно добавить информацию об ошибке в ответ, если нужно
                    analyses_dict[bank_name_from_file] = {"error": analysis_result_single['error'],
                                                          "filename": file.filename}


            except Exception as e_file:
                print(f"Ошибка при обработке файла {file.filename if file.filename else 'unknown_file'}: {str(e_file)}")
                analyses_dict[file.filename if file.filename else f"error_file_{len(analyses_dict)}"] = {
                    "error": f"Failed to process file: {str(e_file)}",
                    "filename": file.filename
                }
                continue  # Продолжаем со следующим файлом

        successful_analyses = {k: v for k, v in analyses_dict.items() if "error" not in v}

        if not successful_analyses:  # Если ни один файл не удалось успешно проанализировать
            # Возвращаем все ошибки, если они были
            all_errors = True
            for bank_name_key, analysis_item in analyses_dict.items():
                if "error" not in analysis_item:
                    all_errors = False
                    break
            if all_errors and analyses_dict:  # Если есть только ошибки
                return PDFAnalysisResponse(
                    analyses=analyses_dict,  # Вернуть словарь с ошибками
                    comparative_analysis=None,
                    execution_time=time.time() - start_time_analysis
                )
            # Если были файлы, но все провалились по другой причине
            raise HTTPException(status_code=400, detail="Не удалось успешно проанализировать ни один PDF файл.")

        comparative_analysis_result = None
        if len(successful_analyses) > 1:
            try:
                # Для сравнительного анализа используем только успешно обработанные отчеты
                comparative_analysis_result = await compare_bank_analyses(list(successful_analyses.values()), lang=lang)
            except Exception as e_compare:
                print(f"Ошибка при сравнительном анализе (язык: {lang}): {str(e_compare)}")
                # Не прерываем выполнение, просто логируем ошибку

        execution_time_total = time.time() - start_time_analysis

        return PDFAnalysisResponse(
            analyses=analyses_dict,  # Возвращаем все результаты, включая ошибки для отдельных файлов
            comparative_analysis=comparative_analysis_result,
            execution_time=execution_time_total
        )

    except HTTPException:  # Перехватываем HTTPException, чтобы не обернуть их в 500
        raise
    except Exception as e:
        # Логируем полную ошибку для отладки
        import traceback
        print(f"Критическая ошибка в /analyze_by_pdf (язык: {lang}): {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ошибка при анализе PDF файлов: {str(e)}")


if __name__ == "__main__":
    # Убедитесь, что имя файла совпадает с тем, что передается uvicorn, например, `main.py` -> `main:app`
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)