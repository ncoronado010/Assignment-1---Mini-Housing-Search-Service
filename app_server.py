import argparse
import socket
import time
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

# Client <-> App Server protocol:
# Requests: LIST | SEARCH city=... max_price=... | QUIT
# Responses:
#   OK RESULT <n>\n
#   listing lines (n)
#   END\n
# or ERROR <msg>\n
#
# App Server <-> Data Server protocol:
#   RAW_LIST
#   RAW_SEARCH city=... max_price=...
# same response framing: OK RESULT <n> ... END

LOG_FILE = "app_server.log"

def log_line(direction: str, msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{ts} {direction} {msg}\n")

def read_line(conn: socket.socket) -> Optional[str]:
    buf = b""
    while True:
        chunk = conn.recv(4096)
        print(f"TEST chunk being passed into app_server.read_line:\n {chunk}") #DEBUGGING --------------------
        if not chunk:
            return None
        buf += chunk
        if b"\n" in buf:
            line, _ = buf.split(b"\n", 1)
            return line.decode("ascii", errors="replace").strip()

def recv_framed_response(conn: socket.socket) -> Tuple[bool, List[str], str]:
    # Reads until END or ERROR
    lines: List[str] = []
    while True:
        line = read_line(conn)
        print(f"TEST Line being read by app_server.recv_framed\n {line}") #DEBUGGING -----------------------
        if line is None:
            return False, [], "connection closed while reading response TEST B"
        lines.append(line)
        if line.startswith("ERROR "):
            return False, lines, line[6:]
        if line == "END":
            return True, lines, ""

def parse_kv(parts: List[str]) -> Dict[str, str]:
    kv = {}
    for p in parts:
        if "=" not in p:
            raise ValueError(f"bad field '{p}' (expected key=value)")
        k, v = p.split("=", 1)
        kv[k.strip()] = v.strip()
    return kv

def parse_listing_line(line: str) -> Dict[str, str]:
    # id=1;city=LongBeach;address=...;price=2200;bedrooms=2
    out: Dict[str, str] = {}
    fields = line.split(";")
    for f in fields:
        if "=" not in f:
            continue
        k, v = f.split("=", 1)
        out[k] = v
    return out

def rank_listings(listing_lines: List[str]) -> List[str]:
    # Ranking rule: price ascending, then bedrooms descending
    parsed = []
    for ln in listing_lines:
        d = parse_listing_line(ln)
        try:
            price = int(d.get("price", "999999999"))
        except ValueError:
            price = 999999999
        try:
            beds = int(d.get("bedrooms", "0"))
        except ValueError:
            beds = 0
        parsed.append((price, -beds, ln))
    parsed.sort(key=lambda x: (x[0], x[1]))
    return [x[2] for x in parsed]

class LRUCache:
    def __init__(self, max_size: int = 50) -> None:
        self.max_size = max_size
        self._od: "OrderedDict[str, List[str]]" = OrderedDict()

    def get(self, key: str) -> Optional[List[str]]:
        if key not in self._od:
            return None
        self._od.move_to_end(key)
        return self._od[key]

    def put(self, key: str, value: List[str]) -> None:
        self._od[key] = value
        self._od.move_to_end(key)
        while len(self._od) > self.max_size:
            self._od.popitem(last=False)

def forward_to_data_server(data_host: str, data_port: int, cmd: str):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3.0)
            s.connect((data_host, data_port))
            s.sendall((cmd + "\n").encode("ascii"))
            ok, lines, err = recv_framed_response(s)
            return ok, lines, err
    except Exception as e:
        return False, [], f"data server unreachable: {e}"

def handle_client_command(
    raw_cmd: str,
    cache: Optional[LRUCache],
    data_host: str,
    data_port: int,
    cache_enabled: bool,
) -> List[str]:
    raw_cmd = raw_cmd.strip()
    parts = raw_cmd.split()
    if not parts:
        return [f"ERROR empty command\n"]

    cmd = parts[0]

    if cmd == "QUIT":
        return ["OK RESULT 0\n", "END\n"]  # client will close after receiving OK

    if cmd == "LIST":
        cache_key = raw_cmd
        if cache_enabled and cache is not None:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

        ok, lines, err = forward_to_data_server(data_host, data_port, "RAW_LIST")
        if not ok:
            return [f"ERROR {err}\n"]

        # lines: ["OK RESULT n", <n listing lines>, "END"]
        header = lines[0]
        listing_lines = lines[1:-1]
        ranked = rank_listings(listing_lines)

        resp = [header + "\n"] + [ln + "\n" for ln in ranked] + ["END\n"]
        if cache_enabled and cache is not None:
            cache.put(cache_key, resp)
        return resp

    if cmd == "SEARCH":
        try:
            kv = parse_kv(parts[1:])
            if "city" not in kv or "max_price" not in kv:
                return ["ERROR SEARCH requires city and max_price\n"]
            # Validate int early:
            int(kv["max_price"])
        except ValueError as e:
            return [f"ERROR {str(e)}\n"]

        cache_key = raw_cmd
        if cache_enabled and cache is not None:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

        ds_cmd = f"RAW_SEARCH city={kv['city']} max_price={kv['max_price']}"
        ok, lines, err = forward_to_data_server(data_host, data_port, ds_cmd)
        if not ok:
            return [f"ERROR {err}\n"]

        header = lines[0]
        listing_lines = lines[1:-1]
        ranked = rank_listings(listing_lines)

        resp = [header + "\n"] + [ln + "\n" for ln in ranked] + ["END\n"]
        if cache_enabled and cache is not None:
            cache.put(cache_key, resp)
        return resp

    return [f"ERROR unknown command '{cmd}'\n"]

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--data-host", default="127.0.0.1")
    ap.add_argument("--data-port", type=int, default=5001)
    ap.add_argument("--cache", action="store_true", help="enable cache")
    ap.add_argument("--cache-size", type=int, default=50)
    args = ap.parse_args()

    cache = LRUCache(args.cache_size) if args.cache else None

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.host, args.port))
    srv.listen(5)

    print(f"[app_server] listening on {args.host}:{args.port} (cache={'ON' if args.cache else 'OFF'})")
    print(f"[app_server] data server at {args.data_host}:{args.data_port}")
    log_line("INFO", f"app_server started host={args.host} port={args.port} cache={'ON' if args.cache else 'OFF'}")

    while True:
        conn, addr = srv.accept()
        with conn:
            log_line("INFO", f"client connected {addr}")
            while True:
                line = read_line(conn)
                if line is None:
                    log_line("INFO", f"client disconnected {addr}")
                    break

                log_line("REQ", f"from={addr} {line}")
                try:
                    resp_lines = handle_client_command(
                        raw_cmd=line,
                        cache=cache,
                        data_host=args.data_host,
                        data_port=args.data_port,
                        cache_enabled=args.cache,
                    )
                except Exception as e:
                    resp_lines = [f"ERROR internal server error: {e}\n"]

                # Log replies (single-line log per reply chunk)
                for ln in resp_lines:
                    log_line("RESP", f"to={addr} {ln.rstrip()}")

                conn.sendall("".join(resp_lines).encode("ascii"))

                if line.strip().startswith("QUIT"):
                    log_line("INFO", f"closing connection {addr}")
                    break

if __name__ == "__main__":
    main()