import bot
from config import PROJECT_ROOT


def test_t_st_01_selftest_passes(capsys):
    assert bot.run_selftest() == 0
    assert "selftest: OK" in capsys.readouterr().out


def test_t_st_02_selftest_leaves_project_root_untouched():
    before = sorted(p.name for p in PROJECT_ROOT.iterdir())
    assert bot.run_selftest() == 0
    after = sorted(p.name for p in PROJECT_ROOT.iterdir())
    assert before == after
