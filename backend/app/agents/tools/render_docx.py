"""render_docx：求职信渲染为 docx 并上传对象存储（仅 HITL 确认后触发）。"""
from io import BytesIO
from typing import ClassVar

from docx import Document
from pydantic import BaseModel, Field

from app.agents.tools.adapters import BaseToolAdapter
from app.core.storage import get_storage, new_object_key


class RenderDocxInput(BaseModel):
    content: str = Field(min_length=1)
    user_id: int
    letter_id: str = ""


class RenderDocxAdapter(BaseToolAdapter):
    name: ClassVar[str] = "render_docx"
    input_schema: ClassVar[type[RenderDocxInput]] = RenderDocxInput
    cache_ttl: ClassVar[int | None] = None

    async def _arun(self, payload: RenderDocxInput) -> dict:
        doc = Document()
        for para in payload.content.split("\n"):
            if para.strip():
                doc.add_paragraph(para.strip())
        buf = BytesIO()
        doc.save(buf)

        key = new_object_key(f"letters/{payload.user_id}", "docx")
        get_storage().put(key, buf.getvalue(),
                          content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        return {"file_key": key}


render_docx = RenderDocxAdapter()
