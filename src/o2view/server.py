import io
from typing import TYPE_CHECKING, Any

import dash_mantine_components as dmc
import polars as pl
import setproctitle
from dash import (
    Dash,
    Input,
    Output,
    State,
    _dash_renderer,
    callback,
    dash_table,
    dcc,
)
from dash_iconify import DashIconify

from o2view.datamodel import PlotlyTemplate, parse_contents
from o2view.domino import terminate_when_parent_process_dies

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
    {"id": "fit_id", "name": "fit_id"},
    {"id": "start_index", "name": "start_index"},
    {"id": "end_index", "name": "end_index"},
    {"id": "slope", "name": "slope"},
    {"id": "rsquared", "name": "rsquared"},
    {"id": "mean_y2", "name": "mean_y2"},
    {"id": "name_x", "name": "name_x"},
    {"id": "start_x", "name": "start_x"},
    {"id": "end_x", "name": "end_x"},
    {"id": "name_y", "name": "name_y"},
    {"id": "start_y", "name": "start_y"},
    {"id": "end_y", "name": "end_y"},
    {"id": "name_y2", "name": "name_y2"},
    {"id": "start_y2", "name": "start_y2"},
    {"id": "end_y2", "name": "end_y2"},
]


def create_table_container():
    return


def start_dash(host: str, port: str, server_is_started: "Condition") -> None:
    setproctitle.setproctitle("o2view-dash")

    terminate_when_parent_process_dies()
    _dash_renderer._set_react_version("18.2.0")

    # external_stylesheets: list = [
    #     # Dash CSS
    #     "https://codepen.io/chriddyp/pen/bWLwgP.css",
    #     # Loading screen CSS
    #     "https://codepen.io/chriddyp/pen/brPBPO.css",
    # ]
    app = Dash(__name__, external_stylesheets=dmc.styles.ALL)  # type: ignore
    # cache = Cache(app.server, config={"CACHE_TYPE": "SimpleCache"})

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
                dmc.Box(dcc.Graph(id="graph")),
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
                                            style_as_list_view=True,
                                            style_header={
                                                "backgroundColor": "rgb(230, 230, 230)",
                                                "fontWeight": "bold",
                                                "textAlign": "left",
                                            },
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
                                            style_table={"overflowX": "scroll"},
                                            style_as_list_view=True,
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
        Output("download-results", "data"),
        Input("btn-export-results", "n_clicks"),
        State("table-results", "data"),
        prevent_initial_call=True,
    )
    def export_results(n_clicks: int, data: list[dict[str, Any]]) -> dict[str, Any]:
        df = pl.from_dicts(data)
        return dcc.send_data_frame(df.write_excel, "results.xlsx")

    with server_is_started:
        server_is_started.notify()

    app.run(debug=False, host=host, port=port)
