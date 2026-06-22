# Helmes Agent

AI Agent framework sử dụng Signal làm giao diện chat, kết nối với Claude API (Anthropic). Hỗ trợ tool execution, skill-based task routing, sub-agent decomposition, persistent memory, scheduled tasks, multi-modal (vision), và nhiều hơn nữa.

> **Lưu ý:** Helmes Agent là một agent framework độc lập, không liên quan đến Hermes model của Nous Research.

## Tính năng

### Core
- **Multi-Provider LLM**: Claude (Anthropic), GPT (OpenAI), và Gemini (Google) — đổi provider qua `.env` hoặc runtime bằng `/model`
- **13 tools tích hợp**: bash, file read/write, python, web search, web fetch, email, memory, scheduler
- **Plugin system**: Dễ dàng thêm tool mới bằng cách tạo file plugin
- **Persistent memory**: Agent nhớ thông tin qua các cuộc hội thoại
- **Scheduled tasks**: Lên lịch chạy task tự động (cron syntax)
- **Context summarization**: Tự động tóm tắt khi hội thoại dài
- **Multi-modal**: Nhận và phân tích ảnh qua Signal (Claude Vision)
- **Dual search engine**: Google Custom Search hoặc DuckDuckGo
- **Gmail integration**: Gửi email kết quả qua Gmail SMTP

### Agent Intelligence (DeerFlow-inspired)
- **Skill System**: Auto-classify task → load focused prompt (research, coding, sysadmin, data analysis) → model hoạt động hiệu quả hơn
- **Sub-agent Decomposition**: Task phức tạp tự động tách thành sub-tasks, chạy song song hoặc tuần tự, rồi tổng hợp kết quả
- **Budget-aware Tool Loop**: Model biết còn bao nhiêu iteration, tự wrap up khi sắp hết → không bao giờ mất kết quả
- **Structured Task Tracking**: Token counting, duration, status tracking cho mỗi task — xem qua `/status`

## Kiến trúc

```
Signal App ──► Signal Server ──► signal-cli-rest-api ──► Helmes Agent ──► LLM Provider
                                    (Docker)              (Python)       Claude/GPT/Gemini
                                                             │
                                                 ┌───────────┼───────────┐
                                              SQLite      Plugins     Scheduler
                                            (history,    (13 tools)    (cron)
                                             memory)
                                                             │
                                              ┌──────────────┼──────────────┐
                                           Skills        Sub-agent      TaskResult
                                       (5 task types)  (decomposition)  (tracking)
```

### Agent Flow

```
User Message → Skill Classifier → Matched Skill (research/coding/sysadmin/...)
                                        ↓
                              Task Decomposer (LLM)
                              ↓               ↓
                        Simple task      Complex task
                              ↓               ↓
                     Single tool loop    Decompose → Sub-tasks
                     (budget-aware)      ↓         ↓        ↓
                                     Sub-agent  Sub-agent  Sub-agent
                                     (skill A)  (skill B)  (skill C)
                                         ↓         ↓        ↓
                                          Synthesize results
                                                ↓
                                          Final Response + TaskResult
```

## Yêu cầu hệ thống

- Ubuntu 22.04 (hoặc Linux tương đương)
- 2+ CPU cores, 4GB+ RAM
- Docker & Docker Compose
- Số điện thoại Signal (hoặc link thiết bị phụ)
- Anthropic API key (trực tiếp hoặc qua proxy bên thứ 3)

## Cài đặt nhanh

```bash
git clone https://github.com/Ericnguyen89/helmes-deploy.git
cd helmes-deploy
chmod +x deploy.sh
./deploy.sh
```

Script `deploy.sh` sẽ tự động:
1. Kiểm tra hệ thống (RAM, disk, CPU)
2. Cài Docker nếu chưa có
3. Tạo file `.env` và hỏi thông tin cấu hình
4. Build & khởi chạy Docker containers
5. Cài systemd service để tự khởi động khi reboot

## Cấu hình

Copy `.env.example` thành `.env` và điền thông tin:

```bash
cp .env.example .env
nano .env
```

### Cấu hình cơ bản

| Biến | Mô tả |
|---|---|
| `SIGNAL_PHONE_NUMBER` | Số điện thoại Signal (VD: `+84901234567`) |
| `LLM_PROVIDER` | Provider active: `anthropic` (mặc định) / `openai` / `gemini` |
| `ADMIN_NUMBERS` | Số điện thoại admin, phân cách bằng dấu phẩy |
| `ALLOWED_NUMBERS` | `*` = mọi người, hoặc danh sách số được phép |

### Cấu hình Multi-Provider (Claude / OpenAI / Gemini)

Helmes hỗ trợ 3 nhà cung cấp LLM. Đặt `LLM_PROVIDER` để chọn provider mặc định, và điền API key tương ứng. Bạn có thể đổi model/provider lúc đang chạy bằng lệnh `/model` (provider được tự động nhận diện từ tên model).

| Provider | Biến | Mô tả | Mặc định |
|---|---|---|---|
| **Anthropic** | `ANTHROPIC_API_KEY` | API key (hoặc key proxy) | |
| | `ANTHROPIC_BASE_URL` | URL proxy bên thứ 3 (để trống = API chính thức) | |
| | `ANTHROPIC_MODEL` | VD: `claude-sonnet-4-20250514`, `claude-opus-4-6-thinking` | `claude-sonnet-4-20250514` |
| **OpenAI** | `OPENAI_API_KEY` | API key OpenAI | |
| | `OPENAI_BASE_URL` | URL tuỳ chỉnh (Azure/proxy) — để trống = chính thức | |
| | `OPENAI_MODEL` | VD: `gpt-4o`, `gpt-4.1`, `o3-mini` | `gpt-4o` |
| **Gemini** | `GEMINI_API_KEY` | API key ([lấy tại đây](https://aistudio.google.com/apikey)) | |
| | `GEMINI_BASE_URL` | Để trống = endpoint OpenAI-compatible của Google | |
| | `GEMINI_MODEL` | VD: `gemini-2.0-flash`, `gemini-1.5-pro` | `gemini-2.0-flash` |

**Cách hoạt động:**
- Claude dùng SDK Anthropic gốc (hỗ trợ thinking models).
- OpenAI và Gemini đều dùng SDK OpenAI — Gemini có endpoint OpenAI-compatible nên dùng chung code.
- Conversation history dùng format trung lập (canonical), mỗi provider tự convert → có thể **đổi provider giữa cuộc hội thoại** mà không mất context.

**Ví dụ đổi model qua Signal (admin):**
```
/model gpt-4o                    → chuyển sang OpenAI GPT-4o
/model gemini-2.0-flash          → chuyển sang Google Gemini
/model claude-opus-4-6-thinking  → quay lại Claude (thinking)
```
> Lưu ý: muốn đổi sang provider nào thì API key của provider đó phải được cấu hình sẵn trong `.env`.

### Cấu hình tools

| Biến | Mô tả | Mặc định |
|---|---|---|
| `TOOLS_ENABLED` | Bật/tắt tool execution | `true` |
| `TOOLS_ADMIN_ONLY` | Chỉ admin dùng tools | `false` |
| `WORKSPACE_DIR` | Thư mục làm việc | `/workspace` |
| `TOOL_TIMEOUT` | Timeout cho mỗi tool (giây) | `120` |
| `MAX_TOOL_ITERATIONS` | Số vòng tool call tối đa | `30` |
| `THINKING_BUDGET` | Token budget cho thinking models | `10000` |

### Cấu hình context & memory

| Biến | Mô tả | Mặc định |
|---|---|---|
| `MAX_CONVERSATION_LENGTH` | Tin nhắn tối đa trong history | `50` |
| `CONTEXT_SUMMARIZE_THRESHOLD` | Tự động tóm tắt khi vượt n tin nhắn | `20` |
| `CONTEXT_KEEP_RECENT` | Giữ lại n tin nhắn gần nhất khi tóm tắt | `6` |
| `RATE_LIMIT_PER_HOUR` | Giới hạn tin nhắn/giờ (0 = không giới hạn) | `30` |

### Cấu hình Gmail (gửi email)

| Biến | Mô tả |
|---|---|
| `GMAIL_ADDRESS` | Địa chỉ Gmail gửi đi |
| `GMAIL_APP_PASSWORD` | App Password (KHÔNG phải mật khẩu thường) |

**Cách tạo App Password:**
1. Vào [Google Account](https://myaccount.google.com/) → Security → 2-Step Verification (bật nếu chưa bật)
2. Tìm "App Passwords" → Tạo mới → Chọn "Other" → Đặt tên "Helmes"
3. Copy mật khẩu 16 ký tự (bỏ dấu cách khi paste vào `.env`)

### Cấu hình Search Engine

| Biến | Mô tả | Mặc định |
|---|---|---|
| `SEARCH_ENGINE` | `duckduckgo` hoặc `google` | `duckduckgo` |
| `GOOGLE_API_KEY` | Google API key (chỉ cần khi dùng Google) | |
| `GOOGLE_CSE_ID` | Google Custom Search Engine ID | |

**Cách thiết lập Google Search:**
1. Vào [Google Cloud Console](https://console.cloud.google.com/apis/credentials) → Create Credentials → API Key
2. Enable "Custom Search JSON API" trong [API Library](https://console.cloud.google.com/apis/library)
3. Vào [Programmable Search Engine](https://programmablesearchengine.google.com/) → Tạo mới → Chọn "Search the entire web" → Lấy **Search engine ID**
4. Cập nhật `.env`:
```env
SEARCH_ENGINE=google
GOOGLE_API_KEY=AIzaSy...your-key...
GOOGLE_CSE_ID=a1b2c3d4e5f6g7h8i
```

> Google Custom Search cho 100 queries miễn phí/ngày. Khi hết quota sẽ tự động fallback về DuckDuckGo.

## Đăng ký Signal

Sau khi deploy, chọn một trong hai cách:

**Cách 1: Link thiết bị phụ (khuyên dùng)**
```bash
./deploy.sh link
# Mở Signal trên điện thoại → Settings → Linked Devices → quét QR code
./deploy.sh restart
```

**Cách 2: Đăng ký số mới**
```bash
./deploy.sh register
# Làm theo hướng dẫn: nhập captcha → nhận mã SMS → xác nhận
./deploy.sh restart
```

## Quản lý

```bash
./deploy.sh status     # Xem trạng thái services
./deploy.sh logs       # Xem log realtime
./deploy.sh restart    # Restart services
./deploy.sh stop       # Dừng services
./deploy.sh uninstall  # Xoá containers & images (giữ dữ liệu)
```

Services tự khởi động khi VPS reboot nhờ systemd (`helmes-agent.service`).

## Lệnh chat trong Signal

| Lệnh | Mô tả | Quyền |
|---|---|---|
| `/help` | Hiện danh sách lệnh | Tất cả |
| `/reset` | Xoá lịch sử hội thoại | Tất cả |
| `/ping` | Kiểm tra agent hoạt động | Tất cả |
| `/info` | Xem thống kê hội thoại + skills loaded | Tất cả |
| `/status` | Xem stats task gần nhất (tokens, duration, sub-tasks) | Tất cả |
| `/memory` | Xem danh sách bộ nhớ dài hạn | Tất cả |
| `/schedule` | Xem danh sách scheduled tasks | Tất cả |
| `/system <prompt>` | Đặt system prompt tuỳ chỉnh | Admin |
| `/model <name>` | Đổi model AI | Admin |

## Tools (13 công cụ)

Agent có thể tự quyết định sử dụng tool nào phù hợp với yêu cầu:

| Tool | Mô tả |
|---|---|
| `bash` | Chạy lệnh bash trên server |
| `file_read` | Đọc nội dung file |
| `file_write` | Ghi/tạo file |
| `python` | Thực thi code Python |
| `web_search` | Tìm kiếm internet (Google/DuckDuckGo) |
| `web_fetch` | Tải và đọc nội dung trang web (HTML + XML/sitemap) |
| `send_email` | Gửi email qua Gmail |
| `memory_save` | Lưu thông tin vào bộ nhớ dài hạn |
| `memory_recall` | Tìm kiếm thông tin đã lưu |
| `memory_delete` | Xoá thông tin đã lưu |
| `schedule_add` | Thêm scheduled task (cron syntax) |
| `schedule_list` | Xem danh sách scheduled tasks |
| `schedule_remove` | Xoá scheduled task |

## Skill System

Agent tự động phân loại task và load prompt phù hợp:

| Skill | Kích hoạt khi | Tool ưu tiên |
|---|---|---|
| `research` | Tìm kiếm, tra cứu, so sánh, tin tức | web_search, web_fetch |
| `coding` | Viết code, debug, deploy, git | bash, python, file_read/write |
| `sysadmin` | Server, docker, nginx, network, logs | bash, file_read/write |
| `data_analysis` | Phân tích dữ liệu, thống kê, báo cáo | python, bash, file_read |
| `general` | Câu hỏi đơn giản, hội thoại chung | all |

Mỗi skill bao gồm hướng dẫn hiệu quả riêng (VD: research skill hướng dẫn model chỉ fetch 2-3 trang, coding skill hướng dẫn viết code hoàn chỉnh trong 1 pass).

### Tạo skill mới

Tạo file `.md` trong `agent/skills/definitions/`:

```markdown
---
name: my_skill
description: Mô tả skill
tools: bash, python
---

## My Skill

Hướng dẫn cho agent khi thực hiện loại task này...
```

Thêm classifier rule trong `agent/skills/__init__.py`:

```python
_CLASSIFIER_RULES.append(("my_skill", re.compile(r"(keyword1|keyword2)", re.IGNORECASE)))
```

## Sub-agent Decomposition

Khi nhận task phức tạp, agent tự động:

1. **Phân tích** — LLM đánh giá task có cần tách không
2. **Tách** — Chia thành 2-4 sub-tasks, mỗi sub-task có skill riêng
3. **Thực thi** — Sub-tasks chạy song song (độc lập) hoặc tuần tự (phụ thuộc)
4. **Tổng hợp** — Kết quả được synthesize thành response mạch lạc

Mỗi sub-task có iteration budget riêng → không bao giờ 1 sub-task chiếm hết budget.

### Ví dụ

```
Bạn: Tìm hiểu về Next.js 15 và so sánh với Remix, sau đó viết một ví dụ hello world

→ Agent tách thành:
  Sub-task 1 (research): Tìm hiểu Next.js 15 features
  Sub-task 2 (research): Tìm hiểu Remix features
  Sub-task 3 (coding): Viết hello world example
→ Sub-tasks 1+2 chạy song song, sub-task 3 chạy sau
→ Tổng hợp thành response hoàn chỉnh
```

### Ví dụ sử dụng qua Signal

```
Bạn: Tìm giá Bitcoin hiện tại
→ Skill: research → Agent dùng web_search, trả lời kết quả

Bạn: Viết script Python tính fibonacci, lưu vào file
→ Skill: coding → Agent dùng file_write + python để tạo và test

Bạn: Kiểm tra disk space và memory trên server
→ Skill: sysadmin → Agent dùng bash, chạy df + free

Bạn: Mỗi sáng 8h gửi cho tôi tin tức công nghệ
→ Agent dùng schedule_add với cron "0 8 * * *"

Bạn: [Gửi ảnh] Ảnh này là gì?
→ Agent phân tích ảnh bằng Claude Vision
```

## Tạo plugin mới

Tạo file trong `agent/plugins/`:

```python
# agent/plugins/my_tool.py
from .base import ToolPlugin, ToolContext

class MyTool(ToolPlugin):
    name = "my_tool"
    description = "Mô tả tool của bạn"
    input_schema = {
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "Tham số 1",
            },
        },
        "required": ["param1"],
    }

    def execute(self, tool_input: dict, context: ToolContext) -> str:
        # context.workspace: thư mục làm việc
        # context.timeout: giới hạn thời gian
        # context.sender: số điện thoại người gửi
        return f"Kết quả: {tool_input['param1']}"
```

Plugin sẽ được tự động phát hiện và đăng ký khi agent khởi động. Không cần sửa code ở bất kỳ file nào khác.

## Cấu trúc dự án

```
helmes-deploy/
├── deploy.sh                # Script triển khai & quản lý
├── docker-compose.yml       # Docker services
├── helmes-agent.service     # Systemd service (auto-start on boot)
├── .env.example             # Template cấu hình
├── agent/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py              # Entry point, polling loop
│   ├── config.py            # Cấu hình từ biến môi trường
│   ├── signal_client.py     # Client gửi/nhận tin & ảnh Signal
│   ├── ai_engine.py         # Core engine + budget-aware tool loop (provider-agnostic)
│   ├── providers/           # Multi-provider LLM layer
│   │   ├── __init__.py      # Factory + provider detection
│   │   ├── base.py          # LLMProvider ABC + canonical types
│   │   ├── anthropic_provider.py  # Claude (native SDK)
│   │   └── openai_provider.py     # OpenAI + Gemini (OpenAI-compatible)
│   ├── sub_agent.py         # Sub-agent decomposition executor
│   ├── task_result.py       # Structured task result + token tracking
│   ├── store.py             # SQLite lưu hội thoại
│   ├── memory.py            # Persistent memory store
│   ├── summarizer.py        # Context summarization
│   ├── planner.py           # Task planning + tool efficiency prompt
│   ├── scheduler.py         # Cron-based task scheduler
│   ├── commands.py          # Xử lý lệnh slash (/help, /status, ...)
│   ├── tools.py             # Tool facade (delegates to plugins)
│   ├── skills/              # Skill system (DeerFlow-inspired)
│   │   ├── __init__.py      # SkillRegistry + classifier
│   │   └── definitions/     # Skill prompt files
│   │       ├── research.md
│   │       ├── coding.md
│   │       ├── sysadmin.md
│   │       ├── data_analysis.md
│   │       └── general.md
│   └── plugins/             # Plugin system
│       ├── __init__.py      # Auto-discovery registry
│       ├── base.py          # ToolPlugin base class
│       ├── bash_tool.py
│       ├── file_tools.py
│       ├── python_tool.py
│       ├── web_search_tool.py
│       ├── web_fetch_tool.py
│       ├── email_tool.py
│       ├── memory_tools.py
│       └── scheduler_tools.py
└── data/                    # Dữ liệu persistent (auto-generated)
    ├── signal-cli/          # Dữ liệu signal-cli
    └── agent/               # SQLite database
```

## Budget-aware Tool Loop

Hệ thống quản lý tool iterations thông minh, ngăn việc hết budget giữa chừng:

| Giai đoạn | Hành vi |
|---|---|
| 0–50% budget | Hoạt động bình thường |
| 50–70% budget | Thông báo: "Be efficient with remaining calls" |
| 70–90% budget | Cảnh báo: "Start wrapping up" |
| 90–97% budget | Khẩn cấp: "MUST respond NOW" |
| 97–100% budget | Force stop: bỏ tools, buộc model trả lời text |
| Fallback | Gọi thêm 1 lần không tools để tổng hợp kết quả |

## Cập nhật

```bash
cd helmes-deploy
git pull
docker compose up -d --build --force-recreate
```

## License

MIT
