# LAN Chat & File Sharing

Ứng dụng nhắn tin và chia sẻ tệp ngang hàng trong mạng LAN. Ứng dụng mở **giao diện Tkinter** theo mặc định và có thể chạy trong terminal. Cả hai giao diện đều dùng UDP để tìm người dùng và TCP để nhắn tin, truyền tệp. Các máy kết nối trực tiếp với nhau. Lịch sử trò chuyện chỉ tồn tại trong phiên chạy.

## Yêu cầu

- Python **3.10 trở lên** trên Windows hoặc Linux.
- Hai máy tính trên cùng mạng LAN. Tường lửa cần cho phép gói quảng bá UDP và kết nối TCP đến ứng dụng.
- Cài `prompt_toolkit` cho chế độ dòng lệnh bằng `python -m pip install -r requirements.txt`.
- Giao diện đồ họa cần Tkinter. Trên Windows, Tkinter thường đi kèm Python. Trên Linux, nếu thiếu, cài gói `python3-tk` trên Debian/Ubuntu hoặc `tk` trên Arch/CachyOS.

## Cách chạy

Chạy ứng dụng mà không truyền tùy chọn cấu hình để nhập thiết lập khi khởi động. Cửa sổ Tkinter cho phép nhập tên hiển thị và cổng TCP. Mở **Cài đặt nâng cao** để chỉnh địa chỉ quảng bá và thư mục lưu tệp nhận. Trong terminal, nhấn **Enter** để dùng giá trị mặc định hoặc **Ctrl+C** để hủy.

```bash
# Mở cửa sổ cấu hình
python main.py

# Nhập cấu hình trong terminal
python main.py --nogui

# Bỏ qua bước nhập cấu hình
python main.py --name Khang
python main.py --nogui --name Huy --port 5001

# Ví dụ với các tùy chọn cấu hình khác
python main.py --name Khang --port 5001 --bcast 192.168.1.255 --downloads ./received
```

Khi truyền `--port`, `--bcast` hoặc `--downloads`, hãy truyền kèm `--name`. Các tùy chọn bỏ qua sẽ dùng giá trị mặc định. Nếu chỉ truyền `--nogui`, ứng dụng vẫn hỏi cấu hình trong terminal.

| Tùy chọn | Ý nghĩa | Giá trị mặc định |
| --- | --- | --- |
| `--name TÊN` | Tên hiển thị, từ 1 đến 60 ký tự | Nhập khi khởi động nếu chưa truyền |
| `--port CỔNG` | Cổng TCP lắng nghe | `0` (hệ điều hành tự cấp cổng) |
| `--bcast IP` | Địa chỉ đích để quảng bá UDP | `255.255.255.255` |
| `--downloads THƯ_MỤC` | Thư mục lưu tệp nhận | `downloads` |
| `--nogui` | Dùng giao diện dòng lệnh | Tắt |

Nếu Tkinter bị thiếu hoặc không mở được cửa sổ, ứng dụng chuyển sang chế độ dòng lệnh khi có terminal tương tác. Ứng dụng dùng các tùy chọn cấu hình đã truyền hoặc hỏi cấu hình nếu cần.

### Giao diện đồ họa

- Chọn một người dùng đang trực tuyến trong thanh bên. Ứng dụng mở kết nối TCP ở luồng nền.
- Nhập tin nhắn rồi nhấn **Enter** hoặc bấm **Gửi**.
- Bấm **Đính kèm** để chọn tệp. Thanh tiến độ hiển thị lần truyền tệp gần nhất với người đang được chọn.
- Danh sách **Người dùng** hiển thị trạng thái và số tin chưa đọc. Người dùng đã ngoại tuyến xuất hiện bằng màu xám để bạn vẫn xem được cuộc trò chuyện trong phiên.
- Đóng cửa sổ để thoát và ngắt các kết nối. Nếu đang truyền tệp, ứng dụng hỏi trước khi hủy việc truyền và thoát.

Tên hiển thị và thiết lập mạng được nhập khi khởi động. Trong phiên chạy, bấm nút trạng thái ở góc trên bên phải để chuyển giữa **Trực tuyến** và **Vắng mặt**.

### Lệnh trong terminal

| Lệnh | Mô tả |
| --- | --- |
| `/list` | Xem số thứ tự, tên, địa chỉ IP và trạng thái của người dùng trong mạng |
| `/chat <tên\|số>` | Mở cuộc trò chuyện qua TCP với người dùng theo tên hoặc số thứ tự |
| `<tin nhắn>` | Gửi tin nhắn cho người đang trò chuyện |
| `/send <tệp>` | Gửi tệp cho người đang trò chuyện |
| `/leave` | Rời cuộc trò chuyện hiện tại |
| `/status <online\|away>` | Đổi trạng thái thành trực tuyến hoặc vắng mặt. Trạng thái được quảng bá qua UDP |
| `/help` | Xem danh sách lệnh |
| `/quit` | Thoát ứng dụng |

## Thử kết nối trên một hoặc hai máy

Theo mặc định, hệ điều hành cấp một cổng TCP còn trống cho mỗi phiên chạy. Nếu muốn dùng cổng cố định khi thử hai phiên trên cùng máy, hãy chọn một cổng riêng cho mỗi phiên.

```bash
python main.py --name Khang --port 5001 --bcast 127.255.255.255
python main.py --nogui --name Huy --port 5002 --bcast 127.255.255.255
```

Khả năng nhiều phiên cùng lắng nghe cổng UDP `9999` trên một máy phụ thuộc vào cách hệ điều hành cho phép dùng chung cổng. Để thử trong điều kiện thực tế, hãy chạy ứng dụng trên hai máy cùng mạng LAN. Trong Wireshark, lọc `udp.port == 9999` để xem các gói quảng bá tìm người dùng. Lọc `tcp.port == 5001` để xem bắt tay ba bước TCP và thay `5001` bằng cổng lắng nghe thực tế.

## Giao thức và lưu trữ

- **UDP.** Gói `HELLO` chứa JSON với các trường `id`, `name`, `port` và `status`. Ứng dụng quảng bá mỗi **3 giây** qua cổng UDP **9999**. Sau **10 giây** không nhận được cập nhật, người dùng được đánh dấu ngoại tuyến.
- **TCP.** Mỗi khung bắt đầu bằng 4 byte ghi độ dài JSON (số nguyên không dấu, big-endian), theo sau là JSON mã hóa UTF-8. Độ dài JSON tối đa là 256 KiB.
- **Nhắn tin.** Sau khi kết nối TCP, hai bên trao đổi `HELLO`, rồi dùng các khung `MSG` và `BYE`.
- **Truyền tệp.** Ứng dụng dùng một kết nối TCP riêng để truyền `FILE_META` và dữ liệu tệp. Bên nhận lưu vào tệp tạm `.part`, đổi tên khi nhận đủ dữ liệu rồi gửi `FILE_ACK`. Nếu trùng tên, ứng dụng thêm hậu tố như `(1)`.
- Mỗi lần khởi động, ứng dụng tạo một UUID mới. Người dùng khởi động lại ứng dụng sẽ được nhận diện là một **phiên mới**.
- **Tin nhắn chỉ lưu trong RAM. Thoát ứng dụng sẽ xóa lịch sử trò chuyện cục bộ.** Tệp đã nhận vẫn nằm trong thư mục đã chọn.
- Ứng dụng phục vụ đồ án mạng LAN. Dữ liệu truyền qua mạng ở dạng không mã hóa.

## Kiểm thử

```bash
python -m unittest discover -s tests -v
python -m compileall -q main.py lanchat
```

Khi chuẩn bị demo, hãy thử **GUI ↔ GUI**, **GUI ↔ CLI** và **CLI ↔ CLI** trên hai máy. Kiểm tra tường lửa đã cho phép UDP/9999 và cổng TCP lắng nghe.

## Đóng gói

Dùng PyInstaller để tạo tệp thực thi trên từng hệ điều hành đích.

```bash
python -m pip install pyinstaller
python -m PyInstaller --onefile --name LANChat main.py
```

Tạo bản thực thi có console để dùng các tùy chọn dòng lệnh, chạy với `--nogui` và chuyển sang CLI nếu GUI không mở được. Chạy từ terminal, ví dụ `./dist/LANChat --name Khang` trên Linux hoặc `dist\\LANChat.exe --name Khang` trên Windows. Bản Windows đóng gói với `--windowed` thiếu console cho chế độ CLI tương tác.
