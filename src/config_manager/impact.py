"""配置变更影响范围分析（T05/T06/T07）。

纯 Python 字典递归比较（不引入 deepdiff）。对四类配置变更分别生成
:class:`ChangeImpact`：观察池 / 筛选规则 / 信号规则 / 竞技场。
"""
from __future__ import annotations

from typing import Any

from src.config_manager.schema import AppConfig, ChangeImpact


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------
def _diff_sets(old: set[str], new: set[str]) -> tuple[list[str], list[str]]:
    """返回 (added_sorted, removed_sorted)。"""
    return sorted(new - old), sorted(old - new)


def _item_map(items: list[Any], key: str = "name") -> dict[str, Any]:
    """把对象列表按某字段建立 name -> dump 字典 映射。"""
    return {getattr(item, key): item.model_dump() for item in items}


def _diff_named_rules(
    old_rules: list[Any], new_rules: list[Any]
) -> tuple[list[str], list[str], list[str]]:
    """比较命名规则列表，返回 (added, removed, modified) 名称。"""
    old_map = _item_map(old_rules)
    new_map = _item_map(new_rules)
    added = sorted(set(new_map) - set(old_map))
    removed = sorted(set(old_map) - set(new_map))
    modified = sorted(
        name
        for name in (set(old_map) & set(new_map))
        if old_map[name] != new_map[name]
    )
    return added, removed, modified


# ---------------------------------------------------------------------------
# 各类影响分析
# ---------------------------------------------------------------------------
def _pool_impact(old: AppConfig, new: AppConfig) -> ChangeImpact | None:
    old_set = set(old.observation_pool)
    new_set = set(new.observation_pool)
    added, removed = _diff_sets(old_set, new_set)
    if not added and not removed:
        return None
    affected = sorted(new_set | old_set)
    parts = []
    if added:
        parts.append(f"新增 {len(added)} 只（{', '.join(added)}）")
    if removed:
        parts.append(f"移除 {len(removed)} 只（{', '.join(removed)}）")
    return ChangeImpact(
        change_type="pool",
        added=added,
        removed=removed,
        affected_funds=affected,
        requires_backtest_rerun=False,
        summary="观察池变更：" + "，".join(parts),
    )


def _screener_impact(old: AppConfig, new: AppConfig) -> ChangeImpact | None:
    added, removed, modified = _diff_named_rules(
        old.screener_rules, new.screener_rules
    )
    if not added and not removed and not modified:
        return None
    affected = sorted(set(new.observation_pool) | set(old.observation_pool))
    parts = []
    if added:
        parts.append(f"新增 {len(added)} 条（{', '.join(added)}）")
    if removed:
        parts.append(f"移除 {len(removed)} 条（{', '.join(removed)}）")
    if modified:
        parts.append(f"修改 {len(modified)} 条（{', '.join(modified)}）")
    return ChangeImpact(
        change_type="screener",
        added=added,
        removed=removed,
        affected_funds=affected,
        requires_backtest_rerun=False,
        summary=(
            "筛选规则变更：" + "，".join(parts) +
            f"；潜在影响 {len(affected)} 只观察池基金"
            if affected
            else "筛选规则变更：" + "，".join(parts)
        ),
    )


def _signal_impact(old: AppConfig, new: AppConfig) -> ChangeImpact | None:
    added, removed, modified = _diff_named_rules(
        old.signal_rules, new.signal_rules
    )
    if not added and not removed and not modified:
        return None
    affected = sorted(set(new.observation_pool) | set(old.observation_pool))
    parts = []
    if added:
        parts.append(f"新增 {len(added)} 条（{', '.join(added)}）")
    if removed:
        parts.append(f"移除 {len(removed)} 条（{', '.join(removed)}）")
    if modified:
        parts.append(f"修改 {len(modified)} 条（{', '.join(modified)}）")
    return ChangeImpact(
        change_type="signal",
        added=added,
        removed=removed,
        affected_funds=affected,
        requires_backtest_rerun=False,
        summary=(
            "信号规则变更：" + "，".join(parts) +
            f"；影响 {len(affected)} 只观察池基金信号"
            if affected
            else "信号规则变更：" + "，".join(parts)
        ),
    )


def _arena_impact(old: AppConfig, new: AppConfig) -> ChangeImpact | None:
    old_dump = old.arena.model_dump()
    new_dump = new.arena.model_dump()
    changed_fields: list[str] = []
    detail_parts: list[str] = []
    for key in new_dump:
        if old_dump.get(key) != new_dump[key]:
            changed_fields.append(key)
            detail_parts.append(f"{key}: {old_dump.get(key)}→{new_dump[key]}")
    if not changed_fields:
        return None
    return ChangeImpact(
        change_type="arena",
        added=changed_fields,
        removed=[],
        affected_funds=[],
        requires_backtest_rerun=True,
        summary="竞技场配置变更：" + "，".join(detail_parts) + "，需要重跑回测",
    )


# ---------------------------------------------------------------------------
# 对外入口
# ---------------------------------------------------------------------------
def analyze_impact(old: AppConfig, new: AppConfig) -> list[ChangeImpact]:
    """比较新旧配置，返回所有受影响类别的 :class:`ChangeImpact` 列表。

    按观察池 → 筛选规则 → 信号规则 → 竞技场顺序检测，无变更的类别不返回。
    """
    impacts: list[ChangeImpact] = []
    for analyzer in (_pool_impact, _screener_impact, _signal_impact, _arena_impact):
        impact = analyzer(old, new)
        if impact is not None:
            impacts.append(impact)
    return impacts
