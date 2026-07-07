"""config-manager CLI 入口（T10）。

用法：
    python -m src.config_manager validate <file>          # 校验配置
    python -m src.config_manager impact <old> <new>        # 影响范围分析
    python -m src.config_manager log <file> [--n 10]       # 配置 git 历史
    python -m src.config_manager rollback <file> <commit>  # 回滚配置
    python -m src.config_manager example [--out <file>]    # 生成示例配置
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.config_manager.example import generate_example, write_example
from src.config_manager.manager import DefaultConfigManager, GitError

DEFAULT_CONFIG_PATH = Path("config/strategies.yaml")


def cmd_validate(args: argparse.Namespace) -> int:
    text = Path(args.file).read_text(encoding="utf-8")
    manager = DefaultConfigManager(args.file)
    issues = manager.validate(text)
    if not issues:
        print("✓ 配置校验通过")
        return 0
    print(f"✗ 发现 {len(issues)} 个问题：")
    for issue in issues:
        print(f"  {issue}")
    return 1


def cmd_impact(args: argparse.Namespace) -> int:
    manager = DefaultConfigManager(args.new)
    old = manager.load(args.old)
    new = manager.load(args.new)
    impacts = manager.analyze_impact(old, new)
    if not impacts:
        print("无配置变更")
        return 0
    print(f"检测到 {len(impacts)} 类变更：")
    for imp in impacts:
        print(f"\n[{imp.change_type}] {imp.summary}")
        if imp.added:
            print(f"  新增：{', '.join(imp.added)}")
        if imp.removed:
            print(f"  移除：{', '.join(imp.removed)}")
        if imp.affected_funds:
            print(f"  受影响基金：{', '.join(imp.affected_funds)}")
        if imp.requires_backtest_rerun:
            print("  ⚠ 需要重跑回测")
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    manager = DefaultConfigManager(args.file)
    try:
        entries = manager.log(args.n)
    except GitError as e:
        print(f"✗ git 错误：{e}")
        return 1
    if not entries:
        print("无提交历史")
        return 0
    for entry in entries:
        short = entry["hash"][:8]
        print(f"{short}  {entry['date']}  {entry['message']}")
    return 0


def cmd_rollback(args: argparse.Namespace) -> int:
    manager = DefaultConfigManager(args.file)
    try:
        config = manager.rollback(args.commit)
    except GitError as e:
        print(f"✗ git 错误：{e}")
        return 1
    print(f"✓ 已回滚 {args.file} 到 {args.commit}")
    print(f"  当前观察池基金数：{len(config.observation_pool)}")
    print(f"  筛选规则数：{len(config.screener_rules)}")
    print(f"  信号规则数：{len(config.signal_rules)}")
    return 0


def cmd_example(args: argparse.Namespace) -> int:
    if args.out:
        path = write_example(args.out)
        print(f"✓ 示例配置已写入 {path}")
    else:
        print(generate_example())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="src.config_manager",
        description="策略配置管理（校验 / 影响范围 / 版本管理）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="校验配置文件")
    p_validate.add_argument("file", help="YAML 配置文件路径")
    p_validate.set_defaults(func=cmd_validate)

    p_impact = sub.add_parser("impact", help="分析配置变更影响范围")
    p_impact.add_argument("old", help="旧配置 YAML 路径")
    p_impact.add_argument("new", help="新配置 YAML 路径")
    p_impact.set_defaults(func=cmd_impact)

    p_log = sub.add_parser("log", help="查看配置 git 历史")
    p_log.add_argument("file", help="YAML 配置文件路径")
    p_log.add_argument("--n", type=int, default=10, help="显示条数")
    p_log.set_defaults(func=cmd_log)

    p_rollback = sub.add_parser("rollback", help="回滚配置到指定 commit")
    p_rollback.add_argument("file", help="YAML 配置文件路径")
    p_rollback.add_argument("commit", help="commit hash（支持 HEAD~1）")
    p_rollback.set_defaults(func=cmd_rollback)

    p_example = sub.add_parser("example", help="生成示例配置")
    p_example.add_argument("--out", help="输出文件路径（省略则打印到 stdout）")
    p_example.set_defaults(func=cmd_example)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
