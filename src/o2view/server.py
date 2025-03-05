from typing import TYPE_CHECKING, Any

import dash_ag_grid as dag
import polars as pl
import setproctitle
from dash import Dash, dcc, html, dash_table, callback, Output, Input, State

from o2view.datamodel import PlotlyTemplate, parse_contents
from o2view.domino import terminate_when_parent_process_dies

if TYPE_CHECKING:
    from multiprocessing.synchronize import Condition

upload_link_style = {"color": "#007bff", "textDecoration": "underline", "cursor": "pointer"}
upload_style = {
    "width": "100%",
    "height": "60px",
    "lineHeight": "60px",
    "borderWidth": "1px",
    "borderStyle": "dashed",
    "borderRadius": "5px",
    "textAlign": "center",
    "margin": "10px 0",
}


def create_data_input_controls():
    return html.Div(
        [
            # First row: Skip Rows and Column Separator
            html.Div(
                [
                    # First Column
                    html.Div(
                        [
                            html.Label("Skip Rows"),
                            dcc.Input(id="input-skip-rows", type="number", value=57, min=0),
                        ],
                        style={"flex": "1"},
                    ),
                    # Second Column
                    html.Div(
                        [
                            html.Label("Column Separator"),
                            dcc.Dropdown(
                                id="dropdown-separator",
                                options=[
                                    {"label": "Detect Automatically", "value": "auto"},
                                    {"label": "Comma (',')", "value": ","},
                                    {"label": "Semicolon (';')", "value": ";"},
                                    {"label": "Tab ('\\t')", "value": "\t"},
                                    {"label": "Pipe ('|')", "value": "|"},
                                ],
                                value="auto",
                            ),
                        ],
                        style={"flex": "2"},
                    ),
                    html.Div(
                        [
                            html.Button(
                                "Clear Data",
                                id="btn-clear-data",
                                n_clicks=0,
                                style={"margin-top": "10px"},
                            ),
                        ],
                        style={"flex": "1"},
                    ),
                ],
                style={"display": "flex", "justify-content": "flex-start", "align-items": "flex-end", "gap": "10px"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            dcc.Upload(
                                id="upload-data",
                                children=html.Div(
                                    [
                                        "Drag and Drop or ",
                                        html.A("Select File", style=upload_link_style),
                                    ]
                                ),
                                multiple=False,
                                style=upload_style,
                            ),
                            html.Label("Current File: -", id="label-current-file"),
                        ],
                        style={"flex": "1"},
                    ),
                ],
                style={"display": "flex", "margin-top": "10px"},
            ),
        ],
        style={
            "border": "1px solid #ddd",
            "borderRadius": "5px",
            "padding": "15px",
            "boxShadow": "2px 2px 2px rgba(0,0,0,0.1)",
        },
    )


def create_axis_controls():
    return html.Div(
        [
            html.Div(
                [
                    html.Label("X Axis"),
                    dcc.Dropdown(
                        id="dropdown-x-data",
                        placeholder="Select column for x-axis",
                    ),
                ],
                style={"flex": "1", "padding": "10px"},
            ),
            html.Div(
                [
                    html.Label("Y Axis"),
                    dcc.Dropdown(
                        id="dropdown-y-data",
                        placeholder="Select column for y-axis",
                    ),
                ],
                style={"flex": "1", "padding": "10px"},
            ),
            html.Div(
                [
                    html.Label("Secondary Y Axis"),
                    dcc.Dropdown(
                        id="dropdown-y2-data",
                        placeholder="Select column for secondary y-axis",
                    ),
                ],
                style={"flex": "1", "padding": "10px"},
            ),
        ],
        style={"display": "flex"},
    )


def create_plot_controls():
    return html.Div(
        [
            html.Div(
                [
                    html.Label("Plot Style"),
                    dcc.Dropdown(
                        id="dropdown-plot-template",
                        options=PlotlyTemplate.all_values(),
                        value=PlotlyTemplate.SIMPLE_WHITE,
                        multi=False,
                    ),
                ],
                style={"flex": "0 0 25%", "padding": "10px"},
            ),
            html.Div(
                [
                    html.Button("Plot", id="btn-make-plot", n_clicks=0),
                ],
                style={"flex": "0 0 8.33%", "padding": "10px", "alignSelf": "flex-end"},
            ),
            html.Div(
                [
                    html.Button("Add fit", id="btn-add-fit", n_clicks=0),
                ],
                style={"flex": "0 0 16.67%", "padding": "10px", "alignSelf": "flex-end"},
            ),
        ],
        style={"display": "flex", "marginTop": "10px"},
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
    return html.Div([
        dash_table.DataTable(
            id="table-results",
            columns=result_table_columns,
            # hidden_columns=["name_x", "start_x", "end_x", "name_y", "start_y", "end_y", "name_y2", "start_y2", "end_y2"],
            style_as_list_view=True,
            style_header={"backgroundColor": "rgb(230, 230, 230)", "fontWeight": "bold", "textAlign": "left"},
            style_table={"overflowX": "scroll"},
            row_deletable=True,
            data=[],
            # export_format="xlsx",
            # export_headers="name",
        ),
        # html.Button("Export", id="btn-export-results", n_clicks=0),
        dcc.Download(id="download-results"),
    ])


def create_dataset_table(df: pl.DataFrame | None = None) -> html.Div:
    df = df or pl.DataFrame()
    return html.Div(
        [
            html.H5("Uploaded Data"),
            dash_table.DataTable(
                id="table-dataset",
                columns=[{"name": col_name, "id": col_name} for col_name in df.columns],
                data=df.to_dicts(),
                style_header={"backgroundColor": "rgb(230, 230, 230)", "fontWeight": "bold", "textAlign": "left"},
                style_table={"overflowX": "scroll"},
                style_as_list_view=True,
            )
        ]
    )


def create_layout():
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        html.Div(
                            [
                                create_data_input_controls(),
                                create_axis_controls(),
                                create_plot_controls(),
                            ],
                            style={
                                "border": "1px solid #ddd",
                                "borderRadius": "5px",
                                "padding": "15px",
                                "boxShadow": "2px 2px 2px rgba(0,0,0,0.1)",
                            },
                        ),
                        style={"flex": "1", "padding": "10px"},
                    ),
                    html.Div(
                        [
                            create_results_table(),
                            html.Div(
                                [
                                    html.Button(
                                        "Remove selected result(s)",
                                        id="btn-remove-results",
                                        n_clicks=0,
                                        style={"marginRight": "10px"},
                                    ),
                                    html.Button(
                                        "Export results",
                                        id="btn-export-results",
                                        n_clicks=0,
                                    ),
                                ],
                                style={"display": "flex", "marginTop": "10px"},
                            ),
                        ],
                        style={"flex": "1", "padding": "10px"},
                    ),
                ],
                style={"display": "flex"},
            ),
            html.Div(dcc.Graph(id="graph", style={"width": "100%"}), style={"padding": "10px"}),
            html.Div(
                [
                    create_dataset_table(),
                ]
            ),
            dcc.Store(id="store-dataset"),
        ],
    )


def start_dash(host: str, port: str, server_is_started: "Condition") -> None:
    setproctitle.setproctitle("o2-view-dash")

    terminate_when_parent_process_dies()
    app = Dash(__name__, external_stylesheets=["https://codepen.io/chriddyp/pen/bWLwgP.css"])
    # cache = Cache(app.server, config={"CACHE_TYPE": "SimpleCache"})

    app.layout = create_layout()

    @callback(
        Output("store-dataset", "data"),
        Output("table-dataset", "columns"),
        Output("table-dataset", "data"),
        Output("dropdown-x-data", "options"),
        Output("dropdown-y-data", "options"),
        Output("dropdown-y2-data", "options"),
        Output("dropdown-x-data", "value"),
        Output("dropdown-y-data", "value"),
        Output("dropdown-y2-data", "value"),
        Input("upload-data", "contents"),
        State("upload-data", "filename"),
        State("input-skip-rows", "value"),
        State("dropdown-separator", "value"),
        prevent_initial_call=True,
    )
    def read_presens(contents: str, filename: str, skip_rows: int = 57, separator: str = ";") -> tuple[list[dict[str, Any]], list[dict[str, str]], list[dict[str, Any]], list[str], list[str], list[str], str, str, str] | None:
        if not contents or not filename:
            return None

        parsed = parse_contents(contents, filename, skip_rows, separator)
        cols = parsed.columns
        return parsed.to_dicts(), [{"name": col_name, "id": col_name} for col_name in cols], parsed.to_dicts(), cols, cols, cols, cols[1], cols[2], cols[-1]

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
