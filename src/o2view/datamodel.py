import base64
import csv
import enum
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, NamedTuple, NotRequired, TypedDict

import plotly.graph_objects as go
import polars as pl
import polars.selectors as cs
from plotly.subplots import make_subplots
from scipy import stats

import janitor.polars  # noqa: F401 # isort:skip


def _simulate_contents(path: str) -> str:
    """Simulates the `contents` property of a dcc.Upload component. Used for testing."""
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")

    import mimetypes

    mime_type, _ = mimetypes.guess_type(path)
    return f"data:{mime_type};base64,{data}"


class PlotlyTemplate(enum.StrEnum):
    SIMPLE_WHITE = "simple_white"
    GGPLOT2 = "ggplot2"
    SEABORN = "seaborn"
    PLOTLY = "plotly"
    PLOTLY_WHITE = "plotly_white"
    PLOTLY_DARK = "plotly_dark"
    PRESENTATION = "presentation"
    XGRIDOFF = "xgridoff"
    YGRIDOFF = "ygridoff"
    GRIDON = "gridon"

    @classmethod
    def all_values(cls) -> list[str]:
        return [template.value for template in cls]

    # JSON string of the combined fit results. new results are added by reading the string into a df and then concatenating the new result df (obtained from LinearFit.make_result()).


class SelectedPoint(TypedDict):
    curveNumber: int
    pointNumber: int
    pointIndex: int
    x: float
    y: float
    customdata: NotRequired[list[Any]]


class SelectedRange(TypedDict):
    x: Annotated[list[float], "[min, max]"]
    y: Annotated[list[float], "[min, max]"]
    y2: NotRequired[Annotated[list[float], "[min, max]"]]


class SelectedData(TypedDict):
    points: list[SelectedPoint]
    range: SelectedRange


class LinregressResult(NamedTuple):
    slope: float
    intercept: float
    rvalue: float
    pvalue: float
    stderr: float
    intercept_stderr: float

    @property
    def rsquared(self):
        return self.rvalue**2


class FigureDict(TypedDict):
    data: list[dict[str, Any]]
    layout: dict[str, Any]
    frames: list[dict[str, Any]]


def detect_delimiter(
    decoded_string: str, skip_rows: int = 0, sample_rows: int = 3
) -> str:
    """
    Detect the delimiter used in a CSV-like text.

    This function splits the input string into lines, skips a specified number of rows, and uses a sample of subsequent
    rows to automatically detect the field delimiter via Python's csv.Sniffer.

    Args:
        decoded_string (str): The content of the file as a decoded string.
        skip_rows (int): The number of initial lines (e.g., headers) to skip.
        sample_rows (int): The number of rows to sample for delimiter detection.

    Returns:
        str: The detected delimiter character.

    Raises:
        ValueError: If the file is empty, there are insufficient rows for sampling, or delimiter detection fails.
    """
    sample_rows = max(1, sample_rows)

    lines = decoded_string.splitlines()
    if not lines:
        raise ValueError("File is empty")

    if len(lines) < skip_rows + sample_rows:
        raise ValueError("Insufficient rows for delimiter detection")

    sample = "\n".join(lines[skip_rows : skip_rows + sample_rows])

    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(sample)
        return dialect.delimiter
    except csv.Error as e:
        raise ValueError(f"Delimiter detection failed: {str(e)}") from e


def parse_contents(
    contents: str, filename: str, skip_rows: int = 0, separator: str = "auto"
) -> pl.DataFrame:
    """
    Parse base64-encoded file contents into a Polars DataFrame.

    This function handles CSV/TXT/TSV and Excel files based on the file extension. For CSV-like files, if the
    `separator` is set to "auto", the delimiter is automatically detected. Only numeric columns are retained, and a row
    index is inserted as the first column.

    Args:
        contents (str): The base64-encoded file content string. Expected format: 'data:[<mime>];base64,<data>'.
        filename (str): The name of the file (used to determine the file type).
        skip_rows (int): Number of initial rows to skip (e.g., header rows) during parsing.
        separator (str): Field delimiter for CSV-like files; use "auto" to detect automatically.

    Returns:
        pl.DataFrame: A Polars DataFrame containing only numeric columns with an added row index. If parsing fails or
        the file type is unsupported, an empty DataFrame is returned.
    """
    try:
        _, content_string = contents.split(",", 1)
        decoded_bytes = base64.b64decode(content_string)
    except Exception:
        return pl.DataFrame()

    suffix = Path(filename).suffix.lower()

    try:
        if suffix in {".csv", ".txt", ".tsv"}:
            content_str = decoded_bytes.decode("utf-8", errors="replace")
            if separator == "auto":
                separator = detect_delimiter(content_str, skip_rows=skip_rows)

            # Removes leading and trailing whitespace from each field. Why its there in the first place? Who knows.
            cleaned_content = "\n".join(
                separator.join(field.strip() for field in line.split(separator))
                for line in content_str.splitlines()
            )
            df = (
                pl.scan_csv(
                    io.StringIO(cleaned_content),
                    skip_rows=skip_rows,
                    separator=separator,
                )
                .select(cs.numeric())
                .clean_names(  # type: ignore
                    remove_special=True, strip_underscores=True, strip_accents=True
                )
                .collect()
            )
        elif suffix in {".xlsx", ".xls"}:
            df = (
                pl.read_excel(
                    io.BytesIO(decoded_bytes), read_options={"skip_rows": skip_rows}
                )
                .select(cs.numeric())
                .clean_names(  # type: ignore
                    remove_special=True, strip_underscores=True, strip_accents=True
                )
            )
        else:
            return pl.DataFrame()
    except Exception:
        return pl.DataFrame()

    return df.with_row_index()


@dataclass
class LinearFit:
    start_index: int
    end_index: int
    df: pl.DataFrame
    x_name: str
    y_name: str
    y2_name: str | None = field(default=None)
    y2_first: float = field(default=float("nan"))
    y2_last: float = field(default=float("nan"))
    result: LinregressResult = field(init=False)
    x_first: float = field(init=False)
    x_last: float = field(init=False)
    y_first: float = field(init=False)
    y_last: float = field(init=False)

    def __post_init__(self) -> None:
        x_data = self.df.get_column(self.x_name)
        y_data = self.df.get_column(self.y_name)
        self.x_first = x_data.item(0)
        self.x_last = x_data.item(-1)
        self.y_first = y_data.item(0)
        self.y_last = y_data.item(-1)
        if self.y2_name is not None:
            y2_data = self.df.get_column(self.y2_name)
            self.y2_first = y2_data.item(0)
            self.y2_last = y2_data.item(-1)

        res: Any = stats.linregress(x_data, y_data)
        self.result = LinregressResult(
            slope=res.slope,
            intercept=res.intercept,
            rvalue=res.rvalue,
            pvalue=res.pvalue,
            stderr=res.stderr,
            intercept_stderr=res.intercept_stderr,
        )
        self.df = self.df.with_columns(
            (self.result.slope * pl.col(self.x_name) + self.result.intercept).alias(
                "fitted"
            )
        )

    @property
    def x_data(self) -> pl.Series:
        return self.df.get_column(self.x_name)

    @property
    def y_data(self) -> pl.Series:
        return self.df.get_column(self.y_name)

    @property
    def y_fitted(self) -> pl.Series:
        return self.df.get_column("fitted")

    @property
    def y2_mean(self) -> float:
        if self.y2_name is not None:
            return self.df.get_column(self.y2_name).mean()  # type: ignore
        else:
            return float("nan")

    @property
    def rsquared(self) -> float:
        return self.result.rvalue**2

    def make_result(self, source_file: str) -> pl.DataFrame:
        return pl.DataFrame(
            {
                "source_file": source_file,
                # "fit_id": fit_id,
                "start_index": self.start_index,
                "end_index": self.end_index,
                "slope": self.result.slope,
                "rsquared": self.rsquared,
                "y2_mean": self.y2_mean,
                "x_name": self.x_name,
                "x_first": self.x_first,
                "x_last": self.x_last,
                "y_name": self.y_name,
                "y_first": self.y_first,
                "y_last": self.y_last,
                "y2_name": self.y2_name,
                "y2_first": self.y2_first,
                "y2_last": self.y2_last,
            }
        )


class DataSet:
    def __init__(self, file_path: str, df: pl.DataFrame) -> None:
        self.file_path = file_path
        self.df = df
        self.fig = make_subplots(specs=[[{"secondary_y": True}]])
        self.fits: list[LinearFit] = []
        self._x_name = ""
        self._y_name = ""
        self._y2_name: str | None = None

    @property
    def columns(self) -> list[str]:
        return self.df.columns

    @property
    def source_file_name(self) -> str:
        return Path(self.file_path).name

    @property
    def source_file_stem(self) -> str:
        return Path(self.file_path).stem

    def plot(
        self,
        x_name: str,
        y_name: str,
        y2_name: str | None = None,
        theme: str = "simple_white",
    ) -> go.Figure:
        self._x_name = x_name
        self._y_name = y_name
        self._y2_name = y2_name
        x = self.df.get_column(x_name)
        y = self.df.get_column(y_name)
        y2 = self.df.get_column(y2_name) if y2_name is not None else None
        self.fig.add_scattergl(
            x=x,
            y=y,
            name=y_name,
            mode="markers",
            marker=dict(color="royalblue", symbol="circle-open", opacity=0.2, size=3),
            secondary_y=False,
        )
        self.fig.update_xaxes(title_text=x_name)
        self.fig.update_yaxes(rangemode="tozero")
        self.fig.update_yaxes(title_text=y_name, secondary_y=False)
        if y2 is not None:
            self.fig.add_scattergl(
                x=x,
                y=y2,
                name=y2_name,
                mode="markers",
                marker=dict(color="crimson", symbol="cross", size=3),
                secondary_y=True,
            )
            self.fig.update_yaxes(title_text=y2_name, secondary_y=True)
        self.fig.update_layout(
            clickmode="event+select",
            template=theme,
            dragmode="select",
            autosize=True,
            height=600,
        )
        return self.fig

    def add_fit(self, start_index: int, end_index: int) -> None:
        if not self._x_name or not self._y_name:
            return
        fit_df = self.df.slice(start_index, end_index - start_index + 1)
        fit = LinearFit(
            start_index, end_index, fit_df, self._x_name, self._y_name, self._y2_name
        )
        self.fits.append(fit)
        self.fits.sort(key=lambda fit: fit.start_index)

        self.fig.add_scattergl(
            x=fit.x_data,
            y=fit.y_fitted,
            mode="lines",
            line=dict(color="darkorange", width=4),
            name=f"Fit {self.fits.index(fit) + 1}",
            hoverinfo="name+text",
            hovertext=f"slope={fit.result.slope:.4f}<br>r^2={fit.result.rvalue**2:.3f}<br>y2_mean={fit.y2_mean:.1f}",
        )

    def make_result_table(self) -> pl.DataFrame:
        self.fits.sort(key=lambda fit: fit.start_index)
        return pl.concat(fit.make_result(self.source_file_name) for fit in self.fits)
