import tkinter as tk
from tkinter import ttk, filedialog
import threading
import asyncio
import websockets
import json
import os
import shutil
import socket
from base64 import b64encode
import ttkbootstrap as tb
import qrcode
from PIL import Image, ImageTk

class FileServer:
    def __init__(self):
        self.window = tb.Window(themename="darkly")
        self.window.title("File Server")
        self.window.geometry("500x700")

        self.server_ip = self.get_local_ip()
        self.server_port = 8765
        self.server_url = f"ws://{self.server_ip}:{self.server_port}"

        self.main_frame = ttk.Frame(self.window, padding=20)
        self.main_frame.pack(expand=True, fill=tk.BOTH)

        self.server_btn = tb.Button(self.main_frame, text="Start Server", bootstyle="success", command=self.toggle_server)
        self.server_btn.pack(pady=10, fill=tk.X)

        self.status_label = ttk.Label(self.main_frame, text=f"Server IP: {self.server_ip}")
        self.status_label.pack(pady=5)

        self.qr_label = ttk.Label(self.main_frame)
        self.qr_label.pack(pady=10)
        self.generate_qr_code()

        self.file_list_label = ttk.Label(self.main_frame, text="Available Files:")
        self.file_list_label.pack(pady=5)
        self.file_list = tk.Listbox(self.main_frame, width=50, height=10)
        self.file_list.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        self.send_btn = tb.Button(self.main_frame, text="Select File to Send", bootstyle="primary", command=self.select_file)
        self.send_btn.pack(pady=10, fill=tk.X)

        self.upload_dir = "uploads"
        os.makedirs(self.upload_dir, exist_ok=True)
        self.update_file_list()

        self.server_thread = None
        self.running = False
        self.clients = set()

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception as e:
            print("[ERROR] Unable to get local IP:", e)
            return "127.0.0.1"

    def generate_qr_code(self):
        qr = qrcode.make(self.server_url)
        qr_path = "server_qr.png"
        qr.save(qr_path)
        img = Image.open(qr_path)
        img = img.resize((200, 200))
        img = ImageTk.PhotoImage(img)
        self.qr_label.config(image=img)
        self.qr_label.image = img

    def update_file_list(self):
        self.file_list.delete(0, tk.END)
        for f in os.listdir(self.upload_dir):
            self.file_list.insert(tk.END, f)

    def select_file(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            file_name = os.path.basename(file_path)
            destination = os.path.join(self.upload_dir, file_name)
            shutil.copy(file_path, destination)
            print(f"[INFO] File added: {file_name}")
            self.update_file_list()
            asyncio.run(self.notify_clients())

    async def notify_clients(self):
        files = os.listdir(self.upload_dir)
        message = json.dumps({"type": "list", "files": files})
        to_remove = set()
        for client in self.clients:
            try:
                await client.send(message)
            except:
                to_remove.add(client)
        self.clients -= to_remove

    async def handle_client(self, websocket):
        print("[INFO] Client connected")
        self.clients.add(websocket)
        await websocket.send(json.dumps({"type": "list", "files": os.listdir(self.upload_dir)}))

        try:
            async for message in websocket:
                data = json.loads(message)
                if data["type"] == "download":
                    filename = data["file"]
                    filepath = os.path.join(self.upload_dir, filename)
                    if os.path.exists(filepath):
                        with open(filepath, "rb") as f:
                            content = b64encode(f.read()).decode("utf-8")
                        await websocket.send(json.dumps({"type": "file", "name": filename, "content": content}))
                        print(f"[INFO] Sent file: {filename}")
        except:
            pass
        finally:
            self.clients.discard(websocket)
            print("[INFO] Client disconnected")

    async def run_server(self):
        print("[INFO] Server starting...")
        async with websockets.serve(self.handle_client, self.server_ip, self.server_port):
            await asyncio.Future()

    def start_server(self):
        self.running = True
        self.server_btn.config(text="Stop Server", bootstyle="danger")
        self.server_thread = threading.Thread(target=self.run_async_server, daemon=True)
        self.server_thread.start()
        print("[INFO] Server started.")

    def stop_server(self):
        self.running = False
        self.server_btn.config(text="Start Server", bootstyle="success")
        print("[INFO] Server stopped.")
        self.update_file_list()

    def toggle_server(self):
        if self.running:
            self.stop_server()
        else:
            self.start_server()

    def run_async_server(self):
        asyncio.run(self.run_server())

    def run(self):
        self.window.mainloop()

if __name__ == "__main__":
    server = FileServer()
    server.run()
