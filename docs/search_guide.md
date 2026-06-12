# 🔍 Pandora Advanced Search Guide

Pandora supports a powerful search syntax that allows you to filter your media vault like a pro. You can combine multiple terms, use prefixes, and even exclude specific tags or names.

## 🌟 Basics
*   **Simple Search:** Just type any word (e.g., `vacation`) to find files with that word in the filename or tags.
*   **Exact Phrases:** Use quotes for exact matches: `"my birthday party"`.

## 🏷️ Prefixes
You can target specific fields using prefixes followed by a colon (`:`):

| Prefix | Description | Example |
| :--- | :--- | :--- |
| `tag:` | Search only within tags | `tag:funny` |
| `name:` | Search only within filenames | `name:IMG_` |
| `cat:` | Search for a specific category | `cat:Video` |

## 🚫 Exclusions
To hide certain results, use the minus sign (`-`) before any term or prefix:

| Search | Result |
| :--- | :--- |
| `-Solo` | Hides files with "Solo" in name or tags |
| `-tag:Work` | Hides files tagged with "Work" |
| `-name:clip` | Hides files with "clip" in the filename |

## 🚀 Pro Examples

*   **Find all funny videos:**
    `cat:Video tag:funny`
*   **Find videos tagged 'milf' but EXCLUDE anything tagged 'Solo':**
    `tag:milf -tag:Solo`
*   **Find images that are NOT named 'backup':**
    `cat:Image -name:backup`
*   **Complex Combo:**
    `cat:Video "vacation 2024" -tag:boring`
    *(Finds videos with the exact phrase "vacation 2024" in filename/tags, but hides those tagged "boring")*

## 🔢 Sorting
You can also change the sorting order using the dropdown next to the title:
*   **Date Added:** When you uploaded the file.
*   **Date Created:** Extracted from the file's metadata (if available).
*   **Name:** Natural alphabetical sorting (e.g., `2.mp4` comes before `10.mp4`).
*   **Size:** Find your largest or smallest files.
*   **Duration:** Sort videos by their length.
