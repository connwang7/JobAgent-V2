from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    nickname: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # access token 有效秒数


class UserOut(BaseModel):
    id: int
    email: EmailStr
    nickname: str

    model_config = {"from_attributes": True}


class LLMConfigUpdate(BaseModel):
    """用户级服务配置（设置页）。所有 Key 传明文，入库前 AES-GCM 加密。

    留空表示"不修改"；传空字符串之外的原值即覆盖。
    clear_* 为 True 时清空对应密钥。
    """
    api_key: str = ""
    base_url: str = ""
    model_pref: dict[str, str] = Field(
        default_factory=dict,
        description='角色→模型覆盖，如 {"writer": "deepseek-reasoner"}',
    )
    # 工具服务密钥：配置后优先于全局 .env，未配置时回落
    serper_api_key: str = ""
    firecrawl_api_key: str = ""
    # 显式清除（设置页"清除"按钮）
    clear_api_key: bool = False
    clear_serper: bool = False
    clear_firecrawl: bool = False


class LLMConfigOut(BaseModel):
    """设置页回显：只给掩码与状态，绝不返回密钥明文。"""
    base_url: str = ""
    base_url_effective: str = ""
    model_pref: dict[str, str] = Field(default_factory=dict)
    models: dict[str, str] = Field(default_factory=dict)       # 角色 → 实际生效模型
    defaults: dict[str, str] = Field(default_factory=dict)     # 角色 → 系统默认模型
    api_key_set: bool = False
    api_key_masked: str = ""
    serper_set: bool = False
    serper_masked: str = ""
    firecrawl_set: bool = False
    firecrawl_masked: str = ""
    embedding_ready: bool = False
    embedding_hint: str = ""
    # 联网搜索/岗位搜索是否可用（用户级 Serper Key 或服务端 .env 任一存在即为 True）
    web_search_ready: bool = False
    web_search_hint: str = ""


class LLMTestResult(BaseModel):
    ok: bool
    model: str = ""
    base_url: str = ""
    latency_ms: int = 0
    reply: str = ""
    error: str = ""
