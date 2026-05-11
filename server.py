import socket
import json
import os
import threading
from datetime import datetime

# Configuration
SERVER_HOST = 'localhost'
SERVER_PORT = 5000
FILES_DIR = 'files'
HISTORY_FILE = os.path.join(FILES_DIR, '.history.json')
DEFAULT_USER = 'student'
DEFAULT_PASSWORD = '1234'


def ensure_files_dir():
    """Ensure files directory exists"""
    if not os.path.exists(FILES_DIR):
        os.makedirs(FILES_DIR)
        print(f"✓ Directory '{FILES_DIR}' created")


def authenticate(username, password):
    """Authenticate user"""
    return username == DEFAULT_USER and password == DEFAULT_PASSWORD


def get_safe_path(filename):
    """Return a safe path inside FILES_DIR."""
    if not filename or filename != os.path.basename(filename):
        raise ValueError('Invalid filename')
    return os.path.join(FILES_DIR, filename)


def load_history():
    """Load file operation history from disk."""
    if not os.path.exists(HISTORY_FILE):
        return {}

    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_history(history):
    """Save file operation history to disk."""
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=4)


def add_history(filename, operation, username, details=''):
    """Add a history entry for a file."""
    history = load_history()

    if filename not in history:
        history[filename] = []

    history[filename].append({
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'user': username,
        'operation': operation,
        'details': details
    })

    save_history(history)


def format_history(filename):
    """Format history entries so the client can display them nicely."""
    history = load_history()
    entries = history.get(filename, [])

    if not entries:
        return f'No operation history found for {filename}'

    lines = [f'Operation history for {filename}:']
    for i, entry in enumerate(entries, 1):
        details = entry.get('details', '')
        line = f"{i}. [{entry.get('time')}] {entry.get('operation')} by {entry.get('user')}"
        if details:
            line += f" - {details}"
        lines.append(line)

    return '\n'.join(lines)


def get_server_files():
    """Return visible files from the server directory."""
    ensure_files_dir()
    files = []

    for filename in os.listdir(FILES_DIR):
        filepath = os.path.join(FILES_DIR, filename)
        if os.path.isfile(filepath) and filename != os.path.basename(HISTORY_FILE):
            files.append(filename)

    return sorted(files)


def handle_client(conn, addr):
    """Handle client connection"""
    print(f"\n🔗 Client connected from {addr}")
    authenticated = False
    current_user = None

    try:
        while True:
            # Receive request
            request_data = conn.recv(4096).decode('utf-8')
            if not request_data:
                break

            try:
                request = json.loads(request_data)
                command = request.get('command')

                print(f"📨 Command received: {command}")

                # Authentication
                if command == 'login':
                    username = request.get('username')
                    password = request.get('password')

                    if authenticate(username, password):
                        authenticated = True
                        current_user = username
                        response = {'status': 'success', 'message': f'Welcome {username}!'}
                        print(f"✓ User {username} authenticated")
                    else:
                        response = {'status': 'error', 'message': 'Invalid credentials'}
                        print(f"✗ Authentication failed for user {username}")

                elif not authenticated:
                    response = {'status': 'error', 'message': 'Not authenticated. Use login first'}

                # File operations
                elif command == 'create_file':
                    filename = request.get('filename')
                    content = request.get('content', '')

                    filepath = get_safe_path(filename)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)

                    add_history(filename, 'create_file', current_user, 'File created on server')
                    response = {'status': 'success', 'message': f'File {filename} created on server'}
                    print(f"✓ File created: {filename}")

                elif command == 'upload':
                    filename = request.get('filename')
                    content = request.get('content', '')

                    filepath = get_safe_path(filename)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)

                    add_history(filename, 'upload', current_user, 'File uploaded from client')
                    response = {'status': 'success', 'message': f'File {filename} uploaded'}
                    print(f"✓ File uploaded: {filename}")

                elif command == 'rename_file':
                    old_name = request.get('old_name')
                    new_name = request.get('new_name')
                    old_path = get_safe_path(old_name)
                    new_path = get_safe_path(new_name)

                    if not os.path.exists(old_path):
                        response = {'status': 'error', 'message': f'File {old_name} does not exist'}
                    elif os.path.exists(new_path):
                        response = {'status': 'error', 'message': f'File {new_name} already exists'}
                    else:
                        os.rename(old_path, new_path)

                        history = load_history()
                        history[new_name] = history.pop(old_name, [])
                        save_history(history)
                        add_history(new_name, 'rename_file', current_user, f'Renamed from {old_name} to {new_name}')

                        response = {'status': 'success', 'message': f'File renamed from {old_name} to {new_name}'}
                        print(f"✓ File renamed: {old_name} -> {new_name}")

                elif command == 'read_file':
                    filename = request.get('filename')
                    filepath = get_safe_path(filename)

                    if not os.path.exists(filepath):
                        response = {'status': 'error', 'message': f'File {filename} does not exist'}
                    else:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        add_history(filename, 'read_file', current_user, 'File content was read')
                        response = {'status': 'success', 'message': f'File {filename} read successfully', 'content': content}
                        print(f"✓ File read: {filename}")

                elif command == 'download':
                    filename = request.get('filename')
                    filepath = get_safe_path(filename)

                    if not os.path.exists(filepath):
                        response = {'status': 'error', 'message': f'File {filename} does not exist'}
                    else:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        add_history(filename, 'download', current_user, 'File downloaded by client')
                        response = {'status': 'success', 'message': f'File {filename} downloaded', 'filename': filename, 'content': content}
                        print(f"✓ File downloaded: {filename}")

                elif command == 'edit_file':
                    filename = request.get('filename')
                    new_content = request.get('content', '')
                    filepath = get_safe_path(filename)

                    if not os.path.exists(filepath):
                        response = {'status': 'error', 'message': f'File {filename} does not exist'}
                    else:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        add_history(filename, 'edit_file', current_user, 'File content was edited')
                        response = {'status': 'success', 'message': f'File {filename} edited successfully'}
                        print(f"✓ File edited: {filename}")

                elif command == 'see_file_operation_history':
                    filename = request.get('filename')
                    filepath = get_safe_path(filename)

                    if not os.path.exists(filepath):
                        response = {'status': 'error', 'message': f'File {filename} does not exist'}
                    else:
                        response = {'status': 'success', 'message': format_history(filename)}
                        print(f"✓ History displayed for: {filename}")

                elif command == 'list_files':
                    files = get_server_files()
                    response = {'status': 'success', 'files': files}
                    print(f"✓ Files listed: {len(files)} files found")

                elif command == 'logout':
                    authenticated = False
                    current_user = None
                    response = {'status': 'success', 'message': 'Logged out'}
                    print(f"✓ User logged out")

                else:
                    response = {'status': 'error', 'message': f'Unknown command: {command}'}

            except Exception as e:
                response = {'status': 'error', 'message': str(e)}
                print(f"✗ Error: {str(e)}")

            # Send response
            conn.send(json.dumps(response).encode('utf-8'))

    except Exception as e:
        print(f"✗ Connection error: {str(e)}")
    finally:
        conn.close()
        print(f"🔌 Client disconnected from {addr}")


def start_server():
    """Start FTP server"""
    ensure_files_dir()

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((SERVER_HOST, SERVER_PORT))
    server_socket.listen(5)

    print("=" * 60)
    print("🚀 FTP SERVER STARTED")
    print("=" * 60)
    print(f"Host: {SERVER_HOST}")
    print(f"Port: {SERVER_PORT}")
    print(f"Files Directory: {FILES_DIR}")
    print(f"Default User: {DEFAULT_USER}")
    print(f"Default Password: {DEFAULT_PASSWORD}")
    print("=" * 60)

    try:
        while True:
            conn, addr = server_socket.accept()
            client_thread = threading.Thread(target=handle_client, args=(conn, addr))
            client_thread.daemon = True
            client_thread.start()
    except KeyboardInterrupt:
        print("\n\n⛔ Server shutting down...")
    finally:
        server_socket.close()


if __name__ == '__main__':
    start_server()
