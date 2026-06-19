# Helmes Agent

AI Agent framework sử dụng Signal làm giao diện chat, kết nối với Claude API (Anthropic). Hỗ trợ tool execution, persistent memory, scheduled tasks, multi-modal (vision), và nhiều hơn nữa.

> **Lưu ý:** Helmes Agent là một agent framework độc lập, không liên quan đến Hermes model của Nous Research.

## Tính năng

- **13 tools tích hợp**: bash, file read/write, python, web search, web fetch, email, memory, scheduler
- **Plugin system**: Dễ dàng thêm tool mới bằng cách tạo file plugin
- **Persistent memory**: Agent nhớ thông tin qua các cuộc hội thoại
- **Scheduled tasks**: Lên lịch chạy task tự động (cron syntax)
- **Context summarization**: Tự động tóm tắt khi hội thoại dài
- **Multi-modal**: Nhận và phân tích ảnh qua Signal (Claude Vision)
- **Task planning**: Agent tự lập kế hoạch cho task phức tạp
- **Dual search engine**: Google Custom Search hoặc DuckDuckGo
- **Gmail integration**: Gửi email kết quả qua Gmail SMTP

## Kiến trúc

```
Signal App ──► Signal Server ──► signal-cli-rest-api ──► Helmes Agent ──► Claude API
                                    (Docker)              (Python)
                                                             │
                                                     ┌──────┼──────┐
                                                  SQLite   Plugins  Scheduler
                                                (history,  (13 tools) (cron)
                                                 memory)
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
| `ANTHROPIC_API_KEY` | API key Anthropic (hoặc key proxy) |
| `ANTHROPIC_BASE_URL` | URL proxy bên thứ 3 (để trống = API chính thức) |
| `ANTHROPIC_MODEL` | Model AI (VD: `claude-sonnet-4-20250514`, `claude-opus-4-6-thinking`) |
| `ADMIN_NUMBERS` | Số điện thoại admin, phân cách bằng dấu phẩy |
| `ALLOWED_NUMBERS` | `*` = mọi người, hoặc danh sách số được phép |

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
| `/info` | Xem thống kê hội thoại | Tất cả |
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
| `web_fetch` | Tải và đọc nội dung trang web |
| `send_email` | Gửi email qua Gmail |
| `memory_save` | Lưu thông tin vào bộ nhớ dài hạn |
| `memory_recall` | Tìm kiếm thông tin đã lưu |
| `memory_delete` | Xoá thông tin đã lưu |
| `schedule_add` | Thêm scheduled task (cron syntax) |
| `schedule_list` | Xem danh sách scheduled tasks |
| `schedule_remove` | Xoá scheduled task |

### Ví dụ sử dụng qua Signal

```
Bạn: Tìm giá Bitcoin hiện tại
→ Agent dùng web_search, trả lời kết quả

Bạn: Viết script Python tính fibonacci, lưu vào file
→ Agent dùng file_write + python để tạo và test

Bạn: Mỗi sáng 8h gửi cho tôi tin tức công nghệ
→ Agent dùng schedule_add với cron "0 8 * * *"

Bạn: Gửi kết quả qua email tuannm@gmail.com
→ Agent dùng send_email

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
│   ├── ai_engine.py         # Kết nối Claude API + tool loop
│   ├── store.py             # SQLite lưu hội thoại
│   ├── memory.py            # Persistent memory store
│   ├── summarizer.py        # Context summarization
│   ├── planner.py           # Task planning prompt
│   ├── scheduler.py         # Cron-based task scheduler
│   ├── commands.py          # Xử lý lệnh slash
│   ├── tools.py             # Tool facade (delegates to plugins)
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

## Cập nhật

```bash
cd helmes-deploy
git pull
docker compose up -d --build --force-recreate
```

## License

MIT
