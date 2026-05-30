"""Production startup preflight: Redis check and LAN URL display."""
import os
import socket
import sys


def main():
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    try:
        import redis

        redis.from_url(redis_url).ping()
    except Exception as exc:
        print(f"[ERROR] Cannot connect to Redis ({redis_url}): {exc}")
        print("Please start Redis before running start_production.bat")
        return 1

    print("[OK] Redis is ready")
    print()
    print("[2/3] Access URLs")
    print("  Local:  http://127.0.0.1:8080")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        lan_ip = sock.getsockname()[0]
        sock.close()
        print(f"  LAN:    http://{lan_ip}:8080")
    except Exception:
        print("  LAN:    run ipconfig to find your IPv4 address")
    return 0


if __name__ == "__main__":
    sys.exit(main())
