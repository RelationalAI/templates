# Shared utilities for optimization templates

from pandas import read_csv as pd_read_csv


def read_csv(path):
    """Read CSV with RAI-compatible dtypes.

    Pandas may use StringDtype for string columns, but RAI's data().into()
    requires object dtype. This function ensures compatibility.
    """
    df = pd_read_csv(path)
    # Convert StringDtype to object for RAI compatibility
    string_cols = df.select_dtypes("string").columns
    if len(string_cols) > 0:
        df = df.astype({col: "object" for col in string_cols})
    return df
