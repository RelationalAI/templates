"""Shared model exports for the starter template.

`rai models deploy --path model` deploys everything this package declares.
"""

from .schema import Item, model
from .source import load_sample_data

__all__ = ["Item", "load_sample_data", "model"]
