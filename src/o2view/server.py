from typing import TYPE_CHECKING, Any

import dash_mantine_components as dmc
import polars as pl
import setproctitle
from dash import (
    Dash,
    Input,
    Output,
    _dash_renderer,
    callback,
    ctx,
    dcc,
    no_update,
)
from dash.dash_table.Format import Format, Scheme
from dash_iconify import DashIconify

from o2view.datamodel import GlobalState
from o2view.domino import terminate_when_parent_process_dies

if TYPE_CHECKING:
    from multiprocessing.synchronize import Condition


upload_style = {
    "width": "300px",
    "height": "60px",
    "lineHeight": "60px",
    "borderWidth": "1px",
    "borderStyle": "dashed",
    "borderRadius": "5px",
    "textAlign": "center",
}


result_table_columns: list = [
    {
        "id": "slope",
        "name": "slope",
        "type": "numeric",
        "format": Format(precision=4, scheme=Scheme.fixed),
    },
    {
        "id": "rsquared",
        "name": "rsquared",
        "type": "numeric",
        "format": Format(precision=3, scheme=Scheme.fixed),
    },
    {
        "id": "y2_mean",
        "name": "y2_mean",
        "type": "numeric",
        "format": Format(precision=1, scheme=Scheme.fixed),
    },
    {"id": "start_index", "name": "start_index", "type": "numeric", "format": Format(scheme=Scheme.decimal_integer)},
    {"id": "end_index", "name": "end_index", "type": "numeric", "format": Format(scheme=Scheme.decimal_integer)},
    {"id": "source_file", "name": "source_file", "type": "text"},
    {"id": "x_name", "name": "x_name"},
    {"id": "x_first", "name": "x_first"},
    {"id": "x_last", "name": "x_last"},
    {"id": "y_name", "name": "y_name"},
    {"id": "y_first", "name": "y_first"},
    {"id": "y_last", "name": "y_last"},
    {"id": "y2_name", "name": "y2_name"},
    {"id": "y2_first", "name": "y2_first"},
    {"id": "y2_last", "name": "y2_last"},
]

result_df_schema = {
    "source_file": pl.Utf8,
    "start_index": pl.Int64,
    "end_index": pl.Int64,
    "slope": pl.Float64,
    "rsquared": pl.Float64,
    "y2_mean": pl.Float64,
    "x_name": pl.Utf8,
    "x_first": pl.Float64,
    "x_last": pl.Float64,
    "y_name": pl.Utf8,
    "y_first": pl.Float64,
    "y_last": pl.Float64,
    "y2_name": pl.Utf8,
    "y2_first": pl.Float64,
    "y2_last": pl.Float64,
}

dropdown_separator_data: list = [
    {"label": "Detect Automatically", "value": "auto"},
    {"label": "Comma (,)", "value": ","},
    {"label": "Semicolon (;)", "value": ";"},
    {"label": "Tab (\\t)", "value": "\t"},
    {"label": "Pipe (|)", "value": "|"},
]

dropdown_y_rangemode_data: list = [
    {"label": "Normal", "value": "normal"},
    {"label": "Extend to zero", "value": "tozero"},
    {"label": "Non-negative", "value": "nonnegative"},
]


def start_dash(host: str, port: str, server_is_started: "Condition") -> None:
    import sys

    if not sys.warnoptions:
        import warnings

        warnings.simplefilter("ignore", category=DeprecationWarning)
    setproctitle.setproctitle("o2view-dash")

    terminate_when_parent_process_dies()
    _dash_renderer._set_react_version("18.2.0")
    dmc.add_figure_templates(default="mantine_light")
    app = Dash(__name__, external_stylesheets=dmc.styles.ALL)

    app.layout = dmc.MantineProvider(
        children=[
            dmc.Container(
                fluid=True,
                mt=20,
                mb=20,
                children=[
                    dmc.Group(
                        wrap="nowrap",
                        children=[
                            dmc.Select(
                                id="source-file",
                                label="Source File",
                                placeholder="Select one",
                                searchable=True,
                                checkIconPosition="right",
                                maxDropdownHeight=300,
                                data=GlobalState.instance().unique_files(),
                                inputWrapperOrder=["input", "label"],
                                style={"width": "400px"},
                            ),
                            dmc.Button(
                                "Good Fit",
                                id="mark-good-fit",
                                color="green",
                                variant="outline",
                                size="md",
                                leftSection=DashIconify(icon="fluent:checkmark-12-filled", width=20),
                            ),
                            dmc.Button(
                                "Bad Fit",
                                id="mark-bad-fit",
                                color="red",
                                variant="outline",
                                size="md",
                                leftSection=DashIconify(icon="fluent:dismiss-circle-12-filled", width=20),
                            ),
                            dmc.Text(
                                "This fit is not yet marked",  # good/bad/not yet marked
                                id="fit-status",
                                size="md",
                                style={"align": "right"},
                            ),
                        ],
                    ),
                    dmc.Grid(
                        id="group-tables-graph",
                        children=[
                            dmc.GridCol(
                                span="auto",
                                children=dmc.AspectRatio(
                                    ratio=16 / 9,
                                    flex=1,
                                    children=[
                                        dcc.Loading(
                                            [
                                                dcc.Graph(
                                                    id="graph",
                                                    responsive=True,
                                                    config={
                                                        "displayModeBar": True,
                                                        "editSelection": False,
                                                        "displaylogo": False,
                                                        "scrollZoom": True,
                                                        "modeBarButtonsToAdd": [
                                                            "toggleHover",
                                                        ],
                                                        "modeBarButtonsToRemove": [
                                                            "sendDataToCloud",
                                                            "zoom2d",
                                                            "pan2d",
                                                            "lasso2d",
                                                            "zoomIn2d",
                                                            "zoomOut2d",
                                                        ],
                                                        "doubleClick": "reset+autosize",
                                                    },
                                                    style={"height": "80vh"},
                                                )
                                            ],
                                            overlay_style={
                                                "visibility": "visible",
                                                "opacity": 0.5,
                                                "backgroundColor": "white",
                                            },
                                        ),
                                    ],
                                ),
                            ),
                        ],
                    ),
                    dcc.Store(id="store-graph"),
                ],
            )
        ],
    )

    @callback(
        Output("graph", "figure"),
        Input("store-graph", "data"),
        prevent_initial_call=True,
    )
    def update_graph(data: dict[str, Any]):
        return data or no_update

    @callback(
        Output("store-graph", "data"),
        Output("fit-status", "children", allow_duplicate=True),
        Output("fit-status", "color", allow_duplicate=True),
        Output("fit-status", "variant", allow_duplicate=True),
        Input("source-file", "value"),
        prevent_initial_call=True,
    )
    def plot_file(source_file_cleaned: str):
        fig = GlobalState.instance().plot_data_for_file(source_file_cleaned)
        status = GlobalState.instance().get_marked_status(source_file_cleaned)
        if status == "ok":
            return fig, "This fit is marked as good", "green", "filled"
        elif status == "bad":
            return fig, "This fit is marked as bad", "red", "filled"
        else:
            return fig, "This fit is not yet marked", "gray", "light"

    @callback(
        Output("fit-status", "children", allow_duplicate=True),
        Output("fit-status", "color", allow_duplicate=True),
        Output("fit-status", "variant", allow_duplicate=True),
        Input("source-file", "value"),
        Input("mark-good-fit", "n_clicks"),
        Input("mark-bad-fit", "n_clicks"),
        prevent_initial_call=True,
    )
    def mark_file(
        source_file_cleaned: str,
        mark_good_file: int | None,
        mark_bad_file: int | None,
    ):
        if not ctx.triggered_id:
            return no_update, no_update, no_update
        elif ctx.triggered_id == "mark-good-fit":
            GlobalState.instance().mark_file(source_file_cleaned, "ok")
            return "This fit is marked as good", "green", "filled"
        elif ctx.triggered_id == "mark-bad-fit":
            GlobalState.instance().mark_file(source_file_cleaned, "bad")
            return "This fit is marked as bad", "red", "filled"
        else:
            return "This fit is not yet marked", "gray", "light"

    with server_is_started:
        server_is_started.notify()

    app.run(debug=True, use_reloader=False, host=host, port=port)
