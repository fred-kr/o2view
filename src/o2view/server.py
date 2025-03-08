import io
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import dash_mantine_components as dmc
import polars as pl
import setproctitle
from dash import (
    Dash,
    Input,
    Output,
    Patch,
    State,
    _dash_renderer,
    callback,
    dash_table,
    dcc,
)
from dash.dash_table.Format import Format, Scheme
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from o2view.datamodel import LinearFit, PlotlyTemplate, parse_contents
from o2view.domino import terminate_when_parent_process_dies
from o2view.visualization import make_fit_trace, plot_dataset

if TYPE_CHECKING:
    from multiprocessing.synchronize import Condition

upload_style = {
    "width": "350px",
    "height": "60px",
    "lineHeight": "60px",
    "borderWidth": "1px",
    "borderStyle": "dashed",
    "borderRadius": "5px",
    "textAlign": "center",
}


result_table_columns = [
    {"id": "source_file", "name": "source_file"},
    # {"id": "fit_id", "name": "fit_id"},
    {"id": "start_index", "name": "start_index"},
    {"id": "end_index", "name": "end_index"},
    {"id": "slope", "name": "slope", "type": "numeric", "format": Format(precision=4, scheme=Scheme.fixed)},
    {"id": "rsquared", "name": "rsquared", "type": "numeric", "format": Format(precision=3, scheme=Scheme.fixed)},
    {"id": "y2_mean", "name": "y2_mean", "type": "numeric", "format": Format(precision=1, scheme=Scheme.fixed)},
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


def start_dash(host: str, port: str, server_is_started: "Condition") -> None:
    setproctitle.setproctitle("o2view-dash")

    terminate_when_parent_process_dies()
    _dash_renderer._set_react_version("18.2.0")

    app = Dash(__name__, external_stylesheets=dmc.styles.ALL)  # type: ignore

    app.layout = dmc.MantineProvider(
        dmc.Container(
            fluid=True,
            mt=20,
            mb=20,
            children=[
                dmc.Drawer(
                    id="drawer-settings",
                    title="Settings",
                    opened=False,
                    position="right",
                    children=[
                        dmc.Fieldset(
                            legend="File Upload",
                            children=[
                                dmc.NumberInput(
                                    id="input-skip-rows",
                                    label="Skip rows",
                                    value=57,
                                    min=0,
                                ),
                                dmc.Select(
                                    id="dropdown-separator",
                                    label="Column Separator",
                                    data=[
                                        {"label": "Detect Automatically", "value": "auto"},
                                        {"label": "Comma (,)", "value": ","},
                                        {"label": "Semicolon (;)", "value": ";"},
                                        {"label": "Tab (\\t)", "value": "\t"},
                                        {"label": "Pipe (|)", "value": "|"},
                                    ],
                                    value="auto",
                                    w="100%",
                                ),
                            ],
                        ),
                        dmc.Fieldset(
                            legend="Plot",
                            children=[
                                dmc.Select(
                                    id="dropdown-plot-template",
                                    label="Theme",
                                    data=PlotlyTemplate.all_values(),
                                    value=PlotlyTemplate.SIMPLE_WHITE,
                                ),
                                dmc.Select(
                                    id="dropdown-y-rangemode",
                                    label="Y-axis Behavior",
                                    data=[
                                        {"label": "Default", "value": "normal"},
                                        {"label": "Extend to zero", "value": "tozero"},
                                        {"label": "Non-negative", "value": "nonnegative"},
                                    ],
                                    value="normal",
                                    w="100%",
                                ),
                            ],
                        ),
                    ],
                ),
                dmc.Group(
                    wrap="nowrap",
                    align="stretch",
                    children=[
                        dmc.Stack(
                            gap=5,
                            children=[
                                dcc.Upload(
                                    id="upload-data",
                                    children=dmc.Box(["Drag and Drop or ", dmc.Anchor("Select File", href="#")]),
                                    multiple=False,
                                    style=upload_style,
                                ),
                                dmc.Text("Current: -", id="label-current-file"),
                            ],
                        ),
                        dmc.Group(
                            wrap="nowrap",
                            align="baseline",
                            w="100%",
                            children=[
                                dmc.Select(
                                    id="dropdown-x-data",
                                    label="X-axis",
                                    placeholder="Select one",
                                    withAsterisk=True,
                                    inputWrapperOrder=["input", "label"],
                                ),
                                dmc.Select(
                                    id="dropdown-y-data",
                                    label="Y-axis",
                                    placeholder="Select one",
                                    withAsterisk=True,
                                    inputWrapperOrder=["input", "label"],
                                ),
                                dmc.Select(
                                    id="dropdown-y2-data",
                                    label="Secondary Y-axis",
                                    placeholder="Select one (optional)",
                                    clearable=True,
                                    allowDeselect=True,
                                    inputWrapperOrder=["input", "label"],
                                ),
                                dmc.Group(
                                    wrap="nowrap",
                                    children=[
                                        dmc.Button("Plot", id="btn-make-plot", variant="light"),
                                        dmc.Button("Add fit", id="btn-add-fit", variant="light"),
                                    ],
                                ),
                                dmc.Group(
                                    wrap="nowrap",
                                    justify="flex-end",
                                    flex=1,
                                    children=[
                                        dmc.Button(
                                            "Export Results",
                                            id="btn-export-results",
                                            variant="light",
                                            leftSection=DashIconify(icon="clarity:export-line"),
                                        ),
                                        dmc.Button(
                                            "Clear Dataset",
                                            id="btn-clear-dataset",
                                            variant="light",
                                            leftSection=DashIconify(icon="clarity:remove-line"),
                                        ),
                                        dmc.ActionIcon(
                                            id="btn-show-settings",
                                            children=DashIconify(icon="clarity:settings-line", width=20),
                                            size="input-sm",
                                            variant="light",
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
                dmc.Box(
                    dcc.Graph(
                        id="graph",
                        config={
                            "editSelection": False,
                            "displaylogo": False,
                            "scrollZoom": True,
                            "doubleClick": "reset+autosize",
                        },
                    )
                ),
                dmc.Box(
                    dmc.Tabs(
                        [
                            dmc.TabsList(
                                [
                                    dmc.TabsTab("Results", value="results"),
                                    dmc.TabsTab("Current Dataset", value="dataset"),
                                ]
                            ),
                            dmc.TabsPanel(
                                dmc.Box(
                                    [
                                        dash_table.DataTable(
                                            id="table-results",
                                            columns=result_table_columns,  # type: ignore
                                            sort_action="native",
                                            style_header={
                                                "backgroundColor": "rgb(230, 230, 230)",
                                                "fontWeight": "bold",
                                                "textAlign": "left",
                                            },
                                            style_cell={"textAlign": "left"},
                                            style_table={"overflowX": "auto"},
                                            row_deletable=True,
                                            data=[],
                                        ),
                                        dcc.Download(id="download-results"),
                                    ]
                                ),
                                value="results",
                            ),
                            dmc.TabsPanel(
                                dmc.Box(
                                    [
                                        dash_table.DataTable(
                                            id="table-dataset",
                                            style_header={
                                                "backgroundColor": "rgb(230, 230, 230)",
                                                "fontWeight": "bold",
                                                "textAlign": "left",
                                            },
                                            style_cell={"textAlign": "left"},
                                            style_table={"overflowX": "scroll"},
                                        ),
                                    ]
                                ),
                                value="dataset",
                            ),
                        ],
                        value="results",
                    )
                ),
                dcc.Store(id="store-dataset"),
                dcc.Store(id="store-results"),
                dcc.Store(id="store-graph"),
            ],
        )
    )

    @callback(
        Output("drawer-settings", "opened"),
        Input("btn-show-settings", "n_clicks"),
        State("drawer-settings", "opened"),
        prevent_initial_call=True,
    )
    def toggle_settings(n_clicks: int, opened: bool) -> bool:
        return not opened

    @callback(
        Output("store-dataset", "data"),
        Output("label-current-file", "children"),
        Input("upload-data", "contents"),
        State("upload-data", "filename"),
        State("input-skip-rows", "value"),
        State("dropdown-separator", "value"),
        prevent_initial_call=True,
    )
    def read_presens(contents: str, filename: str, skip_rows: int = 57, separator: str = ";") -> tuple[str, str]:
        if not contents or not filename:
            return "", "Current: -"

        parsed = parse_contents(contents, filename, skip_rows, separator)
        return parsed.write_json(), f"Current: {filename}"

    @callback(
        Output("table-dataset", "columns"),
        Output("table-dataset", "data"),
        Output("dropdown-x-data", "data"),
        Output("dropdown-y-data", "data"),
        Output("dropdown-y2-data", "data"),
        Output("dropdown-x-data", "value"),
        Output("dropdown-y-data", "value"),
        Output("dropdown-y2-data", "value"),
        Input("store-dataset", "data"),
        prevent_initial_call=True,
    )
    def populate_controls(data: str):
        if not data:
            return [], [], [], [], [], "", "", ""

        parsed = pl.read_json(io.StringIO(data))
        cols = parsed.columns
        return (
            [{"name": col_name, "id": col_name} for col_name in cols],
            parsed.to_dicts(),
            cols,
            cols,
            cols,
            cols[1],
            cols[2],
            cols[-1],
        )

    @callback(
        Output("graph", "figure", allow_duplicate=True),
        Input("store-graph", "data"),
        prevent_initial_call=True,
    )
    def update_graph(data: dict[str, Any]):
        return data or {}

    @callback(
        Output("store-graph", "data", allow_duplicate=True),
        Input("btn-make-plot", "n_clicks"),
        State("store-dataset", "data"),
        State("dropdown-x-data", "value"),
        State("dropdown-y-data", "value"),
        State("dropdown-y2-data", "value"),
        State("dropdown-plot-template", "value"),
        State("dropdown-y-rangemode", "value"),
        prevent_initial_call=True,
    )
    def make_plot(
        n_clicks: int,
        data: str,
        x_name: str,
        y_name: str,
        y2_name: str,
        template: str,
        y_rangemode: Literal["normal", "tozero", "nonnegative"],
    ) -> dict[str, Any]:
        if not data:
            raise PreventUpdate

        parsed = pl.read_json(io.StringIO(data))
        fig = plot_dataset(parsed, x_name, y_name, y2_name, template, y_rangemode)
        return fig.to_dict()

    @callback(
        Output("store-graph", "data", allow_duplicate=True),
        Output("table-results", "data"),
        Input("btn-add-fit", "n_clicks"),
        State("graph", "selectedData"),
        State("dropdown-x-data", "value"),
        State("dropdown-y-data", "value"),
        State("dropdown-y2-data", "value"),
        State("upload-data", "filename"),
        State("table-results", "data"),
        prevent_initial_call=True,
    )
    def add_fit(
        n_clicks: int,
        selected_data: dict[str, Any] | None,
        x_name: str,
        y_name: str,
        y2_name: str,
        filename: str,
        results: list[dict[str, Any]],
    ):
        if not selected_data:
            raise PreventUpdate

        df = pl.from_dicts(
            selected_data["points"],
            schema={
                "curveNumber": pl.Int32,
                "pointNumber": pl.Int32,
                "pointIndex": pl.Int32,
                "x": pl.Float64,
                "y": pl.Float64,
            },
        )

        if y2_name:
            fit_df = df.select(
                pl.col("pointIndex").filter(pl.col("curveNumber") == 0).alias("index"),
                pl.col("x").filter(pl.col("curveNumber") == 0).alias(x_name),
                pl.col("y").filter(pl.col("curveNumber") == 0).alias(y_name),
                pl.col("y").filter(pl.col("curveNumber") == 1).alias(y2_name),
            )
        else:
            fit_df = df.select(
                pl.col("pointIndex").filter(pl.col("curveNumber") == 0).alias("index"),
                pl.col("x").filter(pl.col("curveNumber") == 0).alias(x_name),
                pl.col("y").filter(pl.col("curveNumber") == 0).alias(y_name),
            )

        fit_df = fit_df.sort("index", maintain_order=True)
        idx = fit_df.get_column("index")

        start, stop = idx.item(0), idx.item(-1)

        fit = LinearFit(start_index=start, end_index=stop, df=fit_df, x_name=x_name, y_name=y_name, y2_name=y2_name)

        result_df = pl.from_dicts(results, schema=result_df_schema)
        result_df = result_df.extend(fit.make_result(filename))

        fit_trace = make_fit_trace(
            x=fit.x_data,
            y_fitted=fit.y_fitted,
            name=Path(filename).stem,
            slope=fit.result.slope,
            rsquared=fit.result.rvalue,
            y2_mean=fit.y2_mean,
        )
        patched_fig = Patch()
        # Clear the selection region
        patched_fig["layout"]["selections"].clear()
        # patched_fig["layout"]["selectionrevision"] += 1

        patched_fig["data"].append(fit_trace)
        return patched_fig, result_df.to_dicts()

    @callback(
        Output("download-results", "data"),
        Input("btn-export-results", "n_clicks"),
        State("table-results", "data"),
        prevent_initial_call=True,
    )
    def export_results(n_clicks: int, data: list[dict[str, Any]]) -> dict[str, Any]:
        df = pl.from_dicts(data)
        return dcc.send_data_frame(df.write_excel, "results.xlsx")  # type: ignore

    with server_is_started:
        server_is_started.notify()

    app.run(debug=False, host=host, port=port)
