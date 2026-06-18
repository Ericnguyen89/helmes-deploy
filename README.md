# Helmes Agent

AI Agent sử dụng Signal làm giao diện chat, kết nối với Claude API (Anthropic).

## Kiến trúc

```
Signal App ──► Signal Server ──► signal-cli-rest-api ──► Helmes Agent ──► Claude API
                                    (Docker)              (Python)
                                                             │
                                                         SQLite DB
                                                    (lịch sử hội thoại)
```

## Yêu cầu hệ thống

- Ubuntu 22.04 (hoặc Linux tương đương)
- 2+ CPU cores, 4GB+ RAM
- Docker & Docker Compose
- Số điện thoại Signal (hoặc link thiết bị phụ)
- Anthropic API key (trực tiếp hoặc qua proxy bên thứ 3)

## Cài đặt nhanh

```bash
git clone https://github.com/your-username/hemes-agent.git
cd hemes-agent
chmod +x deploy.sh
./deploy.sh
```

Script `deploy.sh` sẽ tự động:
1. Kiểm tra hệ thống (RAM, disk, CPU)
2. Cài Docker nếu chưa có
3. Tạo file `.env` và hỏi thông tin cấu hình
4. Build & khởi chạy Docker containers

## Cấu hình

Copy `.env.example` thành `.env` và điền thông tin:

```bash
cp .env.example .env
nano .env
```

| Biến | Mô tả |
|---|---|
| `SIGNAL_PHONE_NUMBER` | Số điện thoại Signal (VD: `+84901234567`) |
| `ANTHROPIC_API_KEY` | API key Anthropic (hoặc key proxy) |
| `ANTHROPIC_BASE_URL` | URL proxy bên thứ 3 (để trống = API chính thức) |
| `ANTHROPIC_MODEL` | Model AI sử dụng (VD: `claude-sonnet-4-20250514`) |
| `ADMIN_NUMBERS` | Số điện thoại admin, phân cách bằng dấu phẩy |
| `ALLOWED_NUMBERS` | `*` = mọi người, hoặc danh sách số được phép |
| `MAX_CONVERSATION_LENGTH` | Số tin nhắn tối đa trong lịch sử hội thoại |
| `RATE_LIMIT_PER_HOUR` | Giới hạn tin nhắn/giờ/người (0 = không giới hạn) |

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

## Lệnh chat trong Signal

| Lệnh | Mô tả | Quyền |
|---|---|---|
| `/help` | Hiện danh sách lệnh | Tất cả |
| `/reset` | Xoá lịch sử hội thoại | Tất cả |
| `/ping` | Kiểm tra agent hoạt động | Tất cả |
| `/info` | Xem thống kê hội thoại | Tất cả |
| `/system <prompt>` | Đặt system prompt tuỳ chỉnh | Admin |
| `/model <name>` | Đổi model AI | Admin |

## Cấu trúc dự án

```
hemes-agent/
├── deploy.sh                # Script triển khai & quản lý
├── docker-compose.yml       # Docker services
├── .env.example             # Template cấu hình
├── agent/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py              # Entry point, polling loop
│   ├── config.py            # Cấu hình từ biến môi trường
│   ├── signal_client.py     # Client gửi/nhận tin Signal
│   ├── ai_engine.py         # Kết nối Claude API
│   ├── store.py             # SQLite lưu hội thoại
│   └── commands.py          # Xử lý lệnh slash
└── data/                    # Dữ liệu persistent (auto-generated)
    ├── signal-cli/          # Dữ liệu signal-cli
    └── agent/               # SQLite database
```

## License

MIT
