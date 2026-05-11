import socket
import json
import os
import threading
from datetime import datetime

# Configuration
SERVER_HOST = 'localhost'
SERVER_PORT = 5000
FILES_DIR = 'files'
HISTORY_FILE = 'file_history.json'
DEFAULT_USER = 'student'
DEFAULT_PASSWORD = '1234'

def ensure_files_dir():
    """Ensure files directory exists"""
    if not os.path.exists(FILES_DIR):
        os.makedirs(FILES_DIR)
        print(f"[OK] Directory '{FILES_DIR}' created")


history_lock = threading.Lock()


def get_safe_filename(filename):
    """Validate filename and prevent paths like ../file.txt"""
    if not filename:
        return None

    filename = filename.strip()
    if not filename or filename != os.path.basename(filename):
        return None

    return filename


def load_history():
    """Load file operation history from disk"""
    if not os.path.exists(HISTORY_FILE):
        return {}

    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_history(history):
    """Save file operation history to disk"""
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=4)


def add_history(filename, operation, user, details=''):
    """Add one operation to a file's history"""
    safe_filename = get_safe_filename(filename)
    if not safe_filename:
        return

    entry = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'user': user or 'unknown',
        'operation': operation,
        'details': details
    }

    with history_lock:
        history = load_history()
        history.setdefault(safe_filename, []).append(entry)
        save_history(history)


def rename_history(old_name, new_name, user):
    """Move history from old filename to new filename and record rename operation"""
    with history_lock:
        history = load_history()
        old_entries = history.pop(old_name, [])
        history.setdefault(new_name, []).extend(old_entries)
        history[new_name].append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'user': user or 'unknown',
            'operation': 'rename',
            'details': f'Renamed from {old_name} to {new_name}'
        })
        save_history(history)


def authenticate(username, password):
    """Authenticate user"""
    return username == DEFAULT_USER and password == DEFAULT_PASSWORD


def handle_client(conn, addr):
    """Handle client connection"""
    print(f"\n Client connected from {addr}")
    authenticated = False
    current_user = None
    
    try:
        while True:
            # Receive request
            request_data = conn.recv(65536).decode('utf-8')
            if not request_data:
                break
            
            try:
                request = json.loads(request_data)
                command = request.get('command')
                
                print(f" Command received: {command}")
                
                # Authentication
                if command == 'login':
                    username = request.get('username')
                    password = request.get('password')
                    
                    if authenticate(username, password):
                        authenticated = True
                        current_user = username
                        response = {'status': 'success', 'message': f'Welcome {username}!'}
                        print(f"[OK] User {username} authenticated")
                    else:
                        response = {'status': 'error', 'message': 'Invalid credentials'}
                        print(f"[ERROR] Authentication failed for user {username}")
                
                elif not authenticated:
                    response = {'status': 'error', 'message': 'Not authenticated. Use login first'}
                
                # File operations
                elif command == 'create_file':
                    filename = get_safe_filename(request.get('filename'))
                    content = request.get('content', '')

                    if not filename:
                        response = {'status': 'error', 'message': 'Invalid filename'}
                    else:
                        filepath = os.path.join(FILES_DIR, filename)
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(content)

                        add_history(filename, 'create', current_user, 'File created on server')
                        response = {'status': 'success', 'message': f'File {filename} created on server'}
                        print(f"[OK] File created: {filename}")

                elif command == 'upload':
                    filename = get_safe_filename(request.get('filename'))
                    content = request.get('content', '')

                    if not filename:
                        response = {'status': 'error', 'message': 'Invalid filename'}
                    else:
                        filepath = os.path.join(FILES_DIR, filename)
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(content)

                        add_history(filename, 'upload', current_user, 'File uploaded from client')
                        response = {'status': 'success', 'message': f'File {filename} uploaded'}
                        print(f"[OK] File uploaded: {filename}")

                elif command == 'rename_file':
                    old_name = get_safe_filename(request.get('old_name'))
                    new_name = get_safe_filename(request.get('new_name'))

                    if not old_name or not new_name:
                        response = {'status': 'error', 'message': 'Invalid old or new filename'}
                    else:
                        old_path = os.path.join(FILES_DIR, old_name)
                        new_path = os.path.join(FILES_DIR, new_name)

                        if not os.path.exists(old_path):
                            response = {'status': 'error', 'message': f'File {old_name} does not exist'}
                        elif os.path.exists(new_path):
                            response = {'status': 'error', 'message': f'File {new_name} already exists'}
                        else:
                            os.rename(old_path, new_path)
                            rename_history(old_name, new_name, current_user)
                            response = {'status': 'success', 'message': f'File renamed from {old_name} to {new_name}'}
                            print(f"[OK] File renamed: {old_name} -> {new_name}")

                elif command == 'read_file':
                    filename = get_safe_filename(request.get('filename'))

                    if not filename:
                        response = {'status': 'error', 'message': 'Invalid filename'}
                    else:
                        filepath = os.path.join(FILES_DIR, filename)
                        if not os.path.exists(filepath):
                            response = {'status': 'error', 'message': f'File {filename} does not exist'}
                        else:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                content = f.read()
                            add_history(filename, 'read', current_user, 'File content read')
                            response = {'status': 'success', 'filename': filename, 'content': content}
                            print(f"[OK] File read: {filename}")

                elif command == 'download':
                    filename = get_safe_filename(request.get('filename'))

                    if not filename:
                        response = {'status': 'error', 'message': 'Invalid filename'}
                    else:
                        filepath = os.path.join(FILES_DIR, filename)
                        if not os.path.exists(filepath):
                            response = {'status': 'error', 'message': f'File {filename} does not exist'}
                        else:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                content = f.read()
                            add_history(filename, 'download', current_user, 'File downloaded by client')
                            response = {'status': 'success', 'filename': filename, 'content': content}
                            print(f"[OK] File downloaded: {filename}")

                elif command == 'edit_file':
                    filename = get_safe_filename(request.get('filename'))
                    content = request.get('content', '')

                    if not filename:
                        response = {'status': 'error', 'message': 'Invalid filename'}
                    else:
                        filepath = os.path.join(FILES_DIR, filename)
                        if not os.path.exists(filepath):
                            response = {'status': 'error', 'message': f'File {filename} does not exist'}
                        else:
                            with open(filepath, 'w', encoding='utf-8') as f:
                                f.write(content)
                            add_history(filename, 'edit', current_user, 'File content edited')
                            response = {'status': 'success', 'message': f'File {filename} edited successfully'}
                            print(f"[OK] File edited: {filename}")

                elif command == 'see_file_operation_history':
                    filename = get_safe_filename(request.get('filename'))

                    if not filename:
                        response = {'status': 'error', 'message': 'Invalid filename'}
                    else:
                        history = load_history()
                        entries = history.get(filename, [])
                        response = {'status': 'success', 'filename': filename, 'history': entries}
                        print(f"[OK] History shown for: {filename}")
                
                elif command == 'list_files':
                    files = os.listdir(FILES_DIR)
                    response = {'status': 'success', 'files': files}
                    print(f"[OK] Files listed: {len(files)} files found")
                
                elif command == 'logout':
                    authenticated = False
                    current_user = None
                    response = {'status': 'success', 'message': 'Logged out'}
                    print(f"[OK] User logged out")
                
                else:
                    response = {'status': 'error', 'message': f'Unknown command: {command}'}
                
            except Exception as e:
                response = {'status': 'error', 'message': str(e)}
                print(f"[ERROR] Error: {str(e)}")
            
            # Send response
            conn.send(json.dumps(response).encode('utf-8'))
    
    except Exception as e:
        print(f"[ERROR] Connection error: {str(e)}")
    finally:
        conn.close()
        print(f" Client disconnected from {addr}")


def start_server():
    """Start FTP server"""
    ensure_files_dir()
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((SERVER_HOST, SERVER_PORT))
    server_socket.listen(5)
    
    print("=" * 60)
    print(" FTP SERVER STARTED")
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
        print("\n\n Server shutting down...")
    finally:
        server_socket.close()


if __name__ == '__main__':
    start_server()
