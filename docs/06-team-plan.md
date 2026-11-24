# Kế hoạch nhóm 3 người — sprint 3 ngày

> Mỗi ngày có 2 checkpoint. Nguyên tắc: **không ai chờ ai**, `protocol.py` và
> interface chốt trong buổi sáng ngày 1, freeze code trưa ngày 3.

---

## 1. Vai trò

| | **A — Discovery + File** | **B — TCP Chat + Protocol** | **C — UI + Integration + Docs** |
|---|---|---|---|
| Nhánh | `feature/discovery` | `feature/chat` | `feature/ui-docs` |
| File | `discovery/*`, `chat/files.py` | `protocol.py`, `chat/server.py`, `chat/session.py` | `ui/*`, `app.py`, `tests/*`, `README.md`, `docs/*`, `scripts/*` |
| Chức năng | broadcast 3 s, `/list`, `/status`, timeout 10 s, gửi/nhận file, `.part`, progress | acceptor, HI, framing, `/chat`, `/leave`, unread, chống trùng kết nối | console redraw, lock màn hình, command, xử lý lỗi, test, CI, báo cáo |
| Wireshark | UDP 9999 | TCP handshake + stream | chú thích + chèn báo cáo |
| Báo cáo | 4.1, 4.3 | 3, 4.2 | 1, 2, 4.4, 5, 6, 7, 8 + merge |

Điểm rubric tương ứng: A 30 · B 30 · C 40 (C gánh test + báo cáo + demo).

---

## 2. Lịch 3 ngày

### Ngày 1 — Nền móng + đường ống thông

| Giờ | Việc | Ai | Kết quả |
|---|---|---|---|
| 08:00–09:00 | Đọc đề, duyệt `docs/01-protocol-spec.md`, tạo repo + nhánh | cả nhóm | spec v1.0 |
| 09:00–10:00 | Scaffold + `protocol.py` + test khung | C | `python -m lanchat --help` chạy |
| 10:00–12:00 | A: `PeerTable` + presence. B: acceptor + HI + MSG. C: console + commands + `/help` | // | mỗi người có test/loopback |
| 12:00–13:00 | nghỉ | | |
| 13:00–15:30 | A: listener + timeout + `/list` `/status`. B: `/chat` `/leave` 2 chiều. C: `app.py` nối | // | |
| 15:30–16:30 | **G1**: 2 instance chat MSG 2 chiều + `/list` thấy nhau | cả nhóm | tag `v0.1` |
| 16:30–18:00 | buffer: sửa lỗi tích hợp, push nhánh | // | CI xanh |

### Ngày 2 — Chat + File + UI thật

| Giờ | Việc | Ai | Kết quả |
|---|---|---|---|
| 08:00–11:00 | A: file sender/receiver + `.part`. B: route FILE-conn, unread/history. C: progress UI, test đang gõ | // | |
| 11:00–12:00 | **G2**: online/offline trên 2 máy, chat 2 chiều | cả nhóm | tag `v0.2` |
| 12:00–13:00 | nghỉ | | |
| 13:00–15:30 | tích hợp `/send` khi đang chat, sửa race/lock | // | |
| 15:30–16:30 | **G3**: gửi file 2–5 MB, chat vẫn chạy | cả nhóm | tag `v0.3` |
| 16:30–18:00 | A/B bắt Wireshark ngay trong lúc test | A, B | có `.pcapng` thô |

### Ngày 3 — Lỗi, test, báo cáo, demo

| Giờ | Việc | Ai | Kết quả |
|---|---|---|---|
| 08:00–10:30 | 5 nhánh lỗi E01–E05; C chủ trì, A/B sửa | C | **G4** |
| 10:30–12:00 | chạy full test matrix, **freeze code 12:00**, README | cả nhóm | tag `v1.0` |
| 12:00–13:00 | nghỉ | | |
| 13:00–15:00 | ảnh Wireshark + merge báo cáo | A/B viết, C merge | `docs/04-report.md` |
| 15:00–16:30 | tập demo theo `docs/05-demo-script.md` | cả nhóm | |
| 16:30–17:00 | checklist nộp, nén source, kiểm tra máy demo | C | nộp |

---

## 3. Quy trình Git

```
main                 luôn xanh, chỉ C merge
 ├── feature/discovery
 ├── feature/chat
 └── feature/ui-docs
```

- Sáng ngày 1: C tạo repo, push `main` với scaffold + `protocol.py`.
- Mỗi người `git switch -c feature/...`, commit nhỏ, push hằng ngày.
- Mở PR → 1 người review → **squash merge**.
- Tag cuối mỗi checkpoint: `v0.1`, `v0.2`, `v0.3`, `v1.0`.
- Không commit: `downloads/*`, `*.part`, `__pycache__`, file `.pcapng` lớn.

Quy ước commit: xem [`../CONTRIBUTING.md`](../CONTRIBUTING.md).

---

## 4. Hợp đồng giữa các vai (chốt 10:00 ngày 1)

A và C không đọc code B, chỉ dùng:

```python
# protocol.py
encode_hi(name, port, purpose="chat") -> bytes
encode_msg(text) -> bytes
encode_file_header(filename, size) -> bytes
encode_bye() -> bytes
FrameReader(sock).read_header() -> Header(type, meta)
FrameReader(sock).read_exact(n) / read_text(n) / iter_payload(n)

# từ App
app.console.show(line)                 # mọi thread in qua đây
app.peers.snapshot() / .find(token) / .get(name)
app.session.partner / .open(peer) / .leave() / .send_text(text)
app.files.send_async(path, peer)
app.on_peer_seen(name, ip, port)
app.on_chat_message(peer, text)
```

B không cần biết UI vẽ thế nào, chỉ gọi `app.on_chat_message`.
A không cần biết chat, chỉ đẩy `PeerTable` + `FileService.receive`.

---

## 5. Definition of Done

Một phần được coi là xong khi:

- [ ] Chạy được trên 1 máy, không traceback
- [ ] Có ít nhất 1 test hoặc 1 kịch bản tay đã chạy
- [ ] Không `print()` trực tiếp từ thread mạng (dùng `Console.show`)
- [ ] Docstring ngắn ở đầu module/hàm public
- [ ] Không commit file rác
- [ ] PR có mô tả + ảnh/log nếu là UI

Checkpoint chỉ tính là đạt khi **cả nhóm** chạy được trên máy của mình.

---

## 6. Nếu trễ — cắt theo thứ tự

1. Màu sắc, format console
2. Gửi nhiều file song song (giới hạn 1 file/lúc)
3. Lịch sử lưu ra đĩa
4. Tự động reconnect
5. Progress mượt từng % (giữ bậc 25%)

**Không được cắt:** `/status away`, timeout 10 s, `recv_exact`, lock màn hình,
xoá `.part` khi lỗi, 5 nhánh lỗi trong báo cáo.

---

## 7. Rủi ro & phương án

| Rủi ro | Dấu hiệu | Xử lý |
|---|---|---|
| Broadcast không tới | `/list` trống trên 2 máy | kiểm tra firewall/subnet; dùng `--bcast 192.168.x.255`; cuối cùng demo 1 máy với `127.255.255.255` |
| Port bận | `[!] Cannot start on TCP port` | đổi `--port`, demo dùng 5100/6100 |
| Race khi merge | test đỏ sau merge | C revert PR, người đó sửa trên nhánh, không sửa trực tiếp `main` |
| Mất dữ liệu do `git push --force` | — | cấm force trên `main`; bật branch protection |
| Ai đó ốm ngày 3 | — | C có thể demo bằng `docs/05-demo-script.md`; A/B đã commit đủ |

---

## 8. Biên bản checkpoint

```
Checkpoint: G_  ·  Ngày/giờ:
Có mặt:
Đã chạy:
Kết quả:  [ ] đạt  [ ] chưa
Lỗi còn lại / người phụ trách:
Commit/tag:
```
