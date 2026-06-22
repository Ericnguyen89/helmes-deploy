# Changelog

Tất cả thay đổi đáng chú ý của Helmes Agent được ghi lại ở đây.

Định dạng theo [Keep a Changelog](https://keepachangelog.com/),
phiên bản theo [Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-06-22

### Added
- **Multi-Provider LLM**: hỗ trợ Claude (Anthropic), GPT (OpenAI) và Gemini (Google).
  - Provider abstraction layer mới trong `agent/providers/` (`base`, `anthropic_provider`, `openai_provider`).
  - OpenAI và Gemini dùng chung OpenAI SDK (Gemini qua endpoint OpenAI-compatible).
  - Conversation history dùng canonical format → **đổi provider giữa cuộc hội thoại** không mất context.
  - Cấu hình: `LLM_PROVIDER` + `{ANTHROPIC,OPENAI,GEMINI}_{API_KEY,BASE_URL,MODEL}`.
- `/model <name>` tự nhận diện provider từ tên model và rebuild engine (fail gracefully nếu thiếu API key).
- `/info` hiển thị provider đang active; `/info`, `/ping` hiển thị version.
- File `agent/version.py` làm single source of truth cho version.

### Changed
- `AIEngine` khởi tạo bằng `provider_name` + `provider_configs` thay vì `api_key`/`base_url` trực tiếp.
- `ai_engine`, `sub_agent`, `summarizer` refactor để dùng provider abstraction thay vì gọi thẳng Anthropic SDK.

### Notes
- Backward compatible: mặc định vẫn là `anthropic`, cấu hình `ANTHROPIC_*` cũ hoạt động như trước.
- Deploy bản này cần rebuild image để cài `openai` SDK.

## [1.0.0] - 2026-06-22

### Added
- Signal messenger AI agent, kiến trúc fully async (asyncio + httpx).
- 13 plugin tools: bash, file read/write, python, web search/fetch, email, memory, scheduler.
- DeerFlow-inspired: skill system (5 skills), sub-agent decomposition.
- Budget-aware tool loop (3-layer defense) chống lỗi max tool iterations.
- Structured task tracking + lệnh `/status`.
- Multi-modal vision, context summarization, scheduled tasks (cron).
- Docker Compose deployment + systemd auto-start.

[1.1.0]: https://github.com/Ericnguyen89/helmes-deploy/releases/tag/v1.1.0
[1.0.0]: https://github.com/Ericnguyen89/helmes-deploy/releases/tag/v1.0.0
