"""resume_extractor：PDF 解析（PyMuPDF）。

从对象存储按 file_key 读取（替代 v1 硬编码 temp/resume.pdf）。
"""
from typing import ClassVar

import pymupdf  # PyMuPDF（旧名 fitz 已弃用）
from pydantic import BaseModel, Field

from app.agents.tools.adapters import BaseToolAdapter
from app.core.storage import get_storage


class ResumeExtractInput(BaseModel):
    file_key: str = Field(min_length=1)


class ResumeExtractorAdapter(BaseToolAdapter):
    name: ClassVar[str] = "resume_extractor"
    input_schema: ClassVar[type[ResumeExtractInput]] = ResumeExtractInput
    cache_ttl: ClassVar[int | None] = None

    async def _arun(self, payload: ResumeExtractInput) -> str:
        data = get_storage().get(payload.file_key)
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            pages = [page.get_text() for page in pdf]
        return "\n".join(pages).strip()


resume_extractor = ResumeExtractorAdapter()
