from types import SimpleNamespace

import numpy as np
import pytest


@pytest.fixture
def mini_page(qtbot, mocker):
    from badger.gui.mini.components import var_table
    from badger.gui.mini.pages import routine_page

    names = [f"x{i}" for i in range(341)]
    values = dict.fromkeys(names, 0.5)
    values.update(x0=0.0, x1=-0.5, x2=0.99)
    env = SimpleNamespace(
        name="large",
        get_variables=mocker.Mock(
            side_effect=lambda requested: {name: values[name] for name in requested}
        ),
    )
    configs = {
        "params": {},
        "variables": [{name: [-1.0, 1.0]} for name in names],
        "observations": [],
    }
    mocker.patch.object(routine_page, "list_env", return_value=["large"])
    mocker.patch.object(routine_page, "list_generators", return_value=["random"])
    mocker.patch.object(routine_page, "get_env", return_value=(env, configs))
    mocker.patch.object(var_table, "instantiate_env", return_value=env)
    mocker.patch.object(routine_page.BadgerDocsWindow, "update_docs")

    page = routine_page.BadgerRoutinePage()
    qtbot.addWidget(page)
    mocker.patch.object(page, "create_env", return_value=env)
    page.select_generator(0)
    page.env_box.env_cb.blockSignals(True)
    page.env_box.env_cb.setCurrentIndex(0)
    page.env_box.env_cb.blockSignals(False)
    return page, env, values


@pytest.mark.parametrize("option", [0, 1, 2])
def test_select_env_reads_all_variables_once(mini_page, option):
    page, env, values = mini_page
    page.limit_option["limit_option_idx"] = option

    page.select_env(0)

    env.get_variables.assert_called_once_with(list(values))
    table = page.env_box.var_table
    assert table.current_values == values
    assert table.saved_values == values
    assert table.rowCount() == 342
    for name, value in values.items():
        if option == 0:
            delta = abs(value) * page.limit_option["ratio_curr"] / 2
        elif option == 1:
            delta = page.limit_option["ratio_full"]
        else:
            delta = page.limit_option["delta"]
        bounds = [value - delta, value + delta]
        expected = np.clip(bounds, -1.0, 1.0).tolist()
        assert table.bounds[name] == pytest.approx(expected)
        assert table.clipped[name] == (bounds != expected)


def test_select_env_without_relative_ranges_still_reads_once(mini_page):
    page, env, values = mini_page
    page.env_box.relative_to_curr.setChecked(False)

    page.select_env(0)

    env.get_variables.assert_called_once_with(list(values))
    assert page.env_box.var_table.bounds["x1"] == (-1.0, 1.0)


def test_select_env_does_not_reuse_previous_load_values(mini_page):
    page, env, values = mini_page
    page.select_env(0)
    env.get_variables.reset_mock()
    values.update(dict.fromkeys(values, 0.25))

    page.select_env(0)

    env.get_variables.assert_called_once_with(list(values))
    table = page.env_box.var_table
    assert table.current_values == values
    assert table.saved_values == values
    assert table.bounds["x1"] == pytest.approx([0.2375, 0.2625])


@pytest.mark.parametrize("set_all", [True, False])
def test_explicit_range_update_reads_fresh_values(mini_page, set_all):
    page, env, values = mini_page
    page.select_env(0)
    env.get_variables.reset_mock()
    values.update(dict.fromkeys(values, -0.25))
    table = page.env_box.var_table
    table.variables = table.all_variables[:2]

    page.set_vrange(set_all=set_all)

    expected_names = list(values) if set_all else ["x0", "x1"]
    env.get_variables.assert_called_once_with(expected_names)
    assert table.bounds["x1"] == pytest.approx([-0.2625, -0.2375])
    if not set_all:
        assert table.bounds["x3"] == pytest.approx([0.475, 0.525])


def test_redraw_does_not_read_but_refresh_does(mini_page):
    page, env, values = mini_page
    page.select_env(0)
    env.get_variables.reset_mock()
    table = page.env_box.var_table

    table.update_variables(table.variables, filtered=1)
    table.set_scan_range_options()

    env.get_variables.assert_not_called()
    values["x1"] = 0.25
    table.refresh_current_values()

    env.get_variables.assert_called_once_with(list(values))
    assert table.current_values["x1"] == 0.25
    assert table.saved_values["x1"] == -0.5


def test_explicit_range_update_reports_read_failure(mini_page):
    from badger.errors import BadgerEnvVarError

    page, env, _ = mini_page
    page.select_env(0)
    env.get_variables.side_effect = TimeoutError("PV disconnected")

    with pytest.raises(BadgerEnvVarError, match="PV disconnected"):
        page.set_vrange()
