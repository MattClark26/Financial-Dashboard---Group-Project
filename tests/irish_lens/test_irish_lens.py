import pandas as pd
import pytest

from panels import irish_lens


@pytest.mark.parametrize(
    ("probability", "expected_status"),
    [(33.9, "CALM"), (34.0, "WATCH"), (67.0, "ALERT")],
)
def test_score_status_thresholds(probability: float, expected_status: str) -> None:
    result = irish_lens.score_irish_lens(
        sahm_indicator=None,
        export_share=None,
        recession_probability=probability,
        gdp_index=None,
        mdd_index=None,
    )
    assert result["status"] == expected_status


def test_export_share_obeys_as_of_date_and_rolling_average(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dates = pd.date_range("2025-01-31", periods=14, freq="ME")
    frame = pd.DataFrame(
        {
            "Date": dates,
            "US Exports": [25.0] * len(dates),
            "Total Exports": [100.0] * len(dates),
        }
    )
    monkeypatch.setattr(
        irish_lens,
        "_read_cached_frame",
        lambda _filename: frame.copy(),
    )

    result = irish_lens._load_export_exposure(pd.Timestamp("2025-12-31"))

    assert len(result) == 12
    assert result["Date"].max() == pd.Timestamp("2025-12-31")
    assert result.iloc[-1]["US Share (%)"] == pytest.approx(25.0)
    assert result.iloc[-1]["12-month average (%)"] == pytest.approx(25.0)


def test_mdd_recession_starts_require_two_consecutive_declines() -> None:
    mdd = pd.Series(
        [100, 98, 95, 92, 94, 92, 89],
        index=pd.to_datetime(
            [
                "2020-03-31",
                "2020-06-30",
                "2020-09-30",
                "2020-12-31",
                "2021-03-31",
                "2021-06-30",
                "2021-09-30",
            ]
        ),
        dtype="float64",
    )

    starts = irish_lens._mdd_recession_starts(mdd)

    assert list(starts) == list(pd.to_datetime(["2020-09-30", "2021-09-30"]))


def test_track_record_counts_caught_event_and_false_alarm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quarters = pd.period_range("2019Q1", "2023Q4", freq="Q")
    mdd_frame = pd.DataFrame(
        {
            "Time": quarters.astype(str),
            "VALUE": [
                100,
                101,
                102,
                103,
                101,
                99,
                100,
                101,
                102,
                103,
                104,
                105,
                106,
                107,
                108,
                109,
                110,
                111,
                112,
                113,
            ],
        }
    )
    export_dates = pd.date_range("2018-01-31", "2023-12-31", freq="ME")
    exports = pd.DataFrame(
        {
            "Date": export_dates,
            "12-month average (%)": [25.0] * len(export_dates),
        }
    )
    warning_dates = {
        pd.Timestamp("2019-10-31"),
        pd.Timestamp("2021-12-31"),
    }

    monkeypatch.setattr(
        irish_lens,
        "_read_cached_frame",
        lambda _filename: mdd_frame.copy(),
    )
    monkeypatch.setattr(
        irish_lens,
        "_load_export_exposure",
        lambda as_of: exports.loc[exports["Date"] <= as_of].copy(),
    )
    monkeypatch.setattr(
        irish_lens,
        "load_irish_lens_signal",
        lambda as_of: {"score": 40.0 if as_of in warning_dates else 20.0},
    )

    result = irish_lens._compute_irish_track_record(pd.Timestamp("2023-12-31"))

    assert result == {
        "caught": 1,
        "false_alarms": 1,
        "avg_lead_months": 8.0,
    }
