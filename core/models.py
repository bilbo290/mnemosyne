from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class Project(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    content_type: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ProjectSummary(BaseModel):
    project: Project
    content_count: int
    entity_count: int
    reference_count: int
