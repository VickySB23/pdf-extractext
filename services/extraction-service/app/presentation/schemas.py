from pydantic import BaseModel


class ExtractResponse(BaseModel):
    content: str
    page_count: int
