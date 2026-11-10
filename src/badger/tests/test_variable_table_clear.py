import importlib

import pytest


@pytest.mark.parametrize(
    "module",
    ["badger.gui.components.var_table", "badger.gui.mini.components.var_table"],
)
@pytest.mark.parametrize("variables", [None, []])
def test_clear_variable_table(qtbot, module, variables):
    table_class = importlib.import_module(module).VariableTable
    table = table_class()
    qtbot.addWidget(table)
    table.update_variables([{"x0": (-1.0, 1.0)}])
    table.selected["x0"] = True
    table.addtl_vars = ["extra"]

    table.update_variables(variables)

    assert table.rowCount() == 0
    assert table.all_variables == []
    assert table.variables == []
    assert table.selected == {}
    assert table.bounds == {}
    assert table.addtl_vars == []
    if hasattr(table, "current_values"):
        assert table.current_values == {}
        assert table.saved_values == {}
        assert table.clipped == {}
