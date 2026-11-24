# LAN Chat & File Sharing (UDP + TCP)

[![tests](https://github.com/KhoDaeng/lanchat-socket/actions/workflows/ci.yml/badge.svg)](https://github.com/KhoDaeng/lanchat-socket/actions/workflows/ci.yml)

Đồ án **Socket Programming** — ứng dụng chat peer-to-peer chạy trong console.
Mỗi máy chạy **cùng một chương trình**: vừa là client, vừa là server.

- **UDP 9999** → quảng bá sự hiện diện (`HELLO`) mỗi 3 giây, tự phát hiện peer, timeout 10 giây.
- **TCP `<port>`** → chat (framing theo độ dài) và gửi file (mỗi file một kết nối riêng, có tiến độ %).
- **Console UI** → dòng nhập luôn ở cuối màn hình; tin đến không làm mất chữ đang gõ.
- **Chỉ dùng thư viện chuẩn** của Python 3.8+ — không cần `pip install`.

---

## 1. Chạy nhanh trên một máy (3 cửa sổ)

```powershell
# từ thư mục gốc của repo
.\scripts\run_demo.ps1
```

Script mở 3 cửa sổ:

| Peer | TCP port | UDP |
|---|---|---|
| Quan | 5001 | 9999 |
| Minh | 5002 | 9999 |
| Huy  | 5003 | 9999 |

Không có LAN / broadcast bị chặn:

```powershell
.\scripts\run_demo.ps1 -Broadcast 127.255.255.255
```

Chạy thủ công từng instance:

```powershell
python -m lanchat --name Quan --port 5001
python -m lanchat --name Minh --port 5002
python -m lanchat --name Huy  --port 5003
```

Cũng có thể chạy trực tiếp file entry point (ví dụ khi bấm **Run** trong VS Code):

```powershell
python lanchat\__main__.py --name Quan --port 5001
```

> Luôn chạy từ **thư mục gốc** của repo. Không chạy `python lanchat\app.py`
> hay `protocol.py` — đó là các module nội bộ, không phải chương trình.

## 2. Chạy trên 2+ máy trong cùng LAN/Wi-Fi

```powershell
# Máy 1
python -m lanchat --name Quan --port 5000

# Máy 2
python -m lanchat --name Minh --port 6000
```

Nếu peer không xuất hiện trong `/list`:

1. Cho phép Python qua Windows Firewall (mạng **Private**), cả TCP và UDP.
   Cách nhanh: lần đầu chạy, bấm **Allow access**; hoặc:
   ```powershell
   New-NetFirewallRule -DisplayName "LAN Chat (Python)" -Direction Inbound `
     -Program "C:\Path\To\python.exe" -Action Allow
   ```
2. Kiểm tra hai máy cùng subnet (`ipconfig`), thử ping nhau.
3. Chỉ định broadcast address của subnet, ví dụ `--bcast 192.168.1.255`.
4. Một số Wi-Fi/AP chặn broadcast giữa client → dùng cáp LAN hoặc hotspot điện thoại.

---

## 3. Lệnh trong chương trình

| Lệnh | Ý nghĩa |
|---|---|
| `/list` | Danh sách peer online: số thứ tự, tên, IP, TCP port, trạng thái, số giây từ lần cuối |
| `/chat <tên|số>` | Mở (hoặc chuyển sang) chat với peer, kết nối TCP |
| `<văn bản>` | Gửi tin nhắn cho đối tác hiện tại |
| `/send <file>` | Gửi file cho đối tác hiện tại (luồng riêng, hiện 25/50/75/100%) |
| `/leave` | Gửi `BYE`, đóng chat hiện tại |
| `/status <online|away>` | Đổi trạng thái, gửi ngay qua UDP |
| `/help` | Danh sách lệnh |
| `/quit` | Gửi `BYE` trên mọi kết nối, dừng quảng bá, thoát |

Ví dụ một phiên:

```
> /list
[*] Online peers (2):
  1. Minh   192.168.1.12    tcp/6000   online    1s
  2. Huy    192.168.1.20    tcp/5000   away      2s
> /chat Minh
[*] Connected to Minh (192.168.1.12:6000).
[Quan] Chào Minh, sẵn sàng demo chưa?
[Minh] Rồi! Gửi mình slide nhé
[*] New message from Huy (1 unread)
> /chat Huy
[*] Switched to Huy.
[*] 1 unread message(s) from Huy:
   [Huy] router config xong rồi nhé
> /send docs/slides.pdf
[*] Sending slides.pdf (2.4 KB) to Huy ...
[*] Sending slides.pdf ... 25%
...
[*] Sent slides.pdf to Huy.
```

Nhận file: lưu vào `downloads/`, tên trùng tự đổi thành `slides (1).pdf`; file dở dang dùng đuôi `.part` và bị xoá nếu lỗi.

---

## 4. Giao thức (tóm tắt)

Chi tiết đầy đủ: [`docs/01-protocol-spec.md`](docs/01-protocol-spec.md).

| Frame | Định dạng | Ghi chú |
|---|---|---|
| `HI` | `HI\|<name>\|<tcp_port>\|<purpose>\|` | frame đầu tiên của **mọi** kết nối TCP; `purpose` = `chat` hoặc `file` |
| `MSG` | `MSG\|<nbytes>\|<nbytes UTF-8>` | `<nbytes>` là **số byte**, không phải số ký tự |
| `FILE` | `FILE\|<quoted-name>\|<size>\|<raw bytes>` | tên file percent-encode, an toàn với `\|`, dấu cách, tiếng Việt |
| `BYE` | `BYE\|` | kết thúc chat / thoát |

Điểm thiết kế quan trọng:

- **Length-prefixed**: TCP là dòng byte, một `recv()` có thể trả nửa frame hoặc hai frame dính nhau → `FrameReader` đệm và đọc đủ.
- **Percent-encoded filename**: giữ đúng tinh thần `FILE|name|size|` của đề nhưng không vỡ khi tên file chứa `|` (ví dụ: `báo cáo | final.pdf`).
- **`HI` có `purpose`**: bên nhận biết ngay kết nối là `chat` hay `file`, không phải chờ frame kế tiếp. Nhờ vậy bên nhận chat có thể là người gửi tin đầu tiên.
- **Mỗi file một kết nối TCP riêng** → không chèn `FILE` vào giữa stream chat, chat không bị block.
- **Giới hạn phòng thủ**: header ≤ 4096 byte, tin nhắn ≤ 1 MiB, frame lạ → đóng riêng kết nối đó, chương trình vẫn chạy.

---

## 5. Kiến trúc & mô hình luồng

Chi tiết + sơ đồ: [`docs/02-architecture.md`](docs/02-architecture.md).

```
main (keyboard) ── commands ──> App ──> ChatSession ──> TCP peer
                                   ├──> FileService ──> TCP peer (file)
udp-presence (3 s)  ───────────────┘
udp-listener        ──> PeerTable (lock) ──> online/offline events
tcp-acceptor        ──> 1 handler thread / connection
chat-rx-<peer>      ──> hiển thị tin, đếm unread
file-tx-<peer>      ──> gửi file, progress callback
```

| Dữ liệu chia sẻ | Bảo vệ bởi |
|---|---|
| `PeerTable` | `threading.RLock` riêng |
| `ChatHistory` + unread | `threading.RLock` riêng |
| `ChatSession._conns` | `threading.RLock` riêng |
| Màn hình / dòng nhập | `Console._lock` |

Quy tắc chống trùng kết nối khi hai bên cùng `/chat` nhau: **kết nối do bên có tên nhỏ hơn (lexicographic) khởi tạo sẽ thắng**; cả hai bên áp dụng cùng quy tắc nên luôn hội tụ về một socket.

---

## 6. Cấu trúc repo & phân công

```
lanchat/
  __main__.py        CLI (argparse), bootstrap console
  app.py             nối các service, callback, shutdown
  config.py          hằng số (port, timeout, chunk, giới hạn)
  protocol.py        HELLO/HI/MSG/FILE/BYE + FrameReader  [B]
  discovery/         peers.py, presence.py, listener.py  [A]
  chat/              server.py, session.py, files.py, history.py  [B + A]
  ui/                console.py (redraw + lock), commands.py       [C]
tests/               26 unit + integration tests
scripts/             run_demo.ps1, test.ps1
docs/                protocol spec, architecture, test plan, report, demo, team plan
```

| Vai | Phụ trách | Điểm rubric |
|---|---|---|
| **A** | UDP discovery, status, timeout, gửi/nhận file, Wireshark UDP | 30 |
| **B** | TCP acceptor, framing, `/chat`, `/leave`, unread, Wireshark TCP | 30 |
| **C** | Console UI, lock màn hình, command, lỗi, test, README, báo cáo | 40 |

Kế hoạch 3 ngày + quy trình Git: [`docs/06-team-plan.md`](docs/06-team-plan.md) ·
Quy ước đóng góp: [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## 7. Kiểm thử

```powershell
python -m unittest discover -s tests -v
# hoặc
.\scripts\test.ps1
```

39 test, không cần mạng:

- `test_protocol.py` — frame bị cắt, 2 frame dính, UTF-8 nhiều byte, tên file chứa `|`, frame rác, header quá dài.
- `test_peers.py` — online/offline, đổi status, timeout đúng 10 s, tìm theo tên/số/tiền tố.
- `test_files.py` — lưu file, xoá `.part` khi lỗi, chống path traversal, tên trùng.
- `test_integration.py` — TCP thật: chat vào/ra, BYE, file round-trip, frame rác không làm chết server.
- `test_entrypoints.py` — `python -m lanchat` và `python lanchat\__main__.py` đều khởi động được (chống lỗi import).
- `test_commands.py` — console gọi lệnh đúng 1 tham số, `/list` `/status` chat thường đi đúng chỗ (chống lỗi `TypeError`).
- `test_presence_messages.py` — peer khởi động với `--status away` hiện `is away`, không hiện nhầm `is online`.

Kịch bản test tay trên 2 máy + 5 nhánh lỗi: [`docs/03-test-plan.md`](docs/03-test-plan.md).

---

## 8. Wireshark

```text
UDP discovery : udp.port == 9999
TCP handshake : tcp.port == 6000 && tcp.flags.syn == 1
Chat stream   : chọn packet TCP -> Follow -> TCP Stream
File transfer : tcp.stream == 1   (kết nối thứ hai, kết thúc bằng FIN)
Kết thúc      : tcp.flags.fin == 1 || tcp.flags.reset == 1
```

Hướng dẫn bắt gói + checklist ảnh: [`docs/wireshark/README.md`](docs/wireshark/README.md).

---

## 9. Hạn chế đã biết

- Console chỉ hỗ trợ một dòng nhập; dòng dài hơn chiều rộng terminal không tự wrap đẹp.
- Không mã hoá — chỉ dùng trong LAN tin cậy.
- Tên peer nên là duy nhất; trùng tên sẽ ghi đè trong bảng peer.
- Không resume file khi mất mạng giữa chừng (file `.part` bị xoá, gửi lại từ đầu).
- Chưa có GUI (đề cho phép console).

---

## 10. Demo 10 phút

Kịch bản chi tiết theo từng phút: [`docs/05-demo-script.md`](docs/05-demo-script.md).

---

## 11. Lỗi thường gặp

| Lỗi | Nguyên nhân | Cách sửa |
|---|---|---|
| `ModuleNotFoundError: No module named 'config'` | chạy sai thư mục hoặc import bị sửa thành tuyệt đối | `cd` về thư mục gốc, chạy `python -m lanchat ...` |
| `ImportError: attempted relative import with no known parent package` | chạy `python lanchat\app.py` hoặc `protocol.py` | chạy `python -m lanchat` hoặc `python lanchat\__main__.py` |
| `TypeError: handle_line() missing 1 required positional argument` | bản cũ (trước commit sửa lỗi) | `git pull` để lấy bản mới |
| `[!] Cannot start ...` | TCP port đang bận | đổi `--port 5100` |
| `/list` trống | firewall / khác subnet / AP chặn broadcast | mở firewall, thử `--bcast 127.255.255.255` |
| Chữ tiếng Việt lỗi font | console dùng bảng mã cũ | `chcp 65001` |
| Script `.ps1` bị chặn | ExecutionPolicy | `powershell -ExecutionPolicy Bypass -File .\scripts\run_demo.ps1` |

## License

MIT — xem [`LICENSE`](LICENSE).
