"""Narrow compatibility handling for Gradio's deprecated status-code alias."""
import warnings

from starlette.exceptions import StarletteDeprecationWarning


def configure_warnings():
    # Gradio builds its error map even for successful queue requests. Starlette
    # 1.8 warns when that map reads the old name for 422. "once" is unreliable
    # when dependency warning contexts invalidate Python's warning registries.
    # Ignore only this exact advisory at the Gradio call site, not HTTP errors.
    warnings.filterwarnings(
        "ignore",
        message=r"^'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated\. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead\.$",
        category=StarletteDeprecationWarning,
        module=r"^gradio\.routes$",
    )
