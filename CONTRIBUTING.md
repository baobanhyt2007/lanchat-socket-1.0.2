# Quy ước đóng góp

Cả nhóm dùng chung repo này. Mục tiêu: **3 người code song song mà không giẫm chân nhau**.

## 1. Cài đặt

```powershell
git clone <repo-url>
cd socket2
python --version          # cần 3.8+
python -m unittest discover -s tests -v
python -m lanchat --name Test --port 5001
```

Không cần cài thêm package. `requirements.txt` để trống có chủ đích.

## 2. Nhánh

| Nhánh | Ai dùng | Nội dung |
|---|---|---|
| `main` | chỉ C merge | luôn chạy được, test xanh |
| `feature/discovery` | A | UDP, peer table, status, file transfer |
| `feature/chat` | B | protocol, acceptor, session, `/chat`, unread |
| `feature/ui-docs` | C | console, commands, app, test, README, docs |

Quy tắc:

```powershell
git switch main
git pull
git switch -c feature/<việc-ngắn>
# ... code ...
python -m unittest discover -s tests
git add -A
git commit -m "feat(discovery): add 10s peer timeout"
git push -u origin feature/<việc-ngắn>
```

Mở Pull Request vào `main`, nhờ 1 người review, **squash merge**.
Không push trực tiếp vào `main` (bật branch protection nếu repo public).

## 3. Commit message

```
feat(scope): thêm chức năng
fix(scope): sửa lỗi
docs(scope): tài liệu
test(scope): test
refactor(scope): đổi cấu trúc, không đổi hành vi
```

`scope` là `discovery`, `chat`, `files`, `ui`, `protocol`, `docs`, `ci`.

## 4. Vùng sở hữu

| File / thư mục | Người sở hữu | Người khác sửa khi |
|---|---|---|
| `lanchat/discovery/*`, `lanchat/chat/files.py` | A | có PR + A review |
| `lanchat/protocol.py`, `lanchat/chat/server.py`, `session.py` | B | thay đổi protocol phải cả nhóm đồng ý |
| `lanchat/ui/*`, `app.py`, `tests/*`, `README.md`, `docs/*` | C | C review |
| `config.py`, `errors.py` | cả nhóm | chỉ thêm, không đổi tên cũ |

**Đổi protocol = sự kiện của cả nhóm**: cập nhật `docs/01-protocol-spec.md`, tăng version, sửa test, báo trong nhóm chat.

## 5. Checklist trước khi mở PR

- [ ] `python -m unittest discover -s tests -v` xanh (39 test hiện tại)
- [ ] Chạy thử `python -m lanchat --name X --port 50xx`, `/list`, `/chat`, `/send`
- [ ] Không commit `downloads/*`, `*.part`, `__pycache__`, file `.pcapng` lớn
- [ ] Cập nhật docstring / `README` nếu đổi hành vi người dùng thấy được
- [ ] PR mô tả: làm gì, test thế nào, ảnh hưởng ai

## 6. Code style

- Python 3.8: dùng `typing.List/Dict/Optional`, không dùng `list[str]`.
- 4 spaces, tên hàm `snake_case`, class `PascalCase`, hằng số `UPPER_CASE`.
- Mọi lời gọi mạng phải có timeout hoặc nằm trong thread có cơ chế dừng.
- Mọi thứ in ra màn hình phải đi qua `Console.show()` (không `print()` từ thread mạng).
- Mọi truy cập dữ liệu chia sẻ phải có lock; không gọi `Console.show()` khi đang giữ lock của `PeerTable`/`ChatSession`/`ChatHistory`.

## 7. Báo lỗi / hỏi

Tạo GitHub Issue theo mẫu:

```
## Hiện tượng
## Cách tái hiện (lệnh, số máy, port)
## Log / ảnh chụp
## Đoán nguyên nhân
```

Gắn label `bug`, `discovery`, `chat`, `docs`… và assign người sở hữu.
