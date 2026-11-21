#   tao it nhat 2 powershell nhap: cd lan_chat_project cho moi powershell
#   tao nguoi dung cho moi pws: python code.py --name <name> --port 500x --bcast 127.255.255.255


import argparse
import os
import socket
import sys
import threading
import time

UDP_PORT = 9999
BROADCAST_INTERVAL = 3 

online_users = {}
users_lock = threading.Lock()

current_chat_peer = None
current_conn = None
chat_lock = threading.Lock()

unread_messages = {}
unread_lock = threading.Lock()

my_status = "online"
running = True


def get_local_ip():
  """Lấy IP nội bộ của máy tính đang chạy."""
  s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  try:
    s.connect(("10.255.255.255", 1))
    IP = s.getsockname()[0]
  except Exception:
    IP = "127.0.0.1"
  finally:
    s.close()
  return IP


# --- 1. UDP BROADCASTER & LISTENER (Khám phá & Trạng thái) ---
def udp_broadcaster(name, tcp_port, bcast_addr):
  """Định kỳ 3 giây gửi gói tin HELLO lên mạng (đã cấu hình bind và socket options chuẩn demo)."""
  global my_status, running
  s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  if hasattr(socket, "SO_REUSEPORT"):
    try:
      s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except OSError:
      pass
  s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

  try:
    s.bind(("", UDP_PORT))
  except Exception:
    pass

  while running:
    msg = f"HELLO|{name}|{tcp_port}|{my_status}".encode("utf-8")
    try:
      s.sendto(msg, (bcast_addr, UDP_PORT))
    except Exception:
      pass
    time.sleep(BROADCAST_INTERVAL)


def udp_listener(my_name):
  """Lắng nghe gói tin HELLO từ các peer và dọn dẹp peer timeout sau 10s."""
  global running
  s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  if hasattr(socket, "SO_REUSEPORT"):
    try:
      s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except OSError:
      pass
  s.bind(("", UDP_PORT))
  s.settimeout(1.0)

  while running:
    try:
      data, addr = s.recvfrom(1024)
      msg = data.decode("utf-8", errors="replace")
      parts = msg.split("|")
      if len(parts) == 4 and parts[0] == "HELLO":
        peer_name, peer_tcp_port, peer_status = parts[1], parts[2], parts[3]
        if peer_name == my_name:
          continue

        with users_lock:
          is_new = peer_name not in online_users
          online_users[peer_name] = {
              "ip": addr[0],
              "tcp_port": int(peer_tcp_port),
              "status": peer_status,
              "last_seen": time.time(),
          }
          if is_new:
            sys.stdout.write(f"\r\033[K[*] Thông báo: {peer_name} đã online!\n> ")
            sys.stdout.flush()
    except socket.timeout:
      pass
    except Exception:
      pass
    current_time = time.time()
    with users_lock:
      expired = [
          p
          for p, info in online_users.items()
          if current_time - info["last_seen"] > 10
      ]
      for p in expired:
        del online_users[p]
        sys.stdout.write(f"\r\033[K[*] Thông báo: {p} đã offline!\n> ")
        sys.stdout.flush()


# --- 2. TCP FRAMING & SOCKET UTILS ---
def send_tcp_msg(sock, msg_type, content_bytes):
  """Đóng gói message theo chuẩn giao thức TCP framing."""
  if msg_type == "MSG":
    header = f"MSG {len(content_bytes)} ".encode("utf-8")
    sock.sendall(header + content_bytes)
  elif msg_type == "FILE":
    filename, file_data = content_bytes
    header = f"FILE {filename} {len(file_data)} ".encode("utf-8")
    sock.sendall(header + file_data)
  elif msg_type == "BYE":
    sock.sendall(b"BYE")


def recv_exact(sock, n):
  """Đọc chính xác n bytes từ TCP stream."""
  data = bytearray()
  while len(data) < n:
    packet = sock.recv(n - len(data))
    if not packet:
      return None
    data.extend(packet)
  return bytes(data)


# --- 3. TCP SERVER & RECEIVER (Xử lý kết nối đến & Nhận tin/file) ---
def tcp_acceptor(my_tcp_port):
  """Lắng nghe kết nối TCP đến từ các peer khác."""
  global running
  server_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  server_s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  server_s.bind(("", my_tcp_port))
  server_s.listen(5)

  while running:
    try:
      server_s.settimeout(1.0)
      conn, addr = server_s.accept()
    except socket.timeout:
      continue
    except Exception:
      break
    threading.Thread(
        target=handle_peer_connection, args=(conn, addr, False), daemon=True
    ).start()


def handle_peer_connection(conn, addr, is_client):
  """Nhận và phân tích luồng dữ liệu TCP (Tin nhắn, File, BYE)."""
  global current_chat_peer, current_conn
  peer_name = None
  with users_lock:
    for name, info in online_users.items():
      if info["ip"] == addr[0]:
        peer_name = name
        break
  if not peer_name:
    peer_name = addr[0]

  try:
    while True:
      header_bytes = bytearray()
      while b" " in header_bytes or len(header_bytes) < 10:
        chunk = conn.recv(1)
        if not chunk:
          break
        header_bytes.extend(chunk)
        if chunk == b" ":
          break
      if not header_bytes:
        break

      header_str = header_bytes.decode("utf-8", errors="replace").strip()

      if header_str == "BYE":
        break

      elif header_str == "MSG":
        len_bytes = bytearray()
        while True:
          chunk = conn.recv(1)
          if not chunk or chunk == b" ":
            break
          len_bytes.extend(chunk)
        if not len_bytes:
          break
        msg_len = int(len_bytes.decode("utf-8"))
        msg_body = recv_exact(conn, msg_len).decode("utf-8", errors="replace")

        with chat_lock:
          in_chat = current_chat_peer == peer_name

        if in_chat:
          sys.stdout.write(f"\r\033[K[{peer_name}] {msg_body}\n> ")
          sys.stdout.flush()
        else:
          with unread_lock:
            if peer_name not in unread_messages:
              unread_messages[peer_name] = []
            unread_messages[peer_name].append(msg_body)
            count = len(unread_messages[peer_name])
          sys.stdout.write(
              f"\r\033[K[*] New message from {peer_name} ({count} unread)\n> "
          )
          sys.stdout.flush()

      elif header_str == "FILE":
        fname_bytes = bytearray()
        while True:
          chunk = conn.recv(1)
          if not chunk or chunk == b" ":
            break
          fname_bytes.extend(chunk)
        filename = fname_bytes.decode("utf-8")
        fsize_bytes = bytearray()
        while True:
          chunk = conn.recv(1)
          if not chunk or chunk == b" ":
            break
          fsize_bytes.extend(chunk)
        file_size = int(fsize_bytes.decode("utf-8"))

        sys.stdout.write(
            f"\r\033[K[*] Đang nhận file {filename} ({file_size} bytes) từ"
            f" {peer_name}...\n> "
        )
        sys.stdout.flush()
        os.makedirs("downloads", exist_ok=True)
        file_path = os.path.join("downloads", filename)
        received = 0
        with open(file_path, "wb") as f:
          while received < file_size:
            chunk_size = min(1024, file_size - received)
            data = conn.recv(chunk_size)
            if not data:
              break
            f.write(data)
            received += len(data)
            pct = int((received / file_size) * 100)
            sys.stdout.write(
                f"\r\033[K[*] Nhận file: {pct}% ({received}/{file_size} bytes)"
            )
            sys.stdout.flush()

        sys.stdout.write(
            f"\r\033[K[*] Đã lưu file vào {file_path}\n> "
        )
        sys.stdout.flush()

  except Exception:
    pass
  finally:
    conn.close()
    with chat_lock:
      if current_chat_peer == peer_name:
        sys.stdout.write(
            f"\r\033[K[*] Mất kết nối với {peer_name}. Trở lại màn hình"
            f" chính.\n> "
        )
        sys.stdout.flush()
        current_chat_peer = None
        current_conn = None


# --- 4. GỬI FILE (Chạy bằng Thread riêng biệt để không chặn chat) ---
def file_sender_thread(sock, filepath):
  """Tiến trình gửi file kèm thanh tiến trình phần trăm."""
  try:
    filename = os.path.basename(filepath)
    file_size = os.path.getsize(filepath)
    sys.stdout.write(
        f"\r\033[K[*] Sending {filename} ({file_size / (1024*1024):.2f} MB)\n> "
    )
    sys.stdout.flush()
    header = f"FILE {filename} {file_size} ".encode("utf-8")
    sock.sendall(header)

    sent = 0
    with open(filepath, "rb") as f:
      while True:
        chunk = f.read(1024)
        if not chunk:
          break
        sock.sendall(chunk)
        sent += len(chunk)
        pct = int((sent / file_size) * 100)
        sys.stdout.write(f"\r\033[K[*] Progress: {pct}% Done.")
        sys.stdout.flush()

    sys.stdout.write(f"\r\033[K[*] Gửi file thành công!\n> ")
    sys.stdout.flush()
  except Exception as e:
    sys.stdout.write(f"\r\033[K[*] Lỗi truyền file: {e}\n> ")
    sys.stdout.flush()


# --- 5. GIAO DIỆN CHÍNH (CLI) ---
def main():
  global current_chat_peer, current_conn, my_status, running

  parser = argparse.ArgumentParser(description="LAN Chat & File Sharing")
  parser.add_argument("--name", required=True, help="Tên của bạn")
  parser.add_argument("--port", type=int, default=5000, help="Cổng TCP lắng nghe")
  parser.add_argument("--bcast", default="255.255.255.255", help="Địa chỉ broadcast")
  args = parser.parse_args()

  my_ip = get_local_ip()
  print(f"[*] Đang khởi động LAN Chat...")
  print(f"[*] Tên: {args.name} | IP: {my_ip} | TCP Port: {args.port}")
  threading.Thread(
      target=udp_broadcaster,
      args=(args.name, args.port, args.bcast),
      daemon=True,
  ).start()
  threading.Thread(
      target=udp_listener, args=(args.name,), daemon=True
  ).start()
  threading.Thread(
      target=tcp_acceptor, args=(args.port,), daemon=True
  ).start()

  print("[*] Gõ /help để xem danh sách lệnh.")

  while running:
    try:
      cmd = input("> ").strip()
      if not cmd:
        continue
      if cmd.startswith("/"):
        parts = cmd.split(" ", 1)
        command = parts[0].lower()
        param = parts[1] if len(parts) > 1 else ""

        if command == "/quit":
          running = False
          if current_conn:
            try:
              current_conn.sendall(b"BYE")
              current_conn.close()
            except Exception:
              pass
          print("Đang thoát chương trình...")
          break

        elif command == "/list":
          print("\n--- DANH SÁCH ONLINE ---")
          with users_lock:
            if not online_users:
              print("Chưa có ai online trên mạng.")
            else:
              idx = 1
              for p_name, info in online_users.items():
                print(
                    f"{idx}. {p_name} ({info['ip']}:{info['tcp_port']}) -"
                    f" Trạng thái: {info['status']}"
                )
                idx += 1
          print("------------------------")

        elif command == "/status":
          if param in ["online", "away"]:
            my_status = param
            print(f"[*] Đã đổi trạng thái thành: {my_status}")
          else:
            print("Lệnh không hợp lệ. Sử dụng: /status online hoặc /status away")

        elif command == "/chat":
          target = param.strip()
          if not target:
            print("Vui lòng nhập tên hoặc số thứ tự người dùng.")
            continue
          peer_name = None
          peer_info = None
          with users_lock:
            if target.isdigit():
              idx = int(target)
              if 1 <= idx <= len(online_users):
                peer_name = list(online_users.keys())[idx - 1]
                peer_info = online_users[peer_name]
            else:
              if target in online_users:
                peer_name = target
                peer_info = online_users[peer_name]

          if not peer_name or not peer_info:
            print(f"[*] Không tìm thấy người dùng: {target}")
            continue
          try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((peer_info["ip"], peer_info["tcp_port"]))
            with chat_lock:
              current_chat_peer = peer_name
              current_conn = sock
            with unread_lock:
              unread_count = 0
              if peer_name in unread_messages:
                unread_count = len(unread_messages[peer_name])
                print(
                    f"\n[*] Đã kết nối với {peer_name} ({unread_count} tin"
                    " nhắn chưa đọc):"
                )
                for msg in unread_messages[peer_name]:
                  print(f"[{peer_name}] {msg}")
                del unread_messages[peer_name]
              else:
                print(f"[*] Connected to {peer_name} ({peer_info['ip']}:{peer_info['tcp_port']})")
            threading.Thread(
                target=handle_peer_connection,
                args=(sock, (peer_info["ip"], peer_info["tcp_port"]), True),
                daemon=True,
            ).start()
          except Exception as e:
            print(f"[*] Không thể kết nối tới {peer_name}: {e}")

        elif command == "/leave":
          if current_chat_peer:
            with chat_lock:
              if current_conn:
                try:
                  current_conn.sendall(b"BYE")
                  current_conn.close()
                except Exception:
                  pass
              print(f"[*] Đã đóng phiên chat với {current_chat_peer}")
              current_chat_peer = None
              current_conn = None
          else:
            print("[*] Bạn không trong phiên chat nào.")

        elif command == "/send":
          if not current_chat_peer or not current_conn:
            print("[*] Bạn chưa mở phiên chat nào để gửi file. Dùng /chat <tên> trước.")
            continue
          filepath = param.strip().strip('"').strip("'")
          if not os.path.exists(filepath):
            print(f"[*] Không tìm thấy file: {filepath}")
            continue
          threading.Thread(
              target=file_sender_thread,
              args=(current_conn, filepath),
              daemon=True,
          ).start()

        elif command == "/help":
          print("\nCác lệnh khả dụng:")
          print("  /list                 - Xem danh sách người dùng online")
          print(
              "  /chat <tên|số thứ tự> - Mở phiên chat với người dùng (kết nối"
              " TCP)"
          )
          print("  /send <đường_dẫn_file> - Gửi file cho đối tác chat hiện tại")
          print("  /status <online|away> - Thay đổi trạng thái cá nhân")
          print("  /leave                - Đóng phiên chat hiện tại")
          print("  /quit                 - Thoát chương trình\n")
        else:
          print(f"Lệnh không hợp lệ: {command}. Gõ /help để được trợ giúp.")

      else:
        with chat_lock:
          active_peer = current_chat_peer
          conn = current_conn

        if active_peer and conn:
          try:
            send_tcp_msg(conn, "MSG", cmd.encode("utf-8"))
            print(f"[{args.name}] {cmd}")
          except Exception as e:
            print(f"[*] Lỗi khi gửi tin nhắn: {e}")
        else:
            print("[*] Bạn chưa chọn đối tác chat. Hãy dùng lệnh /chat <tên> trước.")

    except KeyboardInterrupt:
      print("\nThoát chương trình.")
      break


if __name__ == "__main__":
  main()