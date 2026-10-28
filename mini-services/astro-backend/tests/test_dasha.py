from datetime import datetime

from app.services.dasha import LORD_YEARS, YEAR_DAYS, VimshottariDasha
from app.services.jataka import JatakaEngine


def test_birth_mahadasha_starts_mid_way_not_with_own_lord():
    d = JatakaEngine().compute_chart()["dasha"]
    first = d.tree[0]
    assert first["lord"] == "Sun"
    # Moon at ~Leo 29.8 (Uttara Phalguni 1): 23% of Sun MD elapsed before birth,
    # so the native is born inside Rahu AD of Sun MD, as drikpanchang lists it.
    assert first["antardashas"][0]["lord"] == "Rahu"
    assert first["antardashas"][0]["start"] == first["start"]
    assert first["antardashas"][-1]["lord"] == "Venus"
    assert abs((first["antardashas"][-1]["end"] - first["end"]).total_seconds()) < 60


def test_full_mahadashas_sum_and_start_with_own_lord():
    v = VimshottariDasha(133.0, datetime(1990, 1, 1))
    for md in v.tree[1:]:
        assert md["antardashas"][0]["lord"] == md["lord"]
        total = sum(a["years"] for a in md["antardashas"])
        assert abs(total - LORD_YEARS[md["lord"]]) < 0.01
        assert abs((md["antardashas"][-1]["end"] - md["end"]).days) <= 1


def test_current_period_for_default_native():
    d = JatakaEngine().compute_chart()["dasha"]
    cur = d.current(datetime(2026, 10, 27))
    assert (cur["mahadasha"]["lord"], cur["antardasha"]["lord"]) == ("Rahu", "Ketu")


def test_year_length_is_drikpanchang_standard():
    assert YEAR_DAYS == 365.2425
