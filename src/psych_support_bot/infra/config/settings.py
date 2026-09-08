import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Psychological Support Bot"
    environment: str = "development"
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    database_url: str = "sqlite:///./psych_support_bot.db"
    redis_url: str = "redis://localhost:6379/0"
    langfuse_public_key: str = Field(default="", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="", alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(default="https://cloud.langfuse.com", alias="LANGFUSE_HOST")
    # 流量环境标记：生产入口保持默认 "production"；eval/测试入口在进程
    # 早期覆盖为 "eval"/"test"（见 evals/runner.py 与 tests/conftest.py），
    # 使 Langfuse 仪表盘与巡检可按环境过滤——基线巡检（2026-09-06）显示
    # 自动化流量占 trace 总量约 89%，不分流则所有统计先要人工排噪。
    langfuse_environment: str = Field(default="production", alias="LANGFUSE_ENVIRONMENT")
    default_conversation_mode: str = "support"
    app_debug: bool = False
    # LLM-as-judge model (separate model for evaluation scoring)
    judge_api_key: str = Field(default="", alias="JUDGE_API_KEY")
    judge_base_url: str = Field(default="", alias="JUDGE_BASE_URL")
    judge_model: str = Field(default="DeepSeek-V4-Flash", alias="JUDGE_MODEL")
    # M2 首答延迟优化：规则判 low/elevated 且支持模式时，风险 LLM 分类与回复
    # 生成并行投机；风险升级 high/critical 则丢弃投机回复走危机路径。
    # 测试环境由 conftest 置 false，避免单测触发真实回复生成。
    speculative_reply_enabled: bool = Field(default=True, alias="SPECULATIVE_REPLY_ENABLED")
    # 记忆层记录模块热插拔开关（ai/memory_modules.py 注册表）：
    # 关闭的模块不渲染进 prompt，仅影响上下文参考信息——安全地板
    # （safety_floor_risk_level）走独立通道，不受这些开关影响。
    memory_module_assessments: bool = Field(default=True, alias="MEMORY_MODULE_ASSESSMENTS")
    memory_module_checkins: bool = Field(default=True, alias="MEMORY_MODULE_CHECKINS")
    memory_module_exercises: bool = Field(default=True, alias="MEMORY_MODULE_EXERCISES")
    # JWT 认证：默认关闭（面板登录 UI 尚未上线，开启即拦截全部 /v1 数据端点）。
    # 商业化部署置 AUTH_ENABLED=true 并显式配置 JWT_SECRET_KEY。
    auth_enabled: bool = Field(default=False, alias="AUTH_ENABLED")
    jwt_secret_key: str = Field(default="", alias="JWT_SECRET_KEY")

    # ── 语音 I/O（与主 LLM 完全分离的供应商配置，便于独立换模型）────────
    # STT：provider = "openai"（multipart /audio/transcriptions，OpenAI/兼容
    # 网关）| "dots"（chat completions + audio_url 内容块，base64 data URI
    # 内联音频，无需公网托管 URL）。base_url/key/model 独立配置；缺省
    # 回落 OPENAI_*（行为兼容旧部署），但 dots 模式必须显式配置。
    voice_stt_provider: str = Field(default="", alias="VOICE_STT_PROVIDER")
    voice_stt_base_url: str = Field(default="", alias="VOICE_STT_BASE_URL")
    voice_stt_api_key: str = Field(default="", alias="VOICE_STT_API_KEY")
    voice_stt_model: str = Field(default="", alias="VOICE_STT_MODEL")
    voice_stt_language: str = Field(default="", alias="VOICE_STT_LANGUAGE")
    # TTS：provider = "minimax"（wss /ws/v1/t2a_v2_bidi 双向流式，用户指定）
    # | "openai"（POST /audio/speech，OpenAI 兼容）。api_key/model/voice
    # 两家共用；minimax 另需 ws_url。provider 缺省时按 base_url 是否配置
    # 回落 openai（旧行为兼容）；dots 平台无 TTS 端点。
    voice_tts_provider: str = Field(default="", alias="VOICE_TTS_PROVIDER")
    voice_tts_ws_url: str = Field(default="", alias="VOICE_TTS_WS_URL")
    voice_tts_language_boost: str = Field(default="Chinese", alias="VOICE_TTS_LANGUAGE_BOOST")
    voice_tts_base_url: str = Field(default="", alias="VOICE_TTS_BASE_URL")
    voice_tts_api_key: str = Field(default="", alias="VOICE_TTS_API_KEY")
    voice_tts_model: str = Field(default="", alias="VOICE_TTS_MODEL")
    voice_tts_voice: str = Field(default="", alias="VOICE_TTS_VOICE")

    @model_validator(mode="after")
    def apply_dashscope_fallbacks(self) -> "Settings":
        if not self.openai_api_key:
            self.openai_api_key = os.getenv("DASHSCOPE_API_KEY", "")
        if not self.openai_base_url:
            self.openai_base_url = os.getenv("DASHSCOPE_BASE_URL", "")
        if self.openai_model in {"", "gpt-4.1-mini"}:
            self.openai_model = os.getenv("DASHSCOPE_MODEL", self.openai_model)
        if not self.jwt_secret_key:
            # 未显式配置时生成随机临时密钥（注册/登录端点始终可用，需可签发）：
            # AUTH_ENABLED=true 的部署重启后所有已签发 token 失效——
            # 生产必须显式配置 JWT_SECRET_KEY。
            import secrets

            self.jwt_secret_key = secrets.token_urlsafe(48)
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
