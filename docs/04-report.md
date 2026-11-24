# Báo cáo đồ án — LAN Chat & File Sharing

> **Mục tiêu 5–10 trang.** Đây là khung đã điền sẵn phần kỹ thuật; các mục có
> `[ĐIỀN]` cần số liệu/ảnh thật của nhóm. Người merge: **C**.
>
> Phân công viết: **A** → 4.1, 4.3, ảnh UDP · **B** → 3, 4.2, ảnh TCP ·
> **C** → 1, 2, 4.4, 5, 6, 7, 8 và format.

---

## 1. Giới thiệu

Đồ án xây dựng ứng dụng chat và chia sẻ file peer-to-peer chạy trong console.
Mỗi máy chạy cùng một chương trình, vừa là client vừa là server. Chương trình
tự khám phá người dùng trong LAN bằng UDP broadcast, chat và gửi file bằng TCP.

Mục tiêu:

- Dùng đúng chỗ mạnh của từng giao thức: UDP cho hiện diện (mất gói không sao),
  TCP cho dữ liệu không được mất (chat, file).
- Tự thiết kế giao thức tầng ứng dụng có framing trên TCP.
- Xử lý đồng thời bằng thread, đảm bảo UI không bị treo và tin đến không làm
  mất chữ đang gõ.
- Xử lý lỗi: peer offline, crash, mất mạng giữa lúc truyền file, frame sai.

Phạm vi: Python 3.8+, chỉ thư viện chuẩn, console UI. Không mã hoá, không lưu
lịch sử ra đĩa, không có server trung tâm.

`[ĐIỀN]` ảnh 3 cửa sổ demo + sơ đồ mạng 2 máy.

---

## 2. Kiến trúc và mô hình luồng

### 2.1 Thành phần

| Thành phần | Vai trò |
|---|---|
| `PresenceService` | gửi `HELLO` mỗi 3 s, gửi ngay khi đổi status |
| `DiscoveryListener` | nhận `HELLO`, cập nhật bảng peer, quét timeout 10 s |
| `PeerTable` | dữ liệu peer + lock, sinh sự kiện online/offline/status |
| `ChatServer` | TCP acceptor, mỗi kết nối một handler thread |
| `ChatSession` | quản lý kết nối chat, partner hiện tại, unread, chống trùng kết nối |
| `FileService` | gửi/nhận file, tiến độ, `.part`, tên an toàn |
| `Console` | đọc phím, giữ buffer, redraw dòng nhập, lock màn hình |
| `App` | nối các thành phần, callback, shutdown |

### 2.2 Luồng

| Thread | Chờ | Việc |
|---|---|---|
| main | bàn phím | nhập lệnh, gửi tin |
| udp-presence | 3 s | broadcast `HELLO` |
| udp-listener | datagram | cập nhật peer, timeout |
| tcp-acceptor | kết nối mới | tạo handler |
| chat-rx / tcp-conn | dữ liệu | hiển thị tin / nhận file |
| file-tx | đĩa + socket | gửi file, báo % |

`[ĐIỀN]` dán sơ đồ trong `docs/02-architecture.md` (mermaid export PNG).

### 2.3 Đồng bộ

Bốn lock độc lập: `PeerTable`, `ChatHistory`, `ChatSession`, `Console`.
Không module nào giữ lock của mình trong khi gọi `Console.show()` của module
khác, nên không có deadlock. Chi tiết: mục 4 của `docs/02-architecture.md`.

---

## 3. Thiết kế giao thức

### 3.1 UDP

```
HELLO|<name>|<tcp_port>|<status>          ví dụ: HELLO|Minh|6000|away
```

Gửi mỗi 3 s, timeout 10 s (≈ 3 gói liên tiếp). Bỏ qua gói của chính mình bằng
cặp `(name, tcp_port)`. Nhiều instance trên cùng máy dùng `SO_REUSEADDR` để
cùng bind UDP 9999.

### 3.2 TCP framing

| Frame | Định dạng |
|---|---|
| `HI` | `HI\|<name>\|<tcp_port>\|<chat\|file>\|` |
| `MSG` | `MSG\|<nbytes>\|<UTF-8>` |
| `FILE` | `FILE\|<quoted-name>\|<size>\|<raw>` |
| `BYE` | `BYE\|` |

Quyết định thiết kế:

1. **Length-prefix** thay vì newline: text chat có thể chứa newline, file là
   nhị phân; độ dài là cách duy nhất chắc chắn.
2. **Độ dài tính bằng byte UTF-8**, không phải ký tự. Ví dụ một câu 30 ký tự
   tiếng Việt là 35 byte; nếu dùng `len(text)` bên nhận sẽ đọc thiếu.
3. **Percent-encode tên file**: giữ format pipe của đề nhưng tên file chứa
   `|`, dấu cách, tiếng Việt không làm vỡ header. `quote(basename, safe="")`.
4. **`HI` bắt buộc** ở đầu mọi kết nối, kèm `purpose` (`chat`/`file`): bên nhận
   biết ai gọi, port nào và kết nối dùng để làm gì ngay sau frame đầu tiên.
5. **Mỗi file một kết nối riêng**: không chèn frame `FILE` khổng lồ vào stream
   chat, không cần lock socket trong suốt quá trình truyền.
6. **Giới hạn phòng thủ**: header ≤ 4096 byte, `MSG` ≤ 1 MiB, frame lạ → đóng
   riêng kết nối đó.

`[ĐIỀN]` bảng đo thực tế: kích thước file, thời gian truyền, tốc độ.

### 3.3 Chống trùng kết nối

Nếu hai bên cùng `/chat` nhau, kết nối do tên nhỏ hơn (lexicographic) khởi tạo
thắng. Cả hai bên áp dụng cùng quy tắc nên hội tụ về một socket. `[ĐIỀN]` log
minh hoạ nếu có.

---

## 4. Triển khai

### 4.1 Khám phá và trạng thái (A)

- `PresenceService` dùng socket ephemeral + `SO_BROADCAST`, không bind 9999.
- `DiscoveryListener` bind `("", 9999)`, `SO_REUSEADDR`/`SO_REUSEPORT`, timeout
  poll 0,5 s để có thể dừng thread.
- Bảng peer lưu `(name, ip, tcp_port, status, last_seen)`; mỗi giây sweep.
- `/status away` đánh thức thread broadcast, gửi ngay không chờ 3 s.

`[ĐIỀN]` ảnh `/list` 3 peer + ảnh Wireshark `udp.port == 9999`.

### 4.2 Chat (B)

- Acceptor bind `("", tcp_port)`, `listen(16)`, mỗi kết nối một thread.
- Frame đầu phải `HI` kèm `purpose`; chat → `ChatSession`, file → `FileService`.
- `ChatSession` giữ `dict[name] = connection`, partner hiện tại, lịch sử và
  unread. Tin từ người không phải partner được lưu, in
  `[*] New message from X (n unread)`.
- `/leave` gửi `BYE` + đóng; peer nhận `BYE` in `X left the chat`.
- Lỗi socket/`recv` → xoá kết nối, partner về `None`, in lý do.

`[ĐIỀN]` ảnh Wireshark bắt tay 3 bước + ảnh 2 cửa sổ chat.

### 4.3 Gửi file (A)

- `/send` tạo thread riêng: TCP connect mới → `HI` → `FILE` header → gửi 64 KiB
  mỗi lần.
- Tiến độ in theo bậc 25/50/75/100% qua `Console.show()` để không phá dòng
  đang gõ.
- Bên nhận ghi `downloads/<name>.part`; đủ byte mới `os.replace()` sang tên
  chính thức; lỗi → xoá `.part`.
- Tên nhận được lọc `basename`, ký tự điều khiển, tên reserved Windows; trùng
  tên → `name (1).ext`.

`[ĐIỀN]` ảnh gửi 5 MB 100% + ảnh thư mục `downloads/` + ảnh Wireshark stream
file.

### 4.4 Giao diện console (C)

- Đọc từng phím: `msvcrt.getwch()` (Windows), `termios` + `tty` (Linux/macOS).
- Giữ `buffer`, mỗi lần tin đến: `\r\033[K` → in tin → vẽ lại `> ` + buffer.
- Một `RLock` bảo vệ màn hình; main thread và mọi thread mạng đều đi qua
  `Console.show()`.
- Ctrl+C / `/quit` khôi phục terminal (`termios.tcsetattr`), gửi `BYE`.

`[ĐIỀN]` 2 ảnh trước/sau khi tin đến lúc đang gõ.

---

## 5. Kiểm thử và xử lý lỗi

- 39 test tự động: protocol, peer table, file, integration TCP thật.
- Kịch bản tay 1 máy (M01–M14), 2 máy (N01–N08), 5 nhánh lỗi E01–E05.
- Kết quả: `[ĐIỀN] __/39 automated, __/__ manual`.

| Nhánh lỗi | Cơ chế xử lý |
|---|---|
| `/chat` peer vừa offline | `connect()` timeout 5 s / refused → báo lỗi, không crash |
| Peer crash giữa chat | `recv()==b""`/RST → `ConnectionClosed` → dọn kết nối |
| Mất mạng khi gửi file | `OSError` ở sender; receiver thiếu byte → xoá `.part` |
| Frame sai (`nc` gửi rác) | `ProtocolError` → đóng kết nối đó, in log |
| Sai lệnh / file không tồn tại | in usage / `File not found`, không traceback |

`[ĐIỀN]` bảng kết quả test thật + link ảnh.

---

## 6. Khó khăn và giải pháp

Mỗi thành viên viết 1–2 mục, giữ nguyên giọng kể thực tế:

1. **Ranh giới frame TCP** — lần đầu dùng `recv(1024)` và tưởng 1 lần là 1 tin;
   tin tiếng Việt dài bị cắt, 2 tin ngắn bị dính. Giải pháp: `FrameReader` có
   buffer + đọc đủ theo độ dài; test gửi từng byte.
2. **Nhiều instance trên một máy** — bind UDP 9999 lần thứ hai báo lỗi. Giải
   pháp: `SO_REUSEADDR` (+ `SO_REUSEPORT`), bind `("", 9999)`; kiểm chứng
   broadcast được nhân bản cho cả 3 socket.
3. **Mất chữ đang gõ** — in tin từ thread khác đè lên dòng nhập. Giải pháp:
   một lock màn hình + `\r\033[K` + redraw prompt/buffer.
4. **File làm treo chat** — gửi file trên cùng socket khiến chat đứng. Giải
   pháp: kết nối TCP riêng cho mỗi file.
5. **Tên file chứa `|`** — header pipe bị vỡ. Giải pháp: percent-encode.
6. **Hai bên cùng `/chat`** — sinh 2 kết nối rồi cùng chết. Giải pháp: quy tắc
   tên nhỏ hơn thắng.
7. `[ĐIỀN]` khó khăn riêng của A/B/C.

---

## 7. Kết luận và hướng phát triển

Đã hoàn thành: discovery UDP, status, chat TCP nhiều peer, unread, gửi file có
tiến độ, console UI không mất chữ, xử lý 5 nhóm lỗi, 39 test tự động.

Hướng phát triển: mã hoá TLS, resume file, gửi nhiều file song song có hàng
đợi, GUI, lưu lịch sử, chat nhóm, NAT traversal.

`[ĐIỀN]` bài học rút ra của nhóm.

---

## 8. Phân công

| Thành viên | MSSV | Phần việc | % |
|---|---|---|---|
| A | `[ĐIỀN]` | discovery, status, file, Wireshark UDP, mục 4.1/4.3 | 33 |
| B | `[ĐIỀN]` | protocol, acceptor, chat, unread, Wireshark TCP, mục 3/4.2 | 33 |
| C | `[ĐIỀN]` | console UI, lỗi, test, README, merge báo cáo, mục 1/2/5/6/7 | 34 |

---

## Phụ lục

- A. Ảnh Wireshark (UDP broadcast, TCP handshake, chat stream, file stream).
- B. Bảng test đầy đủ (`docs/03-test-plan.md`).
- C. Hướng dẫn chạy (`README.md`).
