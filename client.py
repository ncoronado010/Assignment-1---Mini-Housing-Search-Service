import argparse
import socket
import time
from typing import List, Tuple, Optional


def recv_framed_response(f) -> Tuple[bool, List[str], str]:
    lines: List[str] = []
    while True:
        line = f.readline()

        if not line:
            return False, lines, "connection closed while reading response TEST A"
        text = line.decode("ascii", errors="replace").rstrip("\n")
        lines.append(text)

        if text.startswith("ERROR "):
            return False, lines, text[6:]
        if text == "END":
            return True, lines, ""


def send_cmd(f, cmd: str) -> Tuple[bool, List[str], str]:
    f.write((cmd.strip() + "\n").encode("ascii"))
    f.flush()
    return recv_framed_response(f)


def print_results(lines: List[str]) -> None:
    if not lines:
        print("(no response)")
        return

    header = lines[0]
    if header.startswith("ERROR "):
        print(header)
        return

    listing_lines = lines[1:-1]  
    if not listing_lines:
        print(header)
        print("(no matches)")
        return

    rows = []
    for ln in listing_lines:
        fields = {}
        for part in ln.split(";"):
            if "=" in part:
                k, v = part.split("=", 1)
                fields[k] = v
        rows.append(fields)

    cols = ["id", "city", "address", "price", "bedrooms"]
    widths = {c: max(len(c), max((len(r.get(c, "")) for r in rows), default=0)) for c in cols}

    print(header)
    print("-" * (sum(widths.values()) + len(cols) * 3 + 1))
    print(" | ".join(c.ljust(widths[c]) for c in cols))
    print("-" * (sum(widths.values()) + len(cols) * 3 + 1))
    for r in rows:
        print(" | ".join(r.get(c, "").ljust(widths[c]) for c in cols))
    print("-" * (sum(widths.values()) + len(cols) * 3 + 1))

def interactive(f) -> None:
    print("Commands:")
    print("  LIST")
    print("  SEARCH city=<CityName> max_price=<Integer>")
    print("  QUIT")
    while True:
        cmd = input("> ").strip()
        if not cmd:
            continue
        ok, lines, err = send_cmd(f, cmd)
        if not ok:
            print(lines[0] if lines else f"ERROR {err}")
        else:
            print_results(lines)

        if cmd.upper().startswith("QUIT"):
            break

def benchmark(f, command: str, n: int) -> None:
    t0 = time.time()
    for _ in range(n):
        ok, lines, err = send_cmd(f, command)
        if not ok:
            print(f"Benchmark request failed: {err}")
            return
    t1 = time.time()
    total = t1 - t0
    avg = total / n
    print(f"Benchmark: {n}x '{command}'")
    print(f"Total time: {total:.6f} sec")
    print(f"Avg time/request: {avg:.6f} sec")

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--benchmark", action="store_true")
    ap.add_argument("--command", default="SEARCH city=LongBeach max_price=2500")
    ap.add_argument("--n", type=int, default=50)
    args = ap.parse_args()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((args.host, args.port))
        f = s.makefile("rwb")

        if args.benchmark:
            benchmark(f, args.command, args.n)
            send_cmd(f, "QUIT")
        else:
            interactive(f)

if __name__ == "__main__":
    main()
