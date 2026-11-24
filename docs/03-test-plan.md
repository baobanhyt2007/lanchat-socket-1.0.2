# Kế hoạch kiểm thử

> Người duy trì: **C** · A/B cung cấp kịch bản cho phần mình làm.
> Mỗi lần chạy thử, ghi kết quả vào cột cuối và chụp ảnh màn hình nếu fail.

---

## 1. Test tự động (39 test, không cần mạng)

```powershell
python -m unittest discover -s tests -v
# hoặc
.\scripts\test.ps1
```

| ID | File | Nội dung | Kỳ vọng |
|---|---|---|---|
| T01 | `test_protocol.py` | `MSG` tiếng Việt | `length` = số byte (35), không phải 30 ký tự |
| T02 | | 2 frame trong 1 `sendall` | đọc được 2 frame riêng biệt |
| T03 | | gửi frame từng byte | vẫn đọc đúng (test phân mảnh) |
| T04 | | tên file `báo cáo \| final.pdf` | giải mã đúng tên, payload đúng |
| T05 | | `BYE\|` | type `BYE` |
| T06 | | `GARBAGE\|` | `ProtocolError` |
| T07 | | 5000 byte không có `\|` | `ProtocolError` (header quá dài) |
| T08 | | `MSG\|-5\|` | `ProtocolError` |
| T09 | | `recv_exact` | trả đúng số byte |
| T10 | `test_peers.py` | lần đầu thấy peer | event `online` |
| T11 | | refresh cùng status | không event |
| T12 | | đổi `online` → `away` | event `status`, lưu `previous_status` |
| T13 | | sweep đúng 10 s | 10.0 s còn, 10.1 s bị xoá |
| T14 | | có `HELLO` mới trước timeout | không bị xoá |
| T15 | | tìm theo tên / số / tiền tố | đúng peer |
| T16 | | tiền tố mơ hồ (`min` với Minh/Minh2) | trả `None` |
| T17 | | parse `HELLO` sai định dạng | trả `None`, không crash |
| T18 | `test_files.py` | nhận file đủ byte | file đúng nội dung, progress 100 |
| T19 | | peer đóng giữa chừng | `.part` bị xoá, không còn file |
| T20 | | trùng tên `report.pdf` | lưu `report (1).pdf`, file cũ nguyên vẹn |
| T21 | | `../../evil.txt`, `CON.txt` | thành `evil.txt`, `file_CON.txt` |
| T22 | `test_integration.py` | chat vào qua TCP thật | server nhận đúng, partner được set |
| T23 | | `BYE` | partner về `None` |
| T24 | | nhận file qua TCP thật | file lưu vào `downloads/` |
| T25 | | frame rác `NOTAFRAME\|` | kết nối bị đóng, server vẫn nhận kết nối mới |
| T26 | | outgoing + file sender | HI/MSG đúng chiều, file round-trip |
| T27 | `test_protocol.py` | `HI` có `purpose` | parse đúng `chat`/`file` |
| T28 | | `HI` purpose lạ | `ProtocolError` |
| T29 | `test_files.py` | tên trùng với `.part` đang nhận | chọn `inflight (1).bin`, không ghi đè bản đang tải |
| T30 | `test_entrypoints.py` | `import lanchat.app` | import sạch, không lỗi tương đối/tuyệt đối |
| T31 | | `python -m lanchat --version` | exit 0, in `1.0.0` |
| T32 | | `python lanchat\__main__.py --version` | exit 0, in `1.0.0` (chạy trực tiếp file) |
| T33 | | `python -m lanchat --help` | exit 0, có `--name --port --udp-port --bcast` |
| T34 | `test_commands.py` | `App.dispatch_line(text)` | nhận đúng 1 tham số, không `TypeError` |
| T35 | | `App.start()` truyền handler vào console | handler gọi được bằng 1 tham số |
| T36 | | `/list`, `/status away`, text thường | gọi đúng method của App |
| T37 | `test_presence_messages.py` | peer đầu tiên có status `online` | in `[*] Minh is online ...` |
| T38 | | peer đầu tiên có status `away` | in `[*] Minh is away ...`, **không** in "is online" |
| T39 | | đổi `away` → `online` | in `[*] Minh is now online.` |

**Điều kiện pass:** 39/39 OK, không warning bất thường.

---

## 2. Test tay trên 1 máy (3 instance)

```powershell
.\scripts\run_demo.ps1
```

| ID | Thao tác | Kỳ vọng |
|---|---|---|
| M01 | chờ 3–5 s ở cả 3 cửa sổ | mỗi cửa sổ báo 2 peer online, không báo chính mình |
| M02 | `/list` ở Quan | số thứ tự, tên, IP `127.0.0.1`, port 5002/5003, thời gian ≤ 3 s |
| M03 | Minh `/status away` | Quan và Huy in `Minh is now away`, `/list` hiện `away` |
| M04 | Quan `/chat Minh`, gõ 3 tin | Minh hiện ngay, Quan thấy bản echo `[Quan] ...` |
| M05 | Minh trả lời khi Quan đang gõ dở | dòng đang gõ **không mất chữ**, tin chen phía trên |
| M06 | Huy gửi tin cho Minh khi Minh đang chat Quan | Minh thấy `[*] New message from Huy (1 unread)` |
| M07 | Minh `/chat Huy` | in `Switched to Huy`, hiện backlog unread |
| M08 | Quan `/send README.md` khi đang chat Minh | Quan thấy 25/50/75/100%, Minh nhận `downloads/README.md` |
| M09 | trong lúc gửi file lớn, gõ tin | chat vẫn gửi/nhận bình thường |
| M10 | gửi file trùng tên 2 lần | lần 2 thành `README (1).md` |
| M11 | `/leave` | bên kia in `Quan left the chat`, prompt vẫn dùng được |
| M12 | Minh `/quit` | 2 bên kia sau ≤ 10 s in `Minh is offline` |
| M13 | `/status abc`, `/chat 99`, `/xyz` | báo lỗi ngắn, không crash |
| M14 | `/send khongco.pdf` | `[!] File not found: ...` |

---

## 3. Test tay trên 2 máy (bắt buộc cho demo)

Chuẩn bị: 2 máy cùng Wi-Fi/LAN, đã mở firewall.

| ID | Máy A | Máy B | Kỳ vọng |
|---|---|---|---|
| N01 | `python -m lanchat --name Quan --port 5000` | `python -m lanchat --name Minh --port 6000` | sau ≤ 5 s mỗi bên thấy peer kia với IP thật |
| N02 | `/status away` | `/list` | Minh thấy Quan `away`, IP đúng |
| N03 | `/chat Minh` | chấp nhận | `Connected to Minh (192.168.x.x:6000)` |
| N04 | gõ tin | trả lời | hai chiều, tiếng Việt đúng |
| N05 | `/send` file 5 MB | theo dõi % | cả hai thấy 25/50/75/100, file mở được, hash khớp |
| N06 | tắt Wi-Fi máy B | chờ 10 s | A báo `Minh is offline`; chat socket báo mất kết nối |
| N07 | bật lại Wi-Fi, chạy B | | A thấy online trở lại, `/chat` lại được |
| N08 | đóng cửa sổ B đột ngột | | A nhận `Connection with Minh lost` trong ≤ 1 s (RST) |

Kiểm tra hash file sau khi truyền:

```powershell
Get-FileHash .\downloads\slides.pdf -Algorithm SHA256
Get-FileHash .\docs\slides.pdf     -Algorithm SHA256
```

---

## 4. Năm nhánh lỗi bắt buộc (mục 5.3 của đề)

| ID | Cách tạo | Kỳ vọng | Ghi chú |
|---|---|---|---|
| E01 | Tắt Minh, ngay lập tức Quan `/chat Minh` | `[!] cannot connect ...` hoặc timeout 5 s; app vẫn chạy | nếu chưa quá 10 s, Minh vẫn trong `/list` |
| E02 | Đang chat, đóng cửa sổ Minh (không `/quit`) | Quan in `Connection with Minh lost`, partner về `None` | RST/FIN |
| E03 | Đang gửi file 50 MB, tắt Wi-Fi máy gửi ở ~50% | Hai bên báo lỗi; `downloads/*.part` bị xoá | thử cả chiều gửi/nhận |
| E04 | `python -c "import socket;s=socket.create_connection(('127.0.0.1',5001));s.sendall(b'abc\x7c');s.close()"` | log `[!] Rejected connection ... unknown frame type`; app sống | thay `abc` bằng `HI` để test header thiếu trường |
| E05 | `/chta Minh`, `/send khongco.pdf` | in trợ giúp ngắn / `File not found` | không traceback |

Bổ sung nên thử:

| ID | Cách tạo | Kỳ vọng |
|---|---|---|
| E06 | gửi file 0 byte | nhận file rỗng, không treo |
| E07 | gửi cùng lúc 2 file | 2 kết nối file độc lập, chat vẫn chạy |
| E08 | `/chat` chính mình (nếu lọt vào list) | `[!] That is you.` |
| E09 | 2 bên cùng `/chat` nhau | chỉ còn 1 kết nối, chat 2 chiều vẫn chạy |
| E10 | thoát bằng Ctrl+C | terminal trở lại bình thường, không kẹt ký tự |

---

## 5. Wireshark — kiểm tra gói

| Giai đoạn | Filter | Ảnh cần chụp |
|---|---|---|
| Discovery | `udp.port == 9999` | 1 gói broadcast đích `255.255.255.255`, payload `HELLO\|...`; gói `away` ngay sau `/status away` |
| Bắt tay TCP | `tcp.port == 6000 && tcp.flags.syn == 1` | SYN, SYN-ACK, ACK cùng seq/ack |
| Chat | Follow → TCP Stream | `HI\|Quan\|5000\|` rồi `MSG\|35\|...` |
| File | `tcp.stream == 1` | kết nối thứ hai, `FILE\|...`, FIN sau khi đủ byte |
| Kết thúc | `tcp.flags.fin == 1 \|\| tcp.flags.reset == 1` | `BYE\|` + FIN; so sánh với RST khi kill process |

Chi tiết cách bắt: [`wireshark/README.md`](wireshark/README.md).

---

## 6. Ma trận môi trường

| Môi trường | Bắt buộc | Ghi chú |
|---|---|---|
| Windows 10/11, Python 3.8 | ✅ | môi trường lớp |
| Ubuntu, Python 3.8/3.11 | ✅ (CI) | `msvcrt` được thay bằng `termios` |
| 1 máy, 3 instance | ✅ | script `run_demo.ps1` |
| 2 máy cùng LAN | ✅ | dùng cho Wireshark + demo |
| Wi-Fi có client isolation | ❌ | broadcast không tới → ghi chú hạn chế môi trường |

---

## 7. Biên bản test

```
Ngày:
Máy / HĐH / Python:
Người test:
Commit:

[ ] 39/39 automated pass
[ ] M01–M14 pass
[ ] N01–N08 pass
[ ] E01–E05 pass
[ ] pcap + ảnh đã lưu vào docs/wireshark/

Lỗi còn lại:
```
