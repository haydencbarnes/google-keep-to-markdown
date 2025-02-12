from __future__ import annotations

import dataclasses
import json
import pathlib
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


@dataclasses.dataclass
class Note:
    title: str
    text: str


def main():
    EXPORT_PATH.parent.mkdir(exist_ok=True)
    with open(EXPORT_PATH, 'w', encoding='utf-8') as file:
        file.write(_get_md_header())
        for note in _load_notes(IMPORT_PATH):
            file.write(_note_to_str(note))
    print('Export successful!')
    print(f'File {EXPORT_PATH} saved.')


def _get_md_header() -> str:
    return ''


def _load_notes(folder: pathlib.Path) -> list[Note]:
    notes = []
    for item in pathlib.Path(folder).iterdir():
        if item.suffix == '.json':
            try:
                notes.append(_load_note(item))
            except RuntimeError as err:
                print(f"Skipping note: '{err}'")
    return sorted(notes, key=lambda x: x.title.lower(), reverse=True)


def _load_note(path: pathlib.Path) -> Note:
    with open(path, encoding='utf-8') as file:
        note_obj = json.load(file)
        if note_obj['isTrashed']:
            raise RuntimeError(
                f"Note '{note_obj[JSON_NOTE_TITLE]}' "
                f"from file '{path}' is trashed"
            )
        return Note(title=_get_title(note_obj), text=_get_text(note_obj))


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
    try:
        text = note[JSON_NOTE_TEXT]
        if not isinstance(text, str):
            raise NotImplementedError
        else:
            return text
    except KeyError:
        items = []
        print(
            f"Note '{note[JSON_NOTE_TITLE]}' "
            "doesn't have text content. Converting..."
        )
        if not isinstance(note['listContent'], list):
            raise NotImplementedError
        for item in note['listContent']:
            checkbox = '[x]' if item['isChecked'] else '[ ]'
            items.append(f"* {checkbox} {item['text']}")
        return '\n'.join(items) + '\n'


def _note_to_str(note: Note) -> str:
    """Creates a single Markdown note"""
    return f'## {note.title}\n\n{note.text}\n\n---\n\n'


if __name__ == '__main__':
    main()
