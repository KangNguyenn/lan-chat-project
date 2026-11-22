LAN CHAT - HƯỚNG DẪN NHANH

CÀI ĐẶT
1. Cài Python 3.10 trở lên trên Windows hoặc Linux.
2. Chạy lệnh python -m pip install -r requirements.txt
3. Trên Linux, cài Tkinter nếu cần giao diện đồ họa và máy chưa có gói này.
   Ubuntu/Debian: sudo apt install python3-tk
   Arch/CachyOS: sudo pacman -S tk

CÁCH CHẠY
Cấu hình trong cửa sổ:        python main.py
Cấu hình trong terminal:      python main.py --nogui
Mở GUI trực tiếp:             python main.py --name Alice
Mở CLI trực tiếp:             python main.py --nogui --name Bob --port 5001
Tùy chọn cấu hình: --port 5001 --bcast 192.168.1.255 --downloads ./received
Khi dùng các tùy chọn cấu hình trên, hãy truyền kèm --name.
Cổng TCP mặc định là 0 để hệ điều hành tự cấp cổng. Dùng --port để chọn cổng cố định.

KIỂM THỬ
Tự động: python -m unittest discover -s tests -v
Thủ công: Chạy ứng dụng trên hai máy cùng mạng LAN. Thử nhắn tin và gửi tệp
          giữa GUI-GUI, GUI-CLI và CLI-CLI.
Bộ lọc Wireshark:
  udp.port == 9999   Gói quảng bá tìm người dùng.
  tcp.port == 5001   Ví dụ lọc bắt tay TCP. Thay 5001 bằng cổng lắng nghe thực tế.
Cho phép UDP 9999 và cổng TCP lắng nghe qua tường lửa.
