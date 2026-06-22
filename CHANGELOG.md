# Changelog

Tất cả thay đổi đáng chú ý của Helmes Agent được ghi lại ở đây.

Định dạng theo [Keep a Changelog](https://keepachangelog.com/),
phiên bản theo [Semantic Versioning](https://semver.org/).

## [1.4.0] - 2026-06-22

### Added
- **Tool `send_file`** — agent gửi tệp/ảnh từ workspace cho người chat dưới dạng Signal attachment.
  - Ví dụ: "chụp màn hình bài báo ở URL này rồi gửi cho tôi" → browser chụp PNG → `send_file` đính kèm gửi đi.
  - Hỗ trợ mọi loại file (ảnh, PDF, chart...) — tự nhận diện MIME.
  - Cross-thread bridge: `execute()` (worker thread) → `asyncio.run_coroutine_threadsafe` → SignalClient trên main loop.
  - Luôn khả dụng kể cả ở sub-agent (delivery tool không bị skill filter lọc bỏ).
- Tổng tool tích hợp: 14 → 15.

### Fixed
- `SignalClient.send_file` viết lại dùng JSON `base64_attachments` (data-URI) cho đúng API `/v2/send` của signal-cli-rest-api (bản cũ dùng multipart `files=` không hợp lệ với v2/send).

## [1.3.0] - 2026-06-22

### Added
- **Complexity-based model routing** — tự chọn model theo độ phức tạp tác vụ:
  - **light** (mặc định Sonnet) cho hỏi đáp, chat đơn giản, và vai trò "quản gia" (decompose + synthesis).
  - **heavy** (mặc định Opus) cho suy luận sâu, coding, phân tích, thiết kế.
  - `agent/model_router.py`: phân loại bằng skill + heuristic (từ khóa suy luận, độ dài, multi-step) — không tốn API call.
  - Mỗi sub-task trong decomposition tự chọn model theo độ phức tạp riêng.
- Config tiers per provider: `{ANTHROPIC,OPENAI,GEMINI}_MODEL_{LIGHT,HEAVY}` + `MODEL_ROUTING` (bật/tắt).
- `/model auto` bật routing; `/model <id>` ghim 1 model (tắt routing).
- `/info`, `/status` hiển thị model đang dùng + trạng thái routing; `/status` hiện model từng sub-task.

### Changed
- `provider.create()` nhận thêm tham số `model` để override per-call (phục vụ routing).
- Summarizer + orchestration (decompose/synthesis) chạy trên model light → tiết kiệm chi phí.
- `TaskResult` thêm field `model_used`.

## [1.2.0] - 2026-06-22

### Added
- **Browser automation tool** (`browser`) — điều khiển headless Chromium qua Puppeteer.
  - Render trang JavaScript/SPA mà `web_fetch` (HTTP thuần) không đọc được.
  - Thao tác trên trang: `click`, `type`, `wait_for`, `wait`, `press`, `evaluate`, `goto`.
  - Chụp screenshot lưu vào workspace (`screenshot`, `full_page`).
  - Node Puppeteer helper (`agent/browser/browser.js`) chạy qua subprocess, giao tiếp JSON — khớp model plugin sync, cô lập khỏi tiến trình Python.
- Config: `BROWSER_ENABLED`, `BROWSER_NODE_BIN`.
- Skill `research` thêm `browser` vào tool hints.

### Changed
- Dockerfile: cài `chromium` (apt tự kéo thư viện phụ thuộc) + `npm install puppeteer-core`; set `PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium`.
- Số lượng tool tích hợp: 13 → 14.

### Notes
- Deploy bản này cần rebuild image (`docker compose up -d --build`) để cài Chromium + puppeteer-core.

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

[1.4.0]: https://github.com/Ericnguyen89/helmes-deploy/releases/tag/v1.4.0
[1.3.0]: https://github.com/Ericnguyen89/helmes-deploy/releases/tag/v1.3.0
[1.2.0]: https://github.com/Ericnguyen89/helmes-deploy/releases/tag/v1.2.0
[1.1.0]: https://github.com/Ericnguyen89/helmes-deploy/releases/tag/v1.1.0
[1.0.0]: https://github.com/Ericnguyen89/helmes-deploy/releases/tag/v1.0.0
