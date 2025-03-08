import polars as pl
from plotly.subplots import make_subplots
import plotly.graph_objects as go


def plot_dataset(
    df: pl.DataFrame,
    x_name: str,
    y_name: str,
    y2_name: str | None = None,
    theme: str = "simple_white",
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
    fig = fig.update_yaxes(rangemode="tozero")
    fig = fig.update_yaxes(title_text=y_name, secondary_y=False)
    if y2 is not None:
        fig = fig.add_scattergl(
            x=x,
            y=y2,
            name=y2_name,
            mode="markers",
            marker=dict(color="crimson", symbol="cross", size=3),
            secondary_y=True,
        )    
        fig = fig.update_yaxes(title_text=y2_name, secondary_y=True)
    fig = fig.update_layout(clickmode="event+select", template=theme, dragmode="select", autosize=True, height=700, margin=dict(l=20, r=20, t=20, b=20))
    return fig