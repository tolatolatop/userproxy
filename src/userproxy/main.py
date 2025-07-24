import argparse
import uvicorn
import os
from . import app


def main():
    parser = argparse.ArgumentParser(description="启动FastAPI WebSocket服务")
    parser.add_argument(
        '--mode', choices=['dev', 'prod'], default='dev', help='运行模式: dev 或 prod')
    parser.add_argument('--host', default='0.0.0.0', help='监听主机，默认0.0.0.0')
    parser.add_argument('--port', type=int, default=8000, help='监听端口，默认8000')
    args = parser.parse_args()

    if args.mode == 'dev':
        uvicorn.run("userproxy:app", host=args.host,
                    port=args.port, reload=True)
    else:
        uvicorn.run("userproxy:app", host=args.host,
                    port=args.port, reload=False, workers=2)


if __name__ == "__main__":
    main()
