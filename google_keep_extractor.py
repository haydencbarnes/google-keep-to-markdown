from __future__ import annotations

import dataclasses
import json
import pathlib
import re
import shutil
from datetime import datetime

EXPORT_TIME = datetime.now()
FILE_TIME_FORMAT = '%Y-%m-%d_%H-%M-%S'
TITLE_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

IMPORT_PATH = pathlib.Path('Takeout/Keep')
EXPORT_PATH = pathlib.Path(
    f'export/export_{EXPORT_TIME.strftime(FILE_TIME_FORMAT)}.md'
)

JSON_NOTE_TITLE = 'title'
JSON_NOTE_TEXT = 'textContent'
JSON_NOTE_LIST = 'listContent'


@dataclasses.dataclass
class Note:
    title: str
    text: str
    attachments: list[str] = dataclasses.field(default_factory=list)
    labels: list[str] = dataclasses.field(default_factory=list)


def main():
    EXPORT_PATH.parent.mkdir(exist_ok=True)
    for note in _load_notes(IMPORT_PATH):
        sanitized_title = re.sub(r'[^\w\-_\. ]', '_', note.title)
        note_export_path = EXPORT_PATH.parent / f"{sanitized_title}.md"
        with open(note_export_path, 'w', encoding='utf-8') as file:
            file.write(_note_to_str(note))
        _copy_attachments(note)
        print(f'File {note_export_path} saved.')
    print('Export successful!')


def _load_notes(folder: pathlib.Path) -> list[Note]:
    notes = []
    for item in pathlib.Path(folder).iterdir():
        if item.suffix == '.json':
            try:
                notes.append(_load_note(item))
            except Exception as err:
                print(f"Error processing file {item}: {err}")
    return sorted(notes, key=lambda x: x.title.lower(), reverse=True)


def _load_note(path: pathlib.Path) -> Note:
    with open(path, encoding='utf-8') as file:
        note_obj = json.load(file)
        if note_obj['isTrashed']:
            raise RuntimeError(
                f"Note '{note_obj[JSON_NOTE_TITLE]}' "
                f"from file '{path}' is trashed"
            )
        return Note(
            title=_get_title(note_obj),
            text=_get_text(note_obj),
            attachments=_get_attachments(note_obj),
            labels=_get_labels(note_obj)
        )


def _get_title(note: dict[str, object]) -> str:
    usec_to_sec = 1e-6
    timestamp_usec = note['createdTimestampUsec']
    if not isinstance(timestamp_usec, int):
        raise NotImplementedError
    created_at = datetime.fromtimestamp(timestamp_usec * usec_to_sec).strftime(
        TITLE_TIME_FORMAT
    )

    if not note[JSON_NOTE_TITLE]:
        return created_at
    else:
        title = note[JSON_NOTE_TITLE]
        if not isinstance(title, str):
            raise NotImplementedError

        if note['isArchived']:
            return f'{created_at} -- [ARCHIVED] {title}'
        elif note['isPinned']:
            return f'{created_at} -- [PINNED] {title}'
        else:
            return f'{created_at} -- {title}'


def _get_text(note: dict[str, object]) -> str:
    if JSON_NOTE_TEXT in note:
        text = note[JSON_NOTE_TEXT]
        if not isinstance(text, str):
            raise NotImplementedError
        return text
    elif JSON_NOTE_LIST in note:
        items = []
        print(
            f"Note '{note[JSON_NOTE_TITLE]}' "
            "doesn't have text content. Converting..."
        )
        if not isinstance(note[JSON_NOTE_LIST], list):
            raise NotImplementedError
        for item in note[JSON_NOTE_LIST]:
            checkbox = '[x]' if item['isChecked'] else '[ ]'
            items.append(f"* {checkbox} {item['text']}")
        return '\n'.join(items) + '\n'
    else:
        print(f"Note '{note[JSON_NOTE_TITLE]}' doesn't have 'textContent' or 'listContent'.")
        print(f"Note '{note[JSON_NOTE_TITLE]}' doesn't have 'textContent' or '{JSON_NOTE_LIST}'.")
        return ""


def _get_attachments(note: dict[str, object]) -> list[str]:
    if 'attachments' in note:
        return [attachment['filePath'] for attachment in note['attachments']]
    return []


def _get_labels(note: dict[str, object]) -> list[str]:
    if 'labels' in note:
        return [label['name'] for label in note['labels']]
    return []


def _note_to_str(note: Note) -> str:
    """Creates a single Markdown note from `Note` object.

    If any note element is missing, it won't be included, and white-space is
    adjusted.

    Strips trailing white-space from each note element, so there's only a
    single newline between them.

    Ends note content with a single newline as in common Unix standard.
    """
    attachments_str = '\n'.join(
        f'![{pathlib.Path(attachment).name}]({attachment})'
        for attachment in note.attachments
    )
    labels_str = f'Labels: {", ".join(note.labels)}' if note.labels else ''
    all_elems = f'# {note.title}', note.text, attachments_str, labels_str
    existing_elems = []
    for elem in all_elems:
        if elem:
            existing_elems.append(elem.strip())
    md_content = '\n\n'.join(existing_elems)
    return md_content + '\n'


def _copy_attachments(note: Note):
    for attachment in note.attachments:
        src_path = IMPORT_PATH / attachment
        dest_path = EXPORT_PATH.parent / attachment
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src_path, dest_path)
        print(f'Copied attachment {src_path} to {dest_path}')


if __name__ == '__main__':
    main()
