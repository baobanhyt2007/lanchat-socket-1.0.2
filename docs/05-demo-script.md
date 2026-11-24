# Kịch bản demo 10 phút

> Người dẫn: **C** · Người bấm máy A: **A** · Người bấm máy B: **B**.
> Mở sẵn: 2 cửa sổ terminal (2 máy), Wireshark đã bắt, thư mục file mẫu,
> `docs/wireshark/` để chiếu ảnh nếu mạng sự cố.

---

## 0:00–0:30 — Mở đầu

C nói:

> "Nhóm em làm LAN Chat & File Sharing. Mỗi máy vừa là client vừa là server.
> UDP dùng để tìm nhau và báo trạng thái, TCP dùng để chat và gửi file.
> Chương trình chỉ dùng thư viện chuẩn Python, chạy console."

Chỉ lên sơ đồ trong `docs/02-architecture.md` (in sẵn hoặc mở tab).

---

## 0:30–1:30 — Khởi động, discovery

Máy A:

```powershell
python -m lanchat --name Quan --port 5000
```

Máy B:

```powershell
python -m lanchat --name Minh --port 6000
```

Nói: "Mỗi bên broadcast `HELLO` mỗi 3 giây trên UDP 9999."

Sau 3–5 giây, cả hai tự in `[*] ... is online` (hoặc `is away` nếu bên kia khởi động với `--status away`). Sau đó:

```
> /list
[*] Online peers (1):
  1. Minh   192.168.1.12    tcp/6000   online    1s
```

Nói: "Timeout 10 giây, tức khoảng 3 gói liên tiếp bị mất."

---

## 1:30–2:30 — Trạng thái

Máy B:

```
> /status away
```

Máy A tự in `[*] Minh is now away.` Ngay lập tức `/list` ở A hiện `away`.

Nhấn mạnh: "Đổi trạng thái được gửi ngay, không chờ nhịp 3 giây."

---

## 2:30–4:30 — Chat hai chiều + đang gõ mà tin đến

A:

```
> /chat Minh
[*] Connected to Minh (192.168.1.12:6000).
[Quan] Chào Minh, sẵn sàng demo chưa?
```

B trả lời:

```
[Minh] Rồi! Gửi mình slide nhé
```

**Pha quan trọng:** A gõ dở `> đợi mình xíu, mình đang chụp...` (đừng Enter),
B gửi thêm một tin. Màn hình A phải hiện:

```
[Quan] Chào Minh, sẵn sàng demo chưa?
[Minh] Rồi! Gửi mình slide nhé
[Minh] ok, gửi khi nào cũng được
> đợi mình xíu, mình đang chụp..._     <- chữ vẫn còn
```

Nói: "Ba thao tác: xoá dòng nhập bằng `\r` + `\033[K`, in tin, vẽ lại prompt
và buffer. Một lock bảo vệ màn hình nên hai thread không in chồng."

---

## 4:30–5:30 — Peer thứ ba, unread, chuyển chat

Máy C (hoặc instance thứ ba trên máy B, port 6001):

```powershell
python -m lanchat --name Huy --port 6001
```

Huy gửi 2 tin cho Minh trong khi Minh vẫn đang chat Quan:

```
[*] New message from Huy (1 unread)
[*] New message from Huy (2 unread)
```

Minh:

```
> /chat Huy
[*] Switched to Huy.
[*] 2 unread message(s) from Huy:
   [Huy] router config xong rồi
   [Huy] gửi mình cái screenshot
```

Nói: "Minh giữ 2 kết nối cùng lúc; `HI` cho biết tin đến từ ai."

---

## 5:30–7:30 — Gửi file trong lúc chat

Minh `/chat Quan` lại. Quan:

```
> /send docs/slides.pdf
[*] Sending slides.pdf (2.4 KB) to Minh ...
[*] Sending slides.pdf ... 25%
[*] Sending slides.pdf ... 50%
[*] Sending slides.pdf ... 75%
[*] Sending slides.pdf ... 100% Done.
```

Minh:

```
[*] Receiving slides.pdf ...
[*] Saved 'slides.pdf' from Quan -> downloads\slides.pdf
```

**Trong lúc file đang gửi (file lớn hơn), gõ một tin chat** → vẫn gửi được.
Nói: "Mỗi file một kết nối TCP riêng, nên chat không bị chặn."

Mở `downloads/` cho hội đồng xem file, chạy `Get-FileHash` nếu muốn chắc.

---

## 7:30–9:00 — Bốn nhánh lỗi (chọn 3–4 cái)

1. **Chat người vừa offline**: tắt cửa sổ Minh, ngay lập tức Quan `/chat Minh`
   → `[!] cannot connect ...`; app vẫn chạy.
2. **Peer crash giữa chat**: đóng cửa sổ Minh → Quan in
   `Connection with Minh lost: ...`, partner về `None`.
3. **Frame rác**:
   ```powershell
   python -c "import socket;s=socket.create_connection(('127.0.0.1',5000));s.sendall(b'abc|');s.close()"
   ```
   → Quan in `[!] Rejected connection ...`, sau đó vẫn chat bình thường.
4. **Sai lệnh / file không tồn tại**:
   ```
   > /chta Minh
   [!] Unknown command '/chta'. Type /help ...
   > /send khongco.pdf
   [!] File not found: ...
   ```
5. Nếu còn thời gian: rút Wi-Fi lúc đang gửi file → `.part` bị xoá.

---

## 9:00–9:30 — Wireshark

Mở 2 ảnh đã chuẩn bị (hoặc capture live):

- `udp.port == 9999`: đích `255.255.255.255`, payload `HELLO|...`.
- `tcp.flags.syn == 1`: SYN → SYN-ACK → ACK.
- Follow TCP Stream: `HI|Quan|5000|chat|` rồi `MSG|35|...`.

Nói: "Ảnh này chứng minh broadcast thật và bắt tay 3 bước thật, không phải mô
phỏng."

---

## 9:30–10:00 — Kết

C chốt:

> "Nhóm hoàn thành đủ 4 nhóm chức năng, 39 test tự động, xử lý 5 nhóm lỗi.
> Hạn chế: chưa mã hoá, chưa resume file. Hướng phát triển: TLS, GUI, chat nhóm."

Cảm ơn hội đồng.

---

## Phương án dự phòng

| Sự cố | Xử lý ngay |
|---|---|
| Wi-Fi/AP chặn broadcast | Chuyển sang 3 instance trên 1 máy bằng `scripts/run_demo.ps1 -Broadcast 127.255.255.255`; đã tập trước |
| Mất mạng hoàn toàn | Chiếu video quay sẵn 2 phút + ảnh Wireshark đã lưu |
| Cổng 5000 bận | Dùng 5100/6100, đã ghi trong `docs/06-team-plan.md` |
| File demo quá lớn | Chuẩn bị sẵn file 2–5 MB; không dùng file > 50 MB khi demo |
| Terminal lỗi font tiếng Việt | Đặt `chcp 65001` trước khi chạy |

## Checklist trước khi vào phòng

- [ ] Pin 2 máy > 60%, mang sạc
- [ ] `python -m unittest discover -s tests` xanh trên máy demo
- [ ] Firewall đã allow Python (Private)
- [ ] Mở sẵn 3 terminal, Wireshark, thư mục `downloads/`
- [ ] File mẫu + ảnh Wireshark nằm trong thư mục dễ tìm
- [ ] Đã tập ít nhất 1 lần bấm giờ
