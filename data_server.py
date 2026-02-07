import json
import argparse
import socket
from typing import Dict, List, Tuple, Optional

def parse_kv_args(parts: List[str]) -> Dict[str, str]:
    kv = {}
    for p in parts:
        if "=" not in p:
            raise ValueError(f"bad field '{p}' (expected key=value)")
        k, v = p.split("=", 1)
        kv[k.strip()] = v.strip()
    return kv

def listing_to_line(item: Dict) -> str:
    return (
        f"id={item['id']};city={item['city']};address={item['address']};"
        f"price={item['price']};bedrooms={item['bedrooms']}\n"
    )

def read_line(conn: socket.socket) -> Optional[str]:
    buf = b""
    while True:
        chunk = conn.recv(4096)
        if not chunk:
            return None
        buf += chunk
        if b"\n" in buf:
            line, rest = buf.split(b"\n", 1)
            return line.decode("ascii", errors="replace").strip()

def send_response(conn: socket.socket, lines: List[str]) -> None:
    conn.sendall("".join(lines).encode("ascii"))

def handle_command(cmd: str, db: List[Dict]) -> Tuple[bool, List[Dict], str]:
    parts = cmd.strip().split()
    if not parts:
        return False, [], "empty command"

    if parts[0] == "RAW_LIST":
        return True, db, ""

    if parts[0] == "RAW_SEARCH":
        try:
            kv = parse_kv_args(parts[1:])
            if "city" not in kv or "max_price" not in kv:
                return False, [], "RAW_SEARCH requires city and max_price"
            city = kv["city"]
            try:
                max_price = int(kv["max_price"])
            except ValueError:
                return False, [], "max_price must be an integer"

            results = [
                x for x in db
                if x.get("city") == city and int(x.get("price", 10**18)) <= max_price
            ]
            return True, results, ""
        except ValueError as e:
            return False, [], str(e)

    return False, [], f"unknown command '{parts[0]}'"

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5001)
    ap.add_argument("--data", default="listings.json")
    args = ap.parse_args()

    with open(args.data, "r", encoding="utf-8") as f:
        db = json.load(f)
        if not isinstance(db, list):
            raise ValueError("listings.json must contain a JSON array")

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.host, args.port))
    srv.listen(5)
    print(f"[data_server] listening on {args.host}:{args.port}, loaded {len(db)} listings from {args.data}")

    while True:
        conn, addr = srv.accept()
        with conn:
            line = read_line(conn)
            if line is None:
                continue

            ok, rows, err = handle_command(line, db)
            if not ok:
                send_response(conn, [f"ERROR {err}\n"])
                continue

            out = [f"OK RESULT {len(rows)}\n"]
            for item in rows:
                out.append(listing_to_line(item))
            out.append("END\n")
            send_response(conn, out)




if __name__ == "__main__":
    main()
