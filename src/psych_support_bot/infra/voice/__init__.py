"""语音 I/O 适配层（STT / TTS）。

供应商无关：STT 支持 openai（multipart /audio/transcriptions）与 dots
（chat completions + audio_url + 服务端临时托管）双模式；TTS 走 OpenAI
兼容 /audio/speech。配置与主 LLM 完全分离（VOICE_STT_* / VOICE_TTS_*）。
"""

from psych_support_bot.infra.voice import media_store
from psych_support_bot.infra.voice.adapter import (
    MAX_AUDIO_BYTES,
    SttConfig,
    TtsConfig,
    VoiceNotConfigured,
    VoiceProviderError,
    get_stt_config,
    get_tts_config,
    synthesize,
    transcribe,
    validate_public_http_url,
)

__all__ = [
    "MAX_AUDIO_BYTES",
    "SttConfig",
    "TtsConfig",
    "VoiceNotConfigured",
    "VoiceProviderError",
    "get_stt_config",
    "get_tts_config",
    "media_store",
    "synthesize",
    "transcribe",
    "validate_public_http_url",
]
