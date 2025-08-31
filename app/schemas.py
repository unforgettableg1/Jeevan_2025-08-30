from __future__ import annotations
from pydantic import BaseModel

class TriggerResp(BaseModel):
    report_id: str

class ReportStatusResp(BaseModel):
    status: str
    report_path: str | None = None
    download_name: str | None = None
