"""
Munshi - Documents API
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session

from munshi.db.session import get_session
from munshi.db.models import InvoiceDocument

router = APIRouter(tags=["documents"])


@router.get("/documents/{document_id}")
def get_document(
    document_id: int,
    session: Session = Depends(get_session),
) -> FileResponse:
    """Download an uploaded document file."""
    doc = session.get(InvoiceDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

    import os
    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=doc.file_path,
        filename=f"{doc.doc_type}_{document_id}",
        media_type="application/octet-stream",
    )
