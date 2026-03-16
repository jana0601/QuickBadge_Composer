from __future__ import annotations

from pathlib import Path

import fitz
from PIL import Image
from PIL.ImageQt import ImageQt
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.generator import generate_record
from app.io.csv_loader import load_people_csv
from app.models.profile import TemplateProfile
from app.ui.template_canvas import TemplateCanvas


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("QuickBadge Composer")
        self.resize(1400, 900)

        self.profile = TemplateProfile()
        self.current_template_path = ""
        self.current_logo_path = ""
        self.current_csv_path = ""
        self.output_dir = str(Path.cwd() / "output")

        self.canvas = TemplateCanvas()
        self.canvas.clicked.connect(self.on_canvas_click)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QGridLayout(root)
        layout.setColumnStretch(0, 2)
        layout.setColumnStretch(1, 1)
        layout.addWidget(self.canvas, 0, 0)
        layout.addWidget(self._build_sidebar(), 0, 1)

    def _build_sidebar(self) -> QWidget:
        container = QWidget()
        side = QVBoxLayout(container)

        files_box = QGroupBox("Files")
        files_form = QFormLayout(files_box)
        self.template_edit = QLineEdit()
        self.logo_edit = QLineEdit()
        self.csv_edit = QLineEdit()
        self.out_edit = QLineEdit(self.output_dir)
        files_form.addRow("Template", self._row_with_button(self.template_edit, "Browse", self.pick_template))
        files_form.addRow("Logo (Optional)", self._row_with_button(self.logo_edit, "Browse", self.pick_logo))
        files_form.addRow("CSV (Batch)", self._row_with_button(self.csv_edit, "Browse", self.pick_csv))
        files_form.addRow("Output Dir", self._row_with_button(self.out_edit, "Browse", self.pick_output_dir))
        side.addWidget(files_box)

        profile_box = QGroupBox("Positioning / Style")
        profile_form = QFormLayout(profile_box)
        self.anchor_mode = QComboBox()
        self.anchor_mode.addItems(["QR", "Name", "Logo"])
        self.qr_size_spin = QSpinBox()
        self.qr_size_spin.setRange(30, 2000)
        self.qr_size_spin.setValue(self.profile.qr_size)
        self.name_size_spin = QSpinBox()
        self.name_size_spin.setRange(8, 300)
        self.name_size_spin.setValue(self.profile.font_size)
        self.logo_enabled_check = QCheckBox("Enable logo")
        self.logo_enabled_check.setChecked(self.profile.logo_enabled)
        self.logo_w_spin = QSpinBox()
        self.logo_w_spin.setRange(10, 2000)
        self.logo_w_spin.setValue(self.profile.logo_width)
        self.logo_h_spin = QSpinBox()
        self.logo_h_spin.setRange(10, 2000)
        self.logo_h_spin.setValue(self.profile.logo_height)
        self.output_format = QComboBox()
        self.output_format.addItems(["pdf", "png", "jpg"])
        self.output_format.setCurrentText(self.profile.output_format)
        self.color_edit = QLineEdit(self.profile.text_color_hex)
        self.font_edit = QLineEdit(self.profile.font_path)

        profile_form.addRow("Click target", self.anchor_mode)
        profile_form.addRow("QR size", self.qr_size_spin)
        profile_form.addRow("Name font size", self.name_size_spin)
        profile_form.addRow("Name font file", self._row_with_button(self.font_edit, "Browse", self.pick_font))
        profile_form.addRow("Text color (#RRGGBB)", self.color_edit)
        profile_form.addRow(self.logo_enabled_check)
        profile_form.addRow("Logo width", self.logo_w_spin)
        profile_form.addRow("Logo height", self.logo_h_spin)
        profile_form.addRow("Image output format", self.output_format)
        side.addWidget(profile_box)

        single_box = QGroupBox("Single Person")
        single_form = QFormLayout(single_box)
        self.single_name_edit = QLineEdit()
        self.single_coupon_edit = QLineEdit()
        single_form.addRow("Person name", self.single_name_edit)
        single_form.addRow("Coupon code", self.single_coupon_edit)
        side.addWidget(single_box)

        action_row1 = QHBoxLayout()
        save_profile_btn = QPushButton("Save Profile")
        load_profile_btn = QPushButton("Load Profile")
        save_profile_btn.clicked.connect(self.save_profile)
        load_profile_btn.clicked.connect(self.load_profile)
        action_row1.addWidget(save_profile_btn)
        action_row1.addWidget(load_profile_btn)
        side.addLayout(action_row1)

        action_row2 = QHBoxLayout()
        gen_single_btn = QPushButton("Generate Single")
        gen_batch_btn = QPushButton("Generate Batch")
        gen_single_btn.clicked.connect(self.generate_single)
        gen_batch_btn.clicked.connect(self.generate_batch)
        action_row2.addWidget(gen_single_btn)
        action_row2.addWidget(gen_batch_btn)
        side.addLayout(action_row2)

        self.status = QTextEdit()
        self.status.setReadOnly(True)
        self.status.setMinimumHeight(150)
        side.addWidget(QLabel("Status"))
        side.addWidget(self.status)
        side.addStretch(1)
        return container

    def _row_with_button(self, line_edit: QLineEdit, button_text: str, callback) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(line_edit)
        btn = QPushButton(button_text)
        btn.clicked.connect(callback)
        row.addWidget(btn)
        return w

    def log(self, message: str) -> None:
        self.status.append(message)

    def _sync_profile_from_ui(self) -> None:
        self.profile.template_path = self.template_edit.text().strip()
        ext = Path(self.profile.template_path).suffix.lower()
        if ext == ".pdf":
            self.profile.template_kind = "pdf"
        elif ext in {".png", ".jpg", ".jpeg"}:
            self.profile.template_kind = "image"
        self.profile.qr_size = self.qr_size_spin.value()
        self.profile.font_size = self.name_size_spin.value()
        self.profile.logo_enabled = self.logo_enabled_check.isChecked()
        self.profile.logo_width = self.logo_w_spin.value()
        self.profile.logo_height = self.logo_h_spin.value()
        self.profile.output_format = self.output_format.currentText()
        self.profile.text_color_hex = self.color_edit.text().strip() or "#000000"
        self.profile.font_path = self.font_edit.text().strip()

    def _apply_profile_to_ui(self) -> None:
        self.template_edit.setText(self.profile.template_path)
        self.qr_size_spin.setValue(self.profile.qr_size)
        self.name_size_spin.setValue(self.profile.font_size)
        self.logo_enabled_check.setChecked(self.profile.logo_enabled)
        self.logo_w_spin.setValue(self.profile.logo_width)
        self.logo_h_spin.setValue(self.profile.logo_height)
        self.output_format.setCurrentText(self.profile.output_format)
        self.color_edit.setText(self.profile.text_color_hex)
        self.font_edit.setText(self.profile.font_path)
        self._refresh_markers()

    def _refresh_markers(self) -> None:
        markers = [
            (self.profile.qr_x, self.profile.qr_y),
            (self.profile.name_x, self.profile.name_y),
        ]
        if self.profile.logo_enabled:
            markers.append((self.profile.logo_x, self.profile.logo_y))
        self.canvas.set_markers(markers)

    def _require_template(self) -> bool:
        if not self.template_edit.text().strip():
            QMessageBox.warning(self, "Missing template", "Please select a template image or PDF.")
            return False
        return True

    def pick_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose template",
            "",
            "Template files (*.png *.jpg *.jpeg *.pdf)",
        )
        if not path:
            return
        self.template_edit.setText(path)
        self.current_template_path = path
        try:
            self.load_template_preview(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Template load failed", str(exc))
            self.log(f"Template load failed: {exc}")
            return
        self.log(f"Template loaded: {path}")

    def pick_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose logo",
            "",
            "Image files (*.png *.jpg *.jpeg)",
        )
        if not path:
            return
        self.logo_edit.setText(path)
        self.current_logo_path = path
        self.log(f"Logo loaded: {path}")

    def pick_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose CSV", "", "CSV files (*.csv)")
        if not path:
            return
        self.csv_edit.setText(path)
        self.current_csv_path = path
        self.log(f"CSV selected: {path}")

    def pick_font(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose font",
            "",
            "Font files (*.ttf *.otf *.ttc)",
        )
        if not path:
            return
        self.font_edit.setText(path)
        self.profile.font_path = path
        self.log(f"Font selected: {path}")

    def pick_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if not path:
            return
        self.out_edit.setText(path)
        self.output_dir = path
        self.log(f"Output directory: {path}")

    def load_template_preview(self, template_path: str) -> None:
        ext = Path(template_path).suffix.lower()
        if ext == ".pdf":
            doc = fitz.open(template_path)
            page = doc[0]
            zoom = 2.0
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            image = QImage(
                pix.samples,
                pix.width,
                pix.height,
                pix.stride,
                QImage.Format.Format_RGB888,
            )
            self.canvas.set_pixmap(QPixmap.fromImage(image.copy()))
            self.profile.template_kind = "pdf"
            self.profile.preview_width = pix.width
            self.profile.preview_height = pix.height
            doc.close()
        else:
            pil_image = Image.open(template_path).convert("RGBA")
            qimage = ImageQt(pil_image)
            self.canvas.set_pixmap(QPixmap.fromImage(qimage))
            self.profile.template_kind = "image"
            self.profile.preview_width = pil_image.width
            self.profile.preview_height = pil_image.height
        self.profile.template_path = template_path
        self._refresh_markers()

    def on_canvas_click(self, x: float, y: float) -> None:
        mode = self.anchor_mode.currentText()
        if mode == "QR":
            self.profile.qr_x = x
            self.profile.qr_y = y
        elif mode == "Name":
            self.profile.name_x = x
            self.profile.name_y = y
        else:
            self.profile.logo_x = x
            self.profile.logo_y = y
        self._refresh_markers()
        self.log(f"{mode} anchor set to ({int(x)}, {int(y)})")

    def save_profile(self) -> None:
        self._sync_profile_from_ui()
        if not self._require_template():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save profile", "", "JSON files (*.json)")
        if not path:
            return
        self.profile.to_json(path)
        self.log(f"Profile saved: {path}")

    def load_profile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load profile", "", "JSON files (*.json)")
        if not path:
            return
        self.profile = TemplateProfile.from_json(path)
        self._apply_profile_to_ui()
        if self.profile.template_path:
            self.load_template_preview(self.profile.template_path)
        self.log(f"Profile loaded: {path}")

    def _validate_run_inputs(self) -> bool:
        self._sync_profile_from_ui()
        template = self.template_edit.text().strip()
        output_dir = self.out_edit.text().strip()
        if not template:
            QMessageBox.warning(self, "Missing template", "Please select a template file.")
            return False
        if not Path(template).exists():
            QMessageBox.warning(self, "Template not found", f"Template file does not exist:\n{template}")
            return False
        if self.profile.template_kind == "pdf" and (
            self.profile.preview_width <= 0
            or self.profile.preview_height <= 0
            or self.profile.template_path != template
        ):
            try:
                # Ensure preview dimensions exist for reliable PDF coordinate scaling.
                self.load_template_preview(template)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "PDF template error", str(exc))
                self.log(f"PDF template validation failed: {exc}")
                return False
        if not output_dir:
            QMessageBox.warning(self, "Missing output dir", "Please select output directory.")
            return False
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        return True

    def generate_single(self) -> None:
        if not self._validate_run_inputs():
            return
        person_name = self.single_name_edit.text().strip()
        coupon_code = self.single_coupon_edit.text().strip()
        if not person_name or not coupon_code:
            QMessageBox.warning(self, "Missing fields", "Name and coupon are required.")
            return
        try:
            output = generate_record(
                template_path=self.template_edit.text().strip(),
                profile=self.profile,
                person_name=person_name,
                coupon_code=coupon_code,
                output_dir=self.out_edit.text().strip(),
                logo_path=self.logo_edit.text().strip() or None,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Generation failed", str(exc))
            self.log(f"Single generation failed: {exc}")
            return
        self.log(f"Generated: {output}")
        QMessageBox.information(self, "Done", f"Generated file:\n{output}")

    def generate_batch(self) -> None:
        if not self._validate_run_inputs():
            return
        csv_path = self.csv_edit.text().strip()
        if not csv_path:
            QMessageBox.warning(self, "Missing CSV", "Please select CSV for batch processing.")
            return
        try:
            rows = load_people_csv(csv_path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Invalid CSV", str(exc))
            self.log(f"CSV validation failed: {exc}")
            return

        progress = QProgressDialog("Generating files...", "Cancel", 0, len(rows), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        failed: list[str] = []
        generated_count = 0
        for index, row in enumerate(rows, start=1):
            if progress.wasCanceled():
                self.log("Batch canceled by user.")
                break
            try:
                output = generate_record(
                    template_path=self.template_edit.text().strip(),
                    profile=self.profile,
                    person_name=row["person_name"],
                    coupon_code=row["coupon_code"],
                    output_dir=self.out_edit.text().strip(),
                    logo_path=self.logo_edit.text().strip() or None,
                )
                generated_count += 1
                self.log(f"Generated: {output}")
            except Exception as exc:  # noqa: BLE001
                failed.append(f"{row['person_name']} ({row['coupon_code']}): {exc}")
            progress.setValue(index)
        progress.close()

        if failed:
            preview = "\n".join(failed[:8])
            if len(failed) > 8:
                preview += "\n..."
            QMessageBox.warning(
                self,
                "Batch completed with errors",
                f"Generated {generated_count}/{len(rows)} files.\n\nErrors:\n{preview}",
            )
            self.log(f"Batch done with {len(failed)} failures.")
            return
        QMessageBox.information(self, "Batch complete", f"Generated {generated_count} files.")
        self.log(f"Batch complete: {generated_count} files.")

