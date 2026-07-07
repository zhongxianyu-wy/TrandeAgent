"""API 启动入口：``python -m src.api`` → uvicorn 启动。

等价于 ``uvicorn src.api.app:app --reload --port 8000``。
"""
from __future__ import annotations


def main() -> None:
    """启动 uvicorn 服务。"""
    import uvicorn

    uvicorn.run(
        "src.api.app:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
