# Wireshark — hướng dẫn bắt gói

Mục tiêu: có bằng chứng thật cho 4 thứ trong báo cáo:

1. UDP broadcast `HELLO` tới `255.255.255.255:9999`.
2. Bắt tay 3 bước TCP (SYN, SYN-ACK, ACK).
3. Stream chat bắt đầu bằng `HI|...` rồi `MSG|...`.
4. Kết nối file riêng, kết thúc bằng FIN; so sánh với RST khi peer crash.

> Bắt trên card mạng thật khi chạy **2 máy**. Bắt loopback chỉ dùng làm tư
> liệu thêm.

---

## 1. Chuẩn bị

- 2 máy cùng LAN, đã mở firewall.
- Cài Wireshark, chọn đúng interface đang dùng (Wi-Fi/Ethernet).
- Chạy trước để chắc app hoạt động, rồi mới bắt gói.

Kiểm tra nhanh IP:

```powershell
ipconfig
```

Ví dụ: Quan `192.168.1.10` TCP 5000 · Minh `192.168.1.12` TCP 6000.

---

## 2. Bắt gói theo giai đoạn

### 2.1 Discovery (UDP)

Filter:

```text
udp.port == 9999
```

Thao tác:

1. Bắt đầu capture.
2. Chạy app trên máy kia, hoặc đổi `/status away`.
3. Dừng sau ~5 gói.

Ảnh cần thấy:

- Destination `255.255.255.255`, port 9999.
- Payload đọc được: `HELLO|Minh|6000|online`.
- Gói `away` xuất hiện ngay sau `/status away`, không chờ 3 giây.
- Nếu chạy 1 máy: đích `127.255.255.255` (loopback) cũng chấp nhận.

Lưu: `docs/wireshark/01-udp-discovery.png` + `udp-discovery.pcapng`.

### 2.2 Bắt tay TCP

Filter:

```text
tcp.port == 6000 && tcp.flags.syn == 1
```

Thao tác: `/chat Minh`.

Ảnh cần thấy 3 gói liên tiếp:

| # | Nguồn → đích | Flags | Ghi chú |
|---|---|---|---|
| 1 | 192.168.1.10 → 192.168.1.12 | SYN | seq = x |
| 2 | 192.168.1.12 → 192.168.1.10 | SYN, ACK | seq = y, ack = x+1 |
| 3 | 192.168.1.10 → 192.168.1.12 | ACK | ack = y+1 |

Lưu: `02-tcp-handshake.png`.

### 2.3 Chat stream

Thao tác: chat vài câu, rồi chuột phải một packet TCP → **Follow → TCP Stream**.

Ảnh cần thấy:

```text
HI|Quan|5000|chat|
MSG|35|Chào Minh, sẵn sàng demo chưa?
MSG|23|Rồi! Gửi mình slide nhé
```

Ghi chú: stream hiển thị dạng text nên thấy rõ header; byte `|` là `0x7C`.
Lưu: `03-chat-stream.png`.

### 2.4 File stream

Thao tác: `/send` một file ~2 MB.

Filter/kiểm tra:

```text
tcp.stream == 1          # kết nối thứ hai (số có thể khác)
```

Ảnh cần thấy:

- Một kết nối TCP mới (không phải kết nối chat đang mở).
- Header `FILE|slides.pdf|2516582|` rồi dữ liệu nhị phân; trước đó là `HI|Quan|5000|file|`.
- Sau khi đủ byte: FIN/ACK, kết nối chat **vẫn mở**.

Lưu: `04-file-stream.png`.

### 2.5 Kết thúc / crash

```text
tcp.flags.fin == 1 || tcp.flags.reset == 1
```

- `/leave` hoặc `/quit`: thấy `BYE|` trong stream rồi FIN.
- Kill process / đóng cửa sổ: thấy RST (không có `BYE`).

Lưu: `05-bye-vs-rst.png`.

---

## 3. Checklist ảnh cho báo cáo

- [ ] `01-udp-discovery.png` — đích broadcast + payload `HELLO`
- [ ] `02-tcp-handshake.png` — đủ SYN / SYN-ACK / ACK
- [ ] `03-chat-stream.png` — `HI` + nhiều `MSG`
- [ ] `04-file-stream.png` — kết nối file riêng + FIN
- [ ] `05-bye-vs-rst.png` — FIN kèm `BYE` so với RST
- [ ] Mỗi ảnh có caption 1 câu giải thích (đưa vào mục 4 báo cáo)

## 4. Mẫu caption

> Hình 3. Gói broadcast UDP từ Quan (192.168.1.10) tới 255.255.255.255:9999,
> payload `HELLO|Quan|5000|online`. Switch nhân bản gói này ra mọi cổng nên
> Minh và Huy đều nhận được.

> Hình 4. Bắt tay ba bước khi Quan mở chat với Minh: SYN (seq=0), SYN-ACK
> (seq=0, ack=1), ACK (ack=1). Sau đó Quan gửi `HI|Quan|5000|chat|` để định danh.

## 5. Lưu ý

- `.pcapng` có thể nặng vài MB → `.gitignore` đang bỏ qua; chỉ commit khi nhóm
  muốn giữ bằng chứng, hoặc nén lại.
- Không bắt trên interface VPN/ảo nếu traffic đi đường khác.
- Nếu dùng Wi-Fi có client isolation, gói broadcast có thể không thấy — ghi
  chú vào phần "khó khăn" của báo cáo.
