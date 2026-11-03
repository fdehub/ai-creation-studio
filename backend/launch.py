"""Start only this application's children; never terminate unrelated processes."""
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    node = shutil.which('node')
    vite = ROOT / 'node_modules' / 'vite' / 'bin' / 'vite.js'
    if not node or not vite.is_file():
        raise SystemExit('请先安装 Node.js 24，并在项目根目录运行 npm ci。')
    for port in (5273, 8100):
        with socket.socket() as sock:
            try:
                sock.bind(('127.0.0.1', port))
            except OSError:
                raise SystemExit(f'端口 {port} 已被使用，请先关闭占用程序，或按 README 手动选择其他端口。')
    commands = [
        [sys.executable, '-m', 'uvicorn', 'main:app', '--app-dir', str(ROOT / 'backend'), '--host', '127.0.0.1', '--port', '8100'],
        [node, str(vite), '--host', '127.0.0.1'],
    ]
    children = []
    try:
        for command in commands:
            children.append(subprocess.Popen(command, cwd=ROOT, env=os.environ.copy()))
        print('前端：http://127.0.0.1:5273\n按 Ctrl+C 停止本次启动的前后端。', flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(.5)
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == '__main__':
    main()
