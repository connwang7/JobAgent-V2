from datetime import datetime

from pydantic import BaseModel


class SessionCreate(BaseModel):
    title: str = "新会话"
    resume_id: int | None = None


class SessionOut(BaseModel):
    id: str
    title: str
    resume_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: int
    role: str
    agent_name: str
    content: str
    refs: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    content: str
    # 深度思考：改用推理模型，并把 reasoning_content 以 thinking 事件流式下发
    deep_thinking: bool = False
    # 联网搜索：给 Planner 加约束，强制包含 WebSearcher 步骤
    web_search: bool = False
    # 本会话参考简历（用户显式上传后才传）：后端校验归属并绑定到会话
    resume_id: int | None = None


class SessionResumeUpdate(BaseModel):
    """会话绑定/解绑参考简历（resume_id=None 表示取消关联）。"""

    resume_id: int | None = None
