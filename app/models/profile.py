from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path


@dataclass
class TemplateProfile:
    template_path: str = ""
    template_kind: str = "image"  # image or pdf
    preview_width: int = 0
    preview_height: int = 0

    qr_x: float = 20.0
    qr_y: float = 20.0
    qr_size: int = 180

    name_x: float = 20.0
    name_y: float = 220.0
    font_size: int = 28
    font_path: str = ""
    text_color_hex: str = "#000000"

    logo_enabled: bool = False
    logo_x: float = 20.0
    logo_y: float = 320.0
    logo_width: int = 160
    logo_height: int = 80

    output_format: str = "pdf"  # pdf, png, jpg

    def to_json(self, file_path: str | Path) -> None:
        Path(file_path).write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def from_json(cls, file_path: str | Path) -> "TemplateProfile":
        data = json.loads(Path(file_path).read_text(encoding="utf-8"))
        return cls(**data)

