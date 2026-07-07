"""飞书 IO CLI 入口（plan §7 / FR-5 / FR-7 / Step6 §5）。

用法：
    python -m src.feishu init            # 创建 Base + 表 + 字段 + 视图
    python -m src.feishu health          # 诊断 lark-cli / 凭证 / Base
    python -m src.feishu doctor          # PATH 诊断（T01）
    python -m src.feishu test-push       # 推送一张示例卡片
    python -m src.feishu install-cli     # 安装 lark-cli 二进制（npm）
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from loguru import logger

from src.feishu.cards import CardAction, CardElement, FeishuCard
from src.feishu.config import load_feishu_config
from src.feishu.error_codes import LarkCLINotInstalled
from src.feishu.lark_cli_client import EXPLICIT_PATH, LARK_CLI_BIN, LarkCLIClient

_SCHEMA_DIR = Path("config/feishu_base_schemas")
_CONFIG_PATH = "config/feishu.yaml"


def detect_lark_cli() -> str | None:
    """检测 lark-cli 是否安装，返回路径或 None。"""
    path_env = EXPLICIT_PATH + os.pathsep + os.environ.get("PATH", "")
    return shutil.which(LARK_CLI_BIN, path=path_env)


def detect_shell() -> str:
    """检测当前 shell（shellingham，用于 PATH 诊断）。"""
    try:
        import shellingham  # type: ignore

        name, _ = shellingham.detect_shell()
        return name
    except Exception:  # noqa: BLE001
        return os.environ.get("SHELL", "unknown")


def cmd_doctor() -> int:
    """PATH 诊断：检测 lark-cli 安装、PATH、npm global bin、shell。"""
    print("=" * 50)
    print("飞书 IO 诊断报告（PATH diagnostics）")
    print("=" * 50)
    cli = detect_lark_cli()
    print(f"lark-cli 路径   : {cli or '未找到（NOT INSTALLED）'}")
    print(f"当前 shell       : {detect_shell()}")
    print(f"显式 PATH        : {EXPLICIT_PATH}")
    print(f"当前 PATH        : {os.environ.get('PATH', '(空)')}")
    npm = shutil.which("npm")
    print(f"npm 路径         : {npm or '未找到'}")
    if not cli:
        print()
        print("⚠ lark-cli 未安装，请运行：")
        print("    python -m src.feishu install-cli")
        print("  或手动：npm install -g @larksuite/cli")
        print()
        print("⚠ 若使用 launchd 定时任务，确保 plist 的 PATH 含 npm global bin：")
        print(f"    {EXPLICIT_PATH}")
        return 1
    print()
    print("✓ lark-cli 已安装。")
    return 0


def cmd_health() -> int:
    config = load_feishu_config(_CONFIG_PATH, strict=False)
    client = LarkCLIClient(config, config_path=_CONFIG_PATH)
    result = client.health_check()
    print("=" * 50)
    print("飞书 IO 健康检查")
    print("=" * 50)
    print(f"lark_cli 安装 : {'✓' if result['lark_cli'] else '✗'}")
    print(f"凭证/token    : {'✓' if result['token'] else '✗'}")
    print(f"Base 已创建   : {'✓' if result['base'] else '✗'}")
    if result["advice"]:
        print()
        print("修复建议：")
        for i, advice in enumerate(result["advice"], 1):
            print(f"  {i}. {advice}")
        return 1
    print()
    print("✓ 全部就绪。")
    return 0


def cmd_init() -> int:
    config = load_feishu_config(_CONFIG_PATH, strict=False)
    client = LarkCLIClient(config, config_path=_CONFIG_PATH)
    try:
        url = client.init_base(_SCHEMA_DIR)
    except LarkCLINotInstalled as e:
        logger.error("{}", e)
        return 1
    print(f"Base 初始化完成：{url}")
    return 0


def cmd_test_push() -> int:
    config = load_feishu_config(_CONFIG_PATH, strict=False)
    client = LarkCLIClient(config, config_path=_CONFIG_PATH)
    card = FeishuCard(
        header={"template": "blue", "title": {"content": "📊 TrandeAgent 测试推送"}},
        elements=[
            CardElement(tag="markdown", content="**这是一条测试卡片**，收到说明推送链路正常。"),
            CardElement(
                tag="action",
                actions=[
                    CardAction(
                        text={"content": "查看详情"},
                        type="primary",
                        open_url="https://feishu.cn",
                    ).model_dump()
                ],
            ),
        ],
    )
    try:
        msg_id = client.send_card(card)
    except LarkCLINotInstalled as e:
        logger.error("{}", e)
        return 1
    print(f"测试卡片已推送 message_id={msg_id}")
    return 0


def cmd_install_cli() -> int:
    """一键安装 lark-cli 二进制（FR-7）。"""
    if detect_lark_cli():
        print("lark-cli 已安装，跳过。")
        return 0
    if not shutil.which("npm"):
        logger.error("未找到 npm，请先安装 Node.js（含 npm）。")
        return 1
    print("正在安装 @larksuite/cli ...")
    result = subprocess.run(
        ["npm", "install", "-g", "@larksuite/cli"],
        env={"PATH": EXPLICIT_PATH, **os.environ},
    )
    if result.returncode != 0:
        logger.error("安装失败（exit {}）", result.returncode)
        return result.returncode
    print("✓ 安装完成。下一步运行：python -m src.feishu health")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="src.feishu", description="飞书 IO CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="创建 Base + 表 + 字段 + 视图")
    sub.add_parser("health", help="诊断 lark-cli / 凭证 / Base")
    sub.add_parser("doctor", help="PATH 诊断")
    sub.add_parser("test-push", help="推送一张示例卡片")
    sub.add_parser("install-cli", help="安装 lark-cli 二进制（npm）")
    args = parser.parse_args(argv)

    if args.command == "init":
        return cmd_init()
    if args.command == "health":
        return cmd_health()
    if args.command == "doctor":
        return cmd_doctor()
    if args.command == "test-push":
        return cmd_test_push()
    if args.command == "install-cli":
        return cmd_install_cli()
    return 0


if __name__ == "__main__":
    sys.exit(main())
