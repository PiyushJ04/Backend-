from datetime import datetime
from pydantic import BaseModel, ConfigDict

class BackgroundJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    exam_id: str
    requested_by: str
    job_type: str
    status: str
    sheet_id: str | None = None
    celery_task_id: str | None = None
    progress_total: int
    progress_completed: int
    result_json: dict | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

class BackgroundJobEnvelope(BaseModel):
    success: bool = True
    message: str
    data: BackgroundJobResponse
