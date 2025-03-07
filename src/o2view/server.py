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
    html,
)

from o2view.datamodel import PlotlyTemplate, parse_contents
from o2view.domino import terminate_when_parent_process_dies

if TYPE_CHECKING:
    from multiprocessing.synchronize import Condition

upload_link_style = {
    "color": "#007bff",
    "textDecoration": "underline",
    "cursor": "pointer",
}
upload_style = {
    "width": "100%",
    "height": "60px",
    "lineHeight": "60px",
    "borderWidth": "1px",
    "borderStyle": "dashed",
    "borderRadius": "5px",
    "textAlign": "center",
    # "margin": "10px 0",
}


def create_file_property_controls():
    return dmc.Group(
        wrap="nowrap",
        children=[
            dmc.Stack(
                align="flex-start",
                maw=200,
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
            dmc.Stack(
                justify="flex-start",
                flex=1,
                gap=5,
                children=[
                    dcc.Upload(
                        id="upload-data",
                        children=dmc.Box(
                            [
                                "Drag and Drop or ",
                                html.A("Select File", style=upload_link_style),
                            ]
                        ),
                        multiple=False,
                        style=upload_style,
                    ),
                    dmc.Text("Current File: -", id="label-current-file"),
                ],
            ),
        ],
    )


def create_axis_controls():
    return dmc.Group(
        grow=True,
        wrap="nowrap",
        children=[
            dmc.Box(
                dmc.Select(
                    id="dropdown-x-data",
                    label="X-axis",
                    placeholder="Select one",
                    withAsterisk=True,
                )
            ),
            dmc.Box(
                dmc.Select(
                    id="dropdown-y-data",
                    label="Y-axis",
                    placeholder="Select one",
                    withAsterisk=True,
                )
            ),
            dmc.Box(
                dmc.Select(
                    id="dropdown-y2-data",
                    label="Secondary y-axis",
                    placeholder="Select one (optional)",
                    clearable=True,
                    allowDeselect=True,
                )
            ),
        ],
    )


def create_plot_controls():
    return dmc.Group(
        grow=True,
        wrap="nowrap",
        children=[
            dmc.Select(
                id="dropdown-plot-template",
                label="Plot Style",
                data=PlotlyTemplate.all_values(),
                value=PlotlyTemplate.SIMPLE_WHITE,
            ),
            dmc.Button("Plot", id="btn-make-plot"),
            dmc.Button("Add fit", id="btn-add-fit"),
        ],
    )


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


def create_results_table():
    return dmc.Box(
        [
            dash_table.DataTable(
                id="table-results",
                columns=result_table_columns,
                # hidden_columns=["name_x", "start_x", "end_x", "name_y", "start_y", "end_y", "name_y2", "start_y2", "end_y2"],
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
    )


def create_dataset_table(df: pl.DataFrame | None = None) -> dmc.Box:
    df = df or pl.DataFrame()
    return dmc.Box(
        [
            dash_table.DataTable(
                id="table-dataset",
                columns=[{"name": col_name, "id": col_name} for col_name in df.columns],
                data=df.to_dicts(),
                style_header={
                    "backgroundColor": "rgb(230, 230, 230)",
                    "fontWeight": "bold",
                    "textAlign": "left",
                },
                style_table={"overflowX": "scroll"},
                style_as_list_view=True,
            ),
        ]
    )


def create_table_container():
    return dmc.Tabs(
        [
            dmc.TabsList(
                [
                    dmc.TabsTab("Results", value="results"),
                    dmc.TabsTab("Current Dataset", value="dataset"),
                ]
            ),
            dmc.TabsPanel(
                create_results_table(),
                value="results",
            ),
            dmc.TabsPanel(
                create_dataset_table(),
                value="dataset",
            ),
        ],
        value="results",
    )


def create_layout():
    return dmc.Container(
        fluid=True,
        mt=20,
        mb=20,
        children=[
            dmc.Box(
                [
                    dmc.Box(
                        dmc.Paper(
                            p="xs",
                            withBorder=True,
                            children=[
                                create_file_property_controls(),
                                create_axis_controls(),
                                create_plot_controls(),
                                dmc.Button("Export results", id="btn-export-results"),
                            ],
                        ),
                    ),
                ],
            ),
            dmc.Box(dcc.Graph(id="graph", style={"width": "100%"})),
            dmc.Box(create_table_container()),
            dcc.Store(id="store-dataset"),
            dcc.Store(id="store-results"),
        ],
    )


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

    app.layout = dmc.MantineProvider(create_layout())

    @callback(
        Output("store-dataset", "data"),
        Input("upload-data", "contents"),
        State("upload-data", "filename"),
        State("input-skip-rows", "value"),
        State("dropdown-separator", "value"),
        prevent_initial_call=True,
    )
    def read_presens(
        contents: str, filename: str, skip_rows: int = 57, separator: str = ";"
    ) -> str | None:
        if not contents or not filename:
            return None

        parsed = parse_contents(contents, filename, skip_rows, separator)
        return parsed.write_json()

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
    def populate_controls(
        data: str,
    ) -> tuple[
        list[dict[str, str]],
        list[dict[str, Any]],
        list[str],
        list[str],
        list[str],
        str,
        str,
        str,
    ]:
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
