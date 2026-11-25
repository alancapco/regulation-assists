from backend.app.mapping import apply_date_filter, map_calendar_event


class _Item:
    """最小载体，验证 apply_date_filter 对 object（非 dict）的 getattr 路径。"""
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_apply_date_filter_empty_params_keeps_none_dates():
    # 9/30 条法规仅年份 → legislation_date 归一为 None；默认视图须返回全量，不丢 None 行
    items = [
        _Item(legislation_date=None),
        _Item(legislation_date="2024-01-01"),
        {"legislation_date": None},
        {"legislation_date": "2023-06-15"},
    ]
    out = apply_date_filter(items, "", "", key="legislation_date")
    assert len(out) == 4


def test_apply_date_filter_range_excludes_none_dates():
    # 显式区间下，None 日期仍被排除（不参与任何区间）
    items = [
        _Item(legislation_date=None),
        _Item(legislation_date="2024-01-01"),
        _Item(legislation_date="2099-01-01"),
    ]
    out = apply_date_filter(items, "2020-01-01", "2025-12-31", key="legislation_date")
    assert len(out) == 1
    assert out[0].legislation_date == "2024-01-01"


def test_map_calendar_event_drops_unparseable_date():
    # 无法归一的日期 → None（F-004 跳过）
    bad = {"id": "x", "date_raw": "Approx. 2024", "title": "t",
           "instrument_id": "i", "regulation_name": "r",
           "jurisdiction": "j", "source_url": None}
    assert map_calendar_event(bad) is None
