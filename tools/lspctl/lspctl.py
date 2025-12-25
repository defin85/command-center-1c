#!/usr/bin/env python3
import argparse
import json
import os
import queue
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace


EXT_LANGUAGE = {
    ".go": "go",
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescriptreact",
    ".js": "javascript",
    ".jsx": "javascriptreact",
    ".rs": "rust",
}

LANG_SERVER = {
    "go": ["gopls"],
    "python": ["pyright-langserver", "--stdio"],
    "typescript": ["typescript-language-server", "--stdio"],
    "typescriptreact": ["typescript-language-server", "--stdio"],
    "javascript": ["typescript-language-server", "--stdio"],
    "javascriptreact": ["typescript-language-server", "--stdio"],
    "rust": ["rust-analyzer"],
}

DEFAULT_SOCKET = "/tmp/lspctl.sock"


class LspClient:
    def __init__(self, cmd, root_uri, root_name, timeout, env=None, init_options=None):
        self._cmd = cmd
        self._root_uri = root_uri
        self._root_name = root_name
        self._timeout = timeout
        self._env = env
        self._init_options = init_options
        self._proc = None
        self._next_id = 1
        self._pending = {}
        self._pending_lock = threading.Lock()
        self._io_lock = threading.Lock()
        self._diagnostics = {}
        self.init_result = None

    def start(self):
        self._proc = subprocess.Popen(
            self._cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self._env,
        )
        t = threading.Thread(target=self._reader, daemon=True)
        t.start()

    def _reader(self):
        stdout = self._proc.stdout
        while True:
            headers = {}
            line = stdout.readline()
            if not line:
                break
            if line == b"\r\n":
                continue
            while line and line != b"\r\n":
                try:
                    key, value = line.decode("ascii").split(":", 1)
                except ValueError:
                    key, value = None, None
                if key:
                    headers[key.strip().lower()] = value.strip()
                line = stdout.readline()
            length = int(headers.get("content-length", "0"))
            if length <= 0:
                continue
            body = stdout.read(length)
            try:
                msg = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            if "id" in msg:
                with self._pending_lock:
                    q = self._pending.get(msg["id"])
                if q:
                    q.put(msg)
            elif msg.get("method") == "textDocument/publishDiagnostics":
                params = msg.get("params", {})
                uri = params.get("uri")
                if uri:
                    self._diagnostics[uri] = params.get("diagnostics", [])

    def _send(self, payload):
        body = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        self._proc.stdin.write(header + body)
        self._proc.stdin.flush()

    def send_request(self, method, params):
        with self._io_lock:
            req_id = self._next_id
            self._next_id += 1
            payload = {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": method,
                "params": params,
            }
            q = queue.Queue()
            with self._pending_lock:
                self._pending[req_id] = q
            self._send(payload)
            try:
                msg = q.get(timeout=self._timeout)
            except queue.Empty:
                raise TimeoutError(f"timeout waiting for {method}")
            finally:
                with self._pending_lock:
                    self._pending.pop(req_id, None)
            if "error" in msg:
                raise RuntimeError(msg["error"])
            return msg.get("result")

    def send_notification(self, method, params):
        with self._io_lock:
            payload = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
            }
            self._send(payload)

    def initialize(self):
        params = {
            "processId": os.getpid(),
            "rootUri": self._root_uri,
            "capabilities": {},
            "workspaceFolders": [
                {
                    "uri": self._root_uri,
                    "name": self._root_name,
                }
            ],
        }
        if self._init_options:
            params["initializationOptions"] = self._init_options
        result = self.send_request("initialize", params)
        self.send_notification("initialized", {})
        self.init_result = result
        return result

    def wait_for_diagnostics(self, uri):
        deadline = time.time() + self._timeout
        while time.time() < deadline:
            if uri in self._diagnostics:
                return self._diagnostics[uri]
            time.sleep(0.05)
        raise TimeoutError("timeout waiting for diagnostics")

    def shutdown(self):
        try:
            self.send_request("shutdown", None)
            self.send_notification("exit", {})
        except Exception:
            pass
        try:
            self._proc.terminate()
        except Exception:
            pass


def path_to_uri(path):
    return Path(path).absolute().as_uri()


def infer_language(path):
    return EXT_LANGUAGE.get(Path(path).suffix)


def load_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def to_lsp_position(line, col):
    return {"line": line - 1, "character": col - 1}


def require_arg(value, name):
    if value is None:
        raise ValueError(f"missing required argument: {name}")


def resolve_server_cmd(lang, override_cmd):
    if override_cmd:
        return override_cmd
    if lang in LANG_SERVER:
        return LANG_SERVER[lang]
    raise ValueError(f"unsupported language: {lang}")


class LspPool:
    def __init__(self):
        self._clients = {}
        self._lock = threading.Lock()

    def get_client(
        self, lang, server_cmd, root_uri, root_name, timeout, venv_path, env, init_options
    ):
        key = (lang or "unknown", root_uri, tuple(server_cmd), venv_path)
        with self._lock:
            client = self._clients.get(key)
            if client:
                return client
            client = LspClient(
                server_cmd,
                root_uri,
                root_name,
                timeout,
                env=env,
                init_options=init_options,
            )
            client.start()
            client.initialize()
            self._clients[key] = client
            return client

    def shutdown(self):
        with self._lock:
            clients = list(self._clients.values())
            self._clients.clear()
        for client in clients:
            client.shutdown()


def find_venv(start_path, root_path):
    candidates = [".venv", "venv"]
    current = Path(start_path).absolute()
    root = Path(root_path).absolute()
    for path in [current] + list(current.parents):
        for name in candidates:
            candidate = path / name
            if candidate.is_dir() and (candidate / "bin" / "python").exists():
                return candidate
        if path == root:
            break
    return None


def resolve_venv(args, root_path):
    if args.venv:
        venv_path = Path(args.venv).expanduser().absolute()
        if not venv_path.is_dir():
            raise ValueError(f"venv path not found: {venv_path}")
        return venv_path
    start_path = Path(args.file).absolute() if args.file else Path(root_path)
    return find_venv(start_path, root_path)


def setup_client(args, pool=None):
    root_path = Path(args.root or os.getcwd()).absolute()
    root_uri = root_path.as_uri()
    root_name = root_path.name or "workspace"
    server_cmd = resolve_server_cmd(args.lang, args.server_cmd)
    env = None
    init_options = None
    venv_path = None
    if args.lang == "python":
        venv_path = resolve_venv(args, root_path)
        if venv_path:
            env = os.environ.copy()
            env["VIRTUAL_ENV"] = str(venv_path)
            env["PATH"] = str(venv_path / "bin") + os.pathsep + env.get("PATH", "")
            init_options = {
                "python": {
                    "venvPath": str(venv_path.parent),
                    "venv": venv_path.name,
                }
            }
    elif args.venv:
        raise ValueError("--venv is only supported for --lang python")
    if pool:
        venv_key = str(venv_path) if venv_path else None
        return pool.get_client(
            args.lang,
            server_cmd,
            root_uri,
            root_name,
            args.timeout,
            venv_key,
            env,
            init_options,
        )
    client = LspClient(
        server_cmd, root_uri, root_name, args.timeout, env=env, init_options=init_options
    )
    client.start()
    client.initialize()
    return client


def open_document(client, path, language_id):
    if not language_id:
        raise ValueError("unable to infer language; use --lang")
    uri = path_to_uri(path)
    text = load_file(path)
    client.send_notification(
        "textDocument/didOpen",
        {
            "textDocument": {
                "uri": uri,
                "languageId": language_id,
                "version": 1,
                "text": text,
            }
        },
    )
    return uri


def command_definition(args, pool=None):
    require_arg(args.file, "--file")
    require_arg(args.line, "--line")
    require_arg(args.col, "--col")
    args.lang = args.lang or infer_language(args.file)
    client = setup_client(args, pool)
    uri = open_document(client, args.file, args.lang)
    params = {
        "textDocument": {"uri": uri},
        "position": to_lsp_position(args.line, args.col),
    }
    return client.send_request("textDocument/definition", params)


def command_references(args, pool=None):
    require_arg(args.file, "--file")
    require_arg(args.line, "--line")
    require_arg(args.col, "--col")
    args.lang = args.lang or infer_language(args.file)
    client = setup_client(args, pool)
    uri = open_document(client, args.file, args.lang)
    params = {
        "textDocument": {"uri": uri},
        "position": to_lsp_position(args.line, args.col),
        "context": {"includeDeclaration": args.include_declaration},
    }
    return client.send_request("textDocument/references", params)


def command_hover(args, pool=None):
    require_arg(args.file, "--file")
    require_arg(args.line, "--line")
    require_arg(args.col, "--col")
    args.lang = args.lang or infer_language(args.file)
    client = setup_client(args, pool)
    uri = open_document(client, args.file, args.lang)
    params = {
        "textDocument": {"uri": uri},
        "position": to_lsp_position(args.line, args.col),
    }
    return client.send_request("textDocument/hover", params)


def command_rename(args, pool=None):
    require_arg(args.file, "--file")
    require_arg(args.line, "--line")
    require_arg(args.col, "--col")
    require_arg(args.new_name, "--new-name")
    args.lang = args.lang or infer_language(args.file)
    client = setup_client(args, pool)
    uri = open_document(client, args.file, args.lang)
    params = {
        "textDocument": {"uri": uri},
        "position": to_lsp_position(args.line, args.col),
        "newName": args.new_name,
    }
    return client.send_request("textDocument/rename", params)


def command_document_symbol(args, pool=None):
    require_arg(args.file, "--file")
    args.lang = args.lang or infer_language(args.file)
    client = setup_client(args, pool)
    uri = open_document(client, args.file, args.lang)
    params = {"textDocument": {"uri": uri}}
    return client.send_request("textDocument/documentSymbol", params)


def command_workspace_symbol(args, pool=None):
    require_arg(args.query, "--query")
    if not args.lang and not args.server_cmd:
        raise ValueError("missing required argument: --lang (or --server-cmd)")
    client = setup_client(args, pool)
    params = {"query": args.query}
    return client.send_request("workspace/symbol", params)


def command_diagnostics(args, pool=None):
    require_arg(args.file, "--file")
    args.lang = args.lang or infer_language(args.file)
    client = setup_client(args, pool)
    uri = open_document(client, args.file, args.lang)
    caps = (client.init_result or {}).get("capabilities", {})
    if "diagnosticProvider" in caps:
        params = {"textDocument": {"uri": uri}}
        return client.send_request("textDocument/diagnostic", params)
    return {"uri": uri, "diagnostics": client.wait_for_diagnostics(uri)}

def normalize_args_dict(data):
    defaults = {
        "file": None,
        "line": None,
        "col": None,
        "query": None,
        "new_name": None,
        "include_declaration": False,
        "root": None,
        "lang": None,
        "venv": None,
        "timeout": 3.0,
        "server_cmd": None,
    }
    if data:
        defaults.update(data)
    return defaults


def command_dispatch(command, args, pool=None):
    if command == "definition":
        return command_definition(args, pool)
    if command == "references":
        return command_references(args, pool)
    if command == "hover":
        return command_hover(args, pool)
    if command == "diagnostics":
        return command_diagnostics(args, pool)
    if command == "rename":
        return command_rename(args, pool)
    if command == "documentSymbol":
        return command_document_symbol(args, pool)
    if command == "workspaceSymbol":
        return command_workspace_symbol(args, pool)
    raise ValueError("unknown command")


def read_json_line(fp):
    line = fp.readline()
    if not line:
        return None
    return json.loads(line.decode("utf-8"))


def write_json_line(fp, payload):
    data = json.dumps(payload, ensure_ascii=True).encode("utf-8") + b"\n"
    fp.write(data)
    fp.flush()


def handle_connection(conn, pool, stop_event):
    with conn:
        fp = conn.makefile("rwb")
        try:
            payload = read_json_line(fp)
            if payload is None:
                return
            command = payload.get("command")
            if command == "shutdown":
                stop_event.set()
                write_json_line(fp, {"result": {"status": "shutting down"}})
                return
            args_dict = normalize_args_dict(payload.get("args"))
            args = SimpleNamespace(**args_dict)
            result = command_dispatch(command, args, pool)
            write_json_line(fp, {"result": result})
        except Exception as exc:
            write_json_line(fp, {"error": str(exc)})


def run_server(args):
    socket_path = args.socket
    if os.path.exists(socket_path):
        try:
            test_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            test_sock.settimeout(0.2)
            test_sock.connect(socket_path)
            test_sock.close()
            raise RuntimeError(f"server already running on {socket_path}")
        except OSError:
            os.remove(socket_path)
    pool = LspPool()
    stop_event = threading.Event()
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.settimeout(0.5)
    server.bind(socket_path)
    server.listen()
    try:
        while not stop_event.is_set():
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            t = threading.Thread(
                target=handle_connection, args=(conn, pool, stop_event), daemon=True
            )
            t.start()
    finally:
        server.close()
        pool.shutdown()
        try:
            os.remove(socket_path)
        except OSError:
            pass


def call_daemon(args):
    socket_path = args.socket
    payload = {
        "command": args.call_command,
        "args": normalize_args_dict({
            "file": args.file,
            "line": args.line,
            "col": args.col,
            "query": args.query,
            "new_name": args.new_name,
            "include_declaration": args.include_declaration,
            "root": args.root,
            "lang": args.lang,
            "venv": args.venv,
            "timeout": args.timeout,
            "server_cmd": args.server_cmd,
        }),
    }
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(args.timeout)
    sock.connect(socket_path)
    with sock:
        fp = sock.makefile("rwb")
        write_json_line(fp, payload)
        response = read_json_line(fp)
        if response is None:
            raise RuntimeError("empty response from daemon")
        if "error" in response:
            raise RuntimeError(response["error"])
        return response.get("result")
def shutdown_daemon(args):
    socket_path = args.socket
    payload = {"command": "shutdown"}
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(args.timeout)
    sock.connect(socket_path)
    with sock:
        fp = sock.makefile("rwb")
        write_json_line(fp, payload)
        response = read_json_line(fp)
        if response is None:
            raise RuntimeError("empty response from daemon")
        if "error" in response:
            raise RuntimeError(response["error"])
        return response.get("result")



def build_parser():
    p = argparse.ArgumentParser(description="LSP CLI helper")
    sub = p.add_subparsers(dest="command", required=True)
    commands = [
        "definition",
        "references",
        "hover",
        "diagnostics",
        "rename",
        "documentSymbol",
        "workspaceSymbol",
    ]

    def add_common_args(sp):
        sp.add_argument("--file")
        sp.add_argument("--line", type=int)
        sp.add_argument("--col", type=int)
        sp.add_argument("--query")
        sp.add_argument("--new-name")
        sp.add_argument("--include-declaration", action="store_true")
        sp.add_argument("--root")
        sp.add_argument("--lang")
        sp.add_argument("--venv")
        sp.add_argument("--timeout", type=float, default=3.0)
        sp.add_argument("--server-cmd", nargs="+")

    for cmd in commands:
        sp = sub.add_parser(cmd)
        add_common_args(sp)

    sp_serve = sub.add_parser("serve")
    sp_serve.add_argument("--socket", default=DEFAULT_SOCKET)

    sp_call = sub.add_parser("call")
    sp_call.add_argument("call_command", choices=commands)
    add_common_args(sp_call)
    sp_call.add_argument("--socket", default=DEFAULT_SOCKET)

    sp_shutdown = sub.add_parser("shutdown")
    sp_shutdown.add_argument("--socket", default=DEFAULT_SOCKET)
    sp_shutdown.add_argument("--timeout", type=float, default=3.0)
    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "serve":
            run_server(args)
            return
        if args.command == "call":
            result = call_daemon(args)
            print(json.dumps({"result": result}, ensure_ascii=True))
            return
        if args.command == "shutdown":
            result = shutdown_daemon(args)
            print(json.dumps({"result": result}, ensure_ascii=True))
            return
        result = command_dispatch(args.command, args)
        print(json.dumps({"result": result}, ensure_ascii=True))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True))
        sys.exit(1)


if __name__ == "__main__":
    main()
