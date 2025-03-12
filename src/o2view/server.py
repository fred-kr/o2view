import io
from typing import TYPE_CHECKING, Any, Literal

import dash_mantine_components as dmc
import polars as pl
import setproctitle
from dash import (
    ClientsideFunction,
    Dash,
    Input,
    Output,
    Patch,
    State,
    _dash_renderer,
    callback,
    clientside_callback,
    dash_table,
    dcc,
    no_update,
)
from dash.dash_table.Format import Format, Scheme
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from o2view.datamodel import FigureDict, LinearFit, PlotlyTemplate, parse_contents
from o2view.domino import terminate_when_parent_process_dies
from o2view.visualization import find_trace_index, make_fit_trace, plot_dataset

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


result_table_columns: list = [
    {"id": "source_file", "name": "source_file"},
    {"id": "start_index", "name": "start_index"},
    {"id": "end_index", "name": "end_index"},
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
    setproctitle.setproctitle("o2view-dash")

    terminate_when_parent_process_dies()
    _dash_renderer._set_react_version("18.2.0")
    dmc.add_figure_templates()
    app = Dash(__name__, external_stylesheets=dmc.styles.ALL)

    app.layout = dmc.MantineProvider(
        children=[
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
                                        data=dropdown_separator_data,
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
                                        value=PlotlyTemplate.YGRIDOFF,
                                    ),
                                    dmc.Select(
                                        id="dropdown-y-rangemode",
                                        label="Y-axis Behavior",
                                        data=dropdown_y_rangemode_data,
                                        value="normal",
                                        w="100%",
                                    ),
                                    dmc.Switch(
                                        id="switch-show-legend",
                                        label="Show Legend",
                                        checked=True,
                                        mt=10,
                                    ),
                                ],
                            ),
                        ],
                    ),
                    dmc.Group(
                        wrap="nowrap",
                        children=[
                            dmc.Stack(
                                gap=5,
                                children=[
                                    dcc.Upload(
                                        id="upload-data",
                                        children=dmc.Box(
                                            [
                                                "Drag and Drop or ",
                                                dmc.Anchor("Select File", href="#"),
                                            ]
                                        ),
                                        multiple=False,
                                        style=upload_style,
                                    ),
                                    dmc.Text("File: -", id="label-current-file"),
                                ],
                            ),
                            dmc.Group(
                                wrap="nowrap",
                                w="100%",
                                children=[
                                    dmc.Select(
                                        id="dropdown-x-data",
                                        label="X-axis",
                                        placeholder="Select one",
                                        required=True,
                                        inputWrapperOrder=["input", "label"],
                                    ),
                                    dmc.Select(
                                        id="dropdown-y-data",
                                        label="Y-axis",
                                        placeholder="Select one",
                                        required=True,
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
                                        flex=1,
                                        grow=True,
                                        children=[
                                            dmc.Tooltip(
                                                dmc.Button(
                                                    "Plot",
                                                    id="btn-make-plot",
                                                    color="indigo",
                                                    variant="filled",
                                                    n_clicks=0,
                                                    size="sm",
                                                ),
                                                label="Re-create plot (including fits) with the current setting values",
                                                multiline=True,
                                            ),
                                            dmc.Tooltip(
                                                dmc.Button(
                                                    "Fit",
                                                    id="btn-add-fit",
                                                    color="indigo",
                                                    variant="filled",
                                                    n_clicks=0,
                                                    size="sm",
                                                ),
                                                label="Fit a line to the selected data points",
                                                multiline=True,
                                            ),
                                        ],
                                    ),
                                    dmc.Group(
                                        wrap="nowrap",
                                        justify="flex-end",
                                        # flex=1,
                                        children=[
                                            dmc.Tooltip(
                                                dmc.Button(
                                                    "Export",
                                                    id="btn-export-results",
                                                    color="indigo",
                                                    variant="light",
                                                    leftSection=DashIconify(icon="clarity:export-line"),
                                                    n_clicks=0,
                                                ),
                                                label="Save contents of results table to Excel file",
                                            ),
                                            dmc.ActionIcon(
                                                id="btn-show-settings",
                                                children=DashIconify(
                                                    icon="clarity:settings-line",
                                                    width=20,
                                                ),
                                                size="input-sm",
                                                color="indigo",
                                                variant="light",
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    dmc.Box(
                        id="box-fig",
                        w="100%",
                        children=[
                            dcc.Loading(
                                [
                                    dcc.Graph(
                                        id="graph",
                                        config={
                                            "editSelection": False,
                                            "displaylogo": False,
                                            "scrollZoom": False,
                                            "doubleClick": "reset",
                                        },
                                        style={"height": "85vh"},
                                    )
                                ],
                                overlay_style={
                                    "visibility": "visible",
                                    "opacity": 0.5,
                                    "backgroundColor": "white",
                                },
                            ),
                            dmc.Affix(
                                dmc.Button(
                                    "Results & Dataset",
                                    id="btn-show-tables",
                                    color="indigo",
                                    variant="light",
                                    leftSection=DashIconify(icon="clarity:table-line", width=20),
                                ),
                                position={"bottom": 20, "left": 20},
                            ),
                        ],
                    ),
                    dmc.Drawer(
                        id="drawer-tables",
                        title="Results & Dataset",
                        opened=False,
                        position="bottom",
                        keepMounted=True,
                        withOverlay=False,
                        children=[
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
                                                    columns=result_table_columns,
                                                    data=[],
                                                    page_size=15,
                                                    style_header={
                                                        "backgroundColor": "rgb(230, 230, 230)",
                                                        "fontWeight": "bold",
                                                        "textAlign": "left",
                                                    },
                                                    style_cell={"textAlign": "left"},
                                                    style_table={"overflowX": "auto"},
                                                    row_deletable=True,
                                                    row_selectable="multi",
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
                                                    page_size=15,
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
                        ],
                    ),
                    dcc.Store(id="store-dataset"),
                    dcc.Store(id="store-results"),
                    dcc.Store(id="store-graph"),
                ],
            )
        ],
    )

    @callback(
        Output("drawer-tables", "opened"),
        Input("btn-show-tables", "n_clicks"),
        State("drawer-tables", "opened"),
        prevent_initial_call=True,
    )
    def toggle_tables(n_clicks: int, opened: bool) -> bool:
        return not opened

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
            return "", "File: -"

        parsed = parse_contents(contents, filename, skip_rows, separator)
        return parsed.write_json(), f"File: {filename}"

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
            raise PreventUpdate

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
        Output("graph", "figure"),
        Input("store-graph", "data"),
        prevent_initial_call=True,
    )
    def update_graph(data: dict[str, Any]):
        return data or no_update

    clientside_callback(
        ClientsideFunction(
            namespace="clientside",
            function_name="updateLoadingState",
        ),
        Output("btn-make-plot", "loading", allow_duplicate=True),
        Input("btn-make-plot", "n_clicks"),
        prevent_initial_call=True,
    )

    @callback(
        Output("store-graph", "data", allow_duplicate=True),
        Output("btn-make-plot", "loading"),
        Input("btn-make-plot", "n_clicks"),
        Input("table-dataset", "data"),
        State("dropdown-x-data", "value"),
        State("dropdown-y-data", "value"),
        State("dropdown-y2-data", "value"),
        State("dropdown-plot-template", "value"),
        State("dropdown-y-rangemode", "value"),
        State("switch-show-legend", "checked"),
        State("table-results", "data"),
        State("upload-data", "filename"),
        prevent_initial_call=True,
    )
    def make_plot(
        n_clicks: int,
        data: list[dict[str, Any]],
        x_name: str,
        y_name: str,
        y2_name: str,
        template: str,
        y_rangemode: Literal["normal", "tozero", "nonnegative"],
        show_legend: bool,
        results: list[dict[str, Any]],
        filename: str,
    ) -> tuple[dict[str, Any], bool]:
        if not data:
            raise PreventUpdate

        parsed = pl.from_dicts(data)
        fig = plot_dataset(parsed, x_name, y_name, y2_name, template, y_rangemode, show_legend)

        res_df = pl.from_dicts(results, schema=result_df_schema).filter(pl.col("source_file") == filename)
        if not res_df.is_empty():
            for row in res_df.iter_rows():
                start, stop = row[1], row[2]
                fit_df = parsed.slice(start, stop - start + 1)
                fit = LinearFit(start, stop, fit_df, x_name, y_name, y2_name)
                fit_trace = make_fit_trace(
                    x=fit.x_data,
                    y_fitted=fit.y_fitted,
                    name=f"{filename}_{start}",
                    slope=fit.result.slope,
                    rsquared=fit.rsquared,
                    start_index=start,
                    y2_mean=fit.y2_mean,
                )
                fig.add_trace(fit_trace)

        return fig.to_dict(), False

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
        if not n_clicks or not selected_data:
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

        fit = LinearFit(
            start_index=start,
            end_index=stop,
            df=fit_df,
            x_name=x_name,
            y_name=y_name,
            y2_name=y2_name,
        )

        result_df = pl.from_dicts(results, schema=result_df_schema)
        result_df = result_df.extend(fit.make_result(filename)).sort("source_file", "start_index", maintain_order=True)

        fit_trace = make_fit_trace(
            x=fit.x_data,
            y_fitted=fit.y_fitted,
            name=f"{filename}_{fit.start_index}",
            slope=fit.result.slope,
            rsquared=fit.result.rvalue,
            start_index=fit.start_index,
            y2_mean=fit.y2_mean,
        )
        patched_fig = Patch()
        # Clear the selection region
        patched_fig["layout"]["selections"].clear()

        patched_fig["data"].append(fit_trace)
        return patched_fig, result_df.to_dicts()

    @callback(
        Output("store-graph", "data", allow_duplicate=True),
        Input("table-results", "data_previous"),
        State("table-results", "data"),
        State("graph", "figure"),
        prevent_initial_call=True,
    )
    def remove_fit(
        data_previous: list[dict[str, Any]],
        data_current: list[dict[str, Any]],
        fig: FigureDict,
    ):
        if not data_previous:
            raise PreventUpdate

        previous = pl.from_dicts(data_previous, schema=result_df_schema)
        current = pl.from_dicts(data_current, schema=result_df_schema)

        removed = previous.join(current, on=previous.columns, how="anti")

        patched_fig = Patch()
        trace_index = find_trace_index(fig, removed.item(0, "source_file"), removed.item(0, "start_index"))
        if trace_index == -1:
            raise PreventUpdate

        del patched_fig["data"][trace_index]
        return patched_fig

    # @callback(
    #     Output("store-graph", "data", allow_duplicate=True),
    #     Output("btn-make-plot", "n_clicks"),
    #     Input("table-results", "selected_rows"),
    #     State("table-results", "data"),
    #     State("graph", "figure"),
    #     State("btn-make-plot", "n_clicks"),
    #     prevent_initial_call=True,
    # )
    # def highlight_selected_results(
    #     selected_rows: list[int], data: list[dict[str, Any]], fig: FigureDict, n_clicks: int
    # ):
    #     if not selected_rows:
    #         # if no rows are selected, restore original plot by simulating click on the plot button
    #         return no_update, n_clicks + 1

    #     rows = [data[i] for i in selected_rows]
    #     selected = pl.from_dicts(rows, schema=result_df_schema)

    #     patched_fig = Patch()
    #     for row in selected.iter_rows(named=True):
    #         trace_index = find_trace_index(fig, row["source_file"], row["start_index"])
    #         if trace_index == -1:
    #             continue

    #         patched_fig["data"][trace_index]["line"] = {"color": "red", "width": 5, "dash": "dash"}

    #     return patched_fig, no_update

    @callback(
        Output("download-results", "data"),
        Input("btn-export-results", "n_clicks"),
        State("table-results", "data"),
        prevent_initial_call=True,
    )
    def export_results(n_clicks: int, data: list[dict[str, Any]]) -> dict[str, Any]:
        df = pl.from_dicts(data, schema=result_df_schema)
        return dcc.express.send_bytes(df.write_excel, "o2view_results.xlsx")

    with server_is_started:
        server_is_started.notify()

    app.run(debug=False, host=host, port=port)
