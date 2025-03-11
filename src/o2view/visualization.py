from typing import Literal

import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots

from o2view.datamodel import FigureDict


def plot_dataset(
    df: pl.DataFrame,
    x_name: str,
    y_name: str,
    y2_name: str | None = None,
    theme: str = "simple_white",
    y_rangemode: Literal["normal", "tozero", "nonnegative"] = "normal",
    show_legend: bool = True,
) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    x = df.get_column(x_name)
    y = df.get_column(y_name)
    y2 = df.get_column(y2_name) if y2_name is not None else None

    fig = fig.add_scattergl(
        x=x,
        y=y,
        name=y_name,
        mode="markers",
        marker=dict(color="royalblue", symbol="circle-open", opacity=0.2, size=3),
        secondary_y=False,
    )
    fig = fig.update_xaxes(title_text=x_name)
    fig = fig.update_yaxes(rangemode=y_rangemode)
    fig = fig.update_yaxes(title_text=y_name, secondary_y=False)
    if y2 is not None:
        fig = fig.add_scattergl(
            x=x,
            y=y2,
            name=y2_name,
            mode="markers",
            marker=dict(color="crimson", symbol="hexagon-open", opacity=0.2, size=3),
            secondary_y=True,
        )
        fig = fig.update_yaxes(title_text=y2_name, secondary_y=True)
    fig = fig.update_layout(
        template=theme,
        dragmode="select",
        selectdirection="h",
        autosize=True,
        height=800,
        showlegend=show_legend,
        # legend=dict(entrywidth=0, entrywidthmode="pixels"),
    )
    return fig


def make_fit_trace(
    x: pl.Series,
    y_fitted: pl.Series,
    name: str,
    slope: float,
    rsquared: float,
    start_index: int,
    y2_mean: float | None = None,
) -> go.Scattergl:
    y2_mean = y2_mean or float("nan")
    return go.Scattergl(
        x=x.to_list(),
        y=y_fitted.to_list(),
        mode="lines",
        line=dict(color="darkorange", width=4),
        name=name,
        hoverinfo="text",
        hovertext=f"start_index={start_index}<br>slope={slope:.4f}<br>r^2={rsquared**2:.3f}<br>y2_mean={y2_mean:.1f}",
        showlegend=False,
    )


def find_trace_index(
    figure_dict: FigureDict, source_file: str, start_index: int
) -> int:
    return next(
        (
            i
            for i, trace in enumerate(figure_dict["data"])
            if trace["name"] == f"{source_file}_{start_index}"
        ),
        -1,
    )
