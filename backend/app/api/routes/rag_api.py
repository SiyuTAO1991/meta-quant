# -*- coding: utf-8 -*-
"""财报 RAG 问答 API。"""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas.common import (
    ApiResponse,
    RagAskRequest,
    RagDocDetailRequest,
    RagDocListRequest,
)
from app.services import rag_service

router = APIRouter()


@router.post("/rag/meta", response_model=ApiResponse)
def rag_meta():
    return ApiResponse(data=rag_service.get_rag_meta())


@router.post("/rag/docs/list", response_model=ApiResponse)
def rag_docs_list(body: RagDocListRequest):
    try:
        data = rag_service.list_documents(body.stock_code, body.page, body.size)
        return ApiResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/docs/detail", response_model=ApiResponse)
def rag_docs_detail(body: RagDocDetailRequest):
    try:
        return ApiResponse(data=rag_service.get_document(body.doc_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/docs/upload", response_model=ApiResponse)
async def rag_docs_upload(
    file: UploadFile = File(...),
    stock_code: str = Form(...),
    stock_name: str = Form(""),
    report_type: str = Form("annual"),
    report_period: str = Form(""),
    title: str = Form(""),
):
    try:
        content = await file.read()
        data = rag_service.upload_and_index(
            file_bytes=content,
            file_name=file.filename or "report.pdf",
            stock_code=stock_code,
            stock_name=stock_name,
            report_type=report_type,
            report_period=report_period,
            title=title,
        )
        return ApiResponse(data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/docs/delete", response_model=ApiResponse)
def rag_docs_delete(body: RagDocDetailRequest):
    try:
        return ApiResponse(data=rag_service.delete_document(body.doc_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/ask", response_model=ApiResponse)
def rag_ask(body: RagAskRequest):
    try:
        data = rag_service.ask_document(body.doc_id, body.question, body.top_k)
        return ApiResponse(data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
