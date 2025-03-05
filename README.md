# Google Keep Extractor

Parse JSON files from Google Keep export and convert them to Markdown files or PDFs. Attachments and images are preserved.

## Getting Started

You can download your Google Keep backup file by visiting:

<https://takeout.google.com/takeout/custom/keep>

You can export data to a `.zip` or `.tgz` archive which has the following structure:

```
└── Takeout
    ├── Keep
    │   ├── JSON & HTML files, and attachments
    └── archive_browser.html
```

## Installation

1. Copy the `Takeout` folder into the root of this repo.

2. Set up a virtual environment (recommended):

   ```bash
   # Create a virtual environment
   python -m venv venv

   # Activate the virtual environment
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. Install required packages:

   ```bash
   pip install reportlab
   ```

## Usage

Run the script with your preferred export format:

```bash
# Export to Markdown only (default)
python google_keep_extractor.py

# Export to PDF only
python google_keep_extractor.py --format pdf

# Export to both Markdown and PDF
python google_keep_extractor.py --format both
```

Python 3.8 or later is required.

After running the script, files are created in the `export` directory with the following structure:

```
export/
├── markdown/
│   ├── attachments/
│   │   └── ... (your attachments)
│   └── ... (your markdown files)
└── pdf/
    └── ... (your PDF files)
```

## Main Features

- Exports to Markdown and/or PDF formats
- Preserves timestamps in filenames
- Includes attachments
- Preserves Keep's Labels
- Maintains checklist formatting
- Handles pinned and archived notes
- Cross-platform compatible (Windows, macOS, Linux)
- Safely handles special characters in filenames

## Requirements

- Python 3.8+
- ReportLab (for PDF export)

## Notes

- Trashed notes are skipped during export
- Special characters in note titles are sanitized for safe filenames
- Pinned and archived notes are marked in the title
- Very long filenames are automatically truncated to avoid filesystem issues
- Progress information is displayed during export

## Troubleshooting

If you encounter any issues:

1. Make sure the `Takeout` folder is in the same directory as the script
2. Check that you have the required Python version (3.8+)
3. Ensure ReportLab is installed correctly
4. For PDF export issues, make sure your attachments are accessible

