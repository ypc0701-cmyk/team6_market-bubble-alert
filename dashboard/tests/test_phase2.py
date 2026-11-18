from pathlib import Path

from streamlit.testing.v1 import AppTest

PAGE = Path(__file__).resolve().parents[1] / "pages" / "2_Phase_2_Risk.py"


def test_preview_handles_missing_scores_and_honest_model_card():
    app = AppTest.from_file(str(PAGE)).run(timeout=30)
    assert not app.exception
    assert "DUMMY DATA" in app.warning[0].value
    assert any("SPCX" in item.value for item in app.info)
    assert any("does not establish" in item.value for item in app.info)
    assert any("trained_at" in item.value for item in app.markdown)
    assert len(app.dataframe[0].value) == 10
    assert any(item.value == "2 · DIVERGENCE" for item in app.metric)
    assert "Comparison" in app.dataframe[0].value.columns


def test_first_week_change_is_unavailable_not_zero():
    app = AppTest.from_file(str(PAGE)).run(timeout=30)
    app.selectbox[0].select("2026-11-06").run()
    assert not app.exception
    assert app.dataframe[0].value["Weekly change"].str.contains("first scored week").all()
    assert any("No dial reading" in item.value for item in app.info)
    assert not any(item.label == "Official dial" for item in app.metric)
