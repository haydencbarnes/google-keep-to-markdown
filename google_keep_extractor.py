from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import re
import shutil
import sys
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.units import inch

TITLE_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
FILE_TIME_FORMAT = "%Y-%m-%d_%H-%M-%S"

# Use os.path.join for better cross-platform compatibility
IMPORT_PATH = pathlib.Path("Takeout", "Keep")
EXPORT_PATH = pathlib.Path("export")

JSON_NOTE_TITLE = "title"
JSON_NOTE_TEXT = "textContent"
JSON_NOTE_LIST = "listContent"

# Maximum filename length (to avoid issues on some filesystems)
MAX_FILENAME_LENGTH = 240  # Leave room for path and extension


@dataclasses.dataclass
class Note:
    title: str
    created_at: datetime
    text: str
    attachments: list[str] = dataclasses.field(default_factory=list)
    labels: list[str] = dataclasses.field(default_factory=list)


def main():
    parser = argparse.ArgumentParser(
        description="Export Google Keep notes to Markdown and/or PDF"
    )
    parser.add_argument(
        "--format",
        choices=["md", "pdf", "both"],
        default="md",
        help="Output format: md (Markdown), pdf (PDF), or both",
    )
    args = parser.parse_args()

    # Check if the import path exists
    if not IMPORT_PATH.exists():
        print(f"Error: Import path '{IMPORT_PATH}' not found.")
        print(
            "Please ensure you've copied the 'Takeout' folder to the same directory as this script."
        )
        sys.exit(1)

    EXPORT_PATH.mkdir(exist_ok=True)

    # Create format-specific directories
    if args.format in ["md", "both"]:
        md_path = EXPORT_PATH / "markdown"
        md_path.mkdir(exist_ok=True)

        # Create attachments directory inside markdown directory
        attachments_path = md_path / "attachments"
        attachments_path.mkdir(exist_ok=True)

    if args.format in ["pdf", "both"]:
        pdf_path = EXPORT_PATH / "pdf"
        pdf_path.mkdir(exist_ok=True)

    notes = _load_notes(IMPORT_PATH)
    print(f"Found {len(notes)} notes to process.")

    for i, note in enumerate(notes, 1):
        print(f"Processing note {i}/{len(notes)}: {note.title or 'Untitled'}")

        timestamp = note.created_at.strftime(FILE_TIME_FORMAT)
        if note.title:
            # Create a safe filename by replacing problematic characters
            safe_title = sanitize_filename(note.title)
            base_filename = f"{timestamp}__{safe_title}"
        else:
            base_filename = f"{timestamp}"

        # Ensure the filename isn't too long
        if len(base_filename) > MAX_FILENAME_LENGTH:
            base_filename = base_filename[:MAX_FILENAME_LENGTH]

        # Export to Markdown if requested
        if args.format in ["md", "both"]:
            note_export_path = EXPORT_PATH / "markdown" / f"{base_filename}.md"
            with open(note_export_path, "w", encoding="utf-8") as file:
                file.write(_note_to_str(note))
            _copy_attachments(note, EXPORT_PATH / "markdown")
            print(f"  Markdown file saved: {note_export_path}")

        # Export to PDF if requested
        if args.format in ["pdf", "both"]:
            pdf_export_path = EXPORT_PATH / "pdf" / f"{base_filename}.pdf"
            _note_to_pdf(note, pdf_export_path)
            print(f"  PDF file saved: {pdf_export_path}")

    print("\nExport successful!")
    print(f"Files saved to: {EXPORT_PATH.absolute()}")


def sanitize_filename(filename: str) -> str:
    """
    Create a safe filename that works across platforms.

    Replaces spaces with underscores and removes characters that are problematic
    in Windows, macOS, and Linux filesystems.
    """
    # Replace spaces with underscores
    safe_name = filename.replace(" ", "_")

    # Remove characters that are invalid in filenames across platforms
    # This includes: < > : " / \ | ? * and control characters
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", safe_name)

    # Replace multiple consecutive underscores with a single one
    safe_name = re.sub(r"_{2,}", "_", safe_name)

    # Remove leading/trailing periods and underscores which can cause issues
    safe_name = safe_name.strip("._")

    # Ensure we have at least something left
    if not safe_name:
        safe_name = "untitled"

    return safe_name


def _load_notes(folder: pathlib.Path) -> list[Note]:
    notes = []
    if not folder.exists():
        print(f"Warning: Folder '{folder}' does not exist.")
        return notes

    for item in folder.iterdir():
        if item.suffix.lower() == ".json":
            try:
                notes.append(_load_note(item))
            except Exception as err:
                print(f"Error processing file `{item}`: `{err}`")

    if not notes:
        print(f"Warning: No valid JSON files found in '{folder}'.")

    return sorted(notes, key=lambda x: x.created_at, reverse=True)


def _load_note(path: pathlib.Path) -> Note:
    with open(path, encoding="utf-8") as file:
        try:
            note_obj = json.load(file)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON in file '{path}': {e}")

        # Check if required fields exist
        if "isTrashed" not in note_obj:
            raise RuntimeError(f"Missing 'isTrashed' field in file '{path}'")
        if "createdTimestampUsec" not in note_obj:
            raise RuntimeError(f"Missing 'createdTimestampUsec' field in file '{path}'")

        if note_obj["isTrashed"]:
            raise RuntimeError(
                f"Note '{note_obj.get(JSON_NOTE_TITLE, 'Untitled')}' "
                f"from file '{path}' is trashed"
            )

        title, created_at = _get_title_and_date(note_obj)
        return Note(
            title=title,
            created_at=created_at,
            text=_get_text(note_obj),
            attachments=_get_attachments(note_obj),
            labels=_get_labels(note_obj),
        )


def _get_title_and_date(note: dict[str, object]) -> tuple[str, datetime]:
    usec_to_sec = 1e-6
    timestamp_usec = note["createdTimestampUsec"]
    if not isinstance(timestamp_usec, int):
        raise NotImplementedError("Non-integer timestamp not supported")

    created_at = datetime.fromtimestamp(timestamp_usec * usec_to_sec)

    if JSON_NOTE_TITLE not in note or not note[JSON_NOTE_TITLE]:
        title = ""
    else:
        title = note[JSON_NOTE_TITLE].strip()
        if not isinstance(title, str):
            raise NotImplementedError("Non-string title not supported")

        # Add status indicators to title
        if note.get("isArchived", False):
            title = f"[ARCHIVED] {title}"
        elif note.get("isPinned", False):
            title = f"[PINNED] {title}"

    return title, created_at


def _get_text(note: dict[str, object]) -> str:
    if JSON_NOTE_TEXT in note:
        text = note[JSON_NOTE_TEXT]
        if not isinstance(text, str):
            raise NotImplementedError("Non-string text content not supported")
        return text
    elif JSON_NOTE_LIST in note:
        items = []
        print(
            f"Note `{note.get(JSON_NOTE_TITLE, 'Untitled')}` "
            "doesn't have text content. Converting checklist..."
        )
        if not isinstance(note[JSON_NOTE_LIST], list):
            raise NotImplementedError("Non-list checklist not supported")

        for item in note[JSON_NOTE_LIST]:
            checkbox = "[x]" if item.get("isChecked", False) else "[ ]"
            items.append(f"* {checkbox} {item.get('text', '')}")

        return "\n".join(items) + "\n"
    else:
        print(
            f"Note `{note.get(JSON_NOTE_TITLE, 'Untitled')}` doesn't have `textContent` "
            f"or `{JSON_NOTE_LIST}`. No text will be extracted."
        )
        return ""


def _get_attachments(note: dict[str, object]) -> list[str]:
    if "attachments" in note and isinstance(note["attachments"], list):
        attachments = []
        for attachment in note["attachments"]:
            if isinstance(attachment, dict) and "filePath" in attachment:
                # Normalize path separators for cross-platform compatibility
                file_path = attachment["filePath"].replace("\\", "/")
                attachments.append(file_path)
        return attachments
    return []


def _get_labels(note: dict[str, object]) -> list[str]:
    if "labels" in note and isinstance(note["labels"], list):
        return [
            label.get("name", "")
            for label in note["labels"]
            if isinstance(label, dict) and "name" in label
        ]
    return []


def _note_to_str(note: Note) -> str:
    """Creates a single Markdown note from `Note` object."""
    if note.title:
        title = "# " + note.title
    else:
        title = "# " + note.created_at.strftime(TITLE_TIME_FORMAT)

    # Use forward slashes in paths for cross-platform compatibility in Markdown
    attachments_str = "\n".join(
        f"![{pathlib.Path(attachment).name}](attachments/{attachment.replace('\\', '/')})"
        for attachment in note.attachments
    )

    labels_str = f"Labels: {', '.join(note.labels)}" if note.labels else ""

    # Fixed the duplicate title issue
    all_elems = [title, note.text, attachments_str, labels_str]
    existing_elems = [elem.strip() for elem in all_elems if elem]
    md_content = "\n\n".join(existing_elems)
    return md_content + "\n"


def _note_to_pdf(note: Note, output_path: pathlib.Path) -> None:
    """Creates a PDF document from a Note object."""
    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72,
    )

    styles = getSampleStyleSheet()
    # Create a custom style for the title
    title_style = ParagraphStyle(
        "TitleStyle", parent=styles["Title"], fontSize=16, spaceAfter=12
    )

    # Create a custom style for the text content
    text_style = ParagraphStyle(
        "TextStyle", parent=styles["Normal"], fontSize=12, spaceAfter=12
    )

    # Create a custom style for labels
    label_style = ParagraphStyle(
        "LabelStyle", parent=styles["Italic"], fontSize=10, textColor="gray"
    )

    # Build the document content
    content = []

    # Add title
    if note.title:
        content.append(Paragraph(note.title, title_style))
    else:
        content.append(
            Paragraph(note.created_at.strftime(TITLE_TIME_FORMAT), title_style)
        )

    content.append(Spacer(1, 0.25 * inch))

    # Add creation date
    date_str = f"Created: {note.created_at.strftime(TITLE_TIME_FORMAT)}"
    content.append(Paragraph(date_str, styles["Italic"]))
    content.append(Spacer(1, 0.25 * inch))

    # Add text content
    if note.text:
        # Split by lines and create paragraphs
        for line in note.text.split("\n"):
            if line.strip():
                # Check if it's a checklist item
                if line.strip().startswith("* ["):
                    # Format checklist items
                    content.append(Paragraph(line, text_style))
                else:
                    content.append(Paragraph(line, text_style))
            else:
                content.append(Spacer(1, 0.1 * inch))

    # Add attachments
    for attachment in note.attachments:
        try:
            # Normalize path separators
            normalized_path = attachment.replace("\\", "/")
            img_path = IMPORT_PATH / normalized_path

            # Check if it's an image file
            if img_path.suffix.lower() in [".jpg", ".jpeg", ".png", ".gif"]:
                # Check if file exists
                if not img_path.exists():
                    content.append(
                        Paragraph(
                            f"Missing image: {pathlib.Path(attachment).name}",
                            styles["Italic"],
                        )
                    )
                    continue

                img = Image(
                    str(img_path), width=5 * inch, height=4 * inch, kind="proportional"
                )
                content.append(img)
                content.append(Spacer(1, 0.1 * inch))
                content.append(
                    Paragraph(
                        f"Attachment: {pathlib.Path(attachment).name}", styles["Italic"]
                    )
                )
            else:
                content.append(
                    Paragraph(
                        f"Attachment (non-image): {pathlib.Path(attachment).name}",
                        styles["Italic"],
                    )
                )
        except Exception as e:
            content.append(
                Paragraph(
                    f"Error including attachment {attachment}: {str(e)}",
                    styles["Italic"],
                )
            )

    # Add labels
    if note.labels:
        content.append(Spacer(1, 0.25 * inch))
        labels_text = f"Labels: {', '.join(note.labels)}"
        content.append(Paragraph(labels_text, label_style))

    # Build the PDF
    try:
        doc.build(content)
    except Exception as e:
        print(f"Error creating PDF '{output_path}': {e}")


def _copy_attachments(note: Note, base_path: pathlib.Path = EXPORT_PATH):
    """Copy attachments to the specified base path's attachments directory."""
    for attachment in note.attachments:
        # Normalize path separators
        normalized_path = attachment.replace("\\", "/")
        src_path = IMPORT_PATH / normalized_path
        dest_path = base_path / "attachments" / normalized_path

        # Create parent directories if they don't exist
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        if src_path.exists():
            try:
                shutil.copy2(src_path, dest_path)  # copy2 preserves metadata
                print(f"  Copied attachment: {dest_path.name}")
            except Exception as e:
                print(f"  Error copying attachment {src_path} to {dest_path}: {e}")
        else:
            print(f"  Warning: Attachment not found: {src_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExport cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        print("\nIf you continue to have issues, please report them on GitHub.")
        sys.exit(1)
