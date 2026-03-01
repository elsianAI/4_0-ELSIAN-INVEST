"""Debug: which sections have parseable period headers after parser changes."""
import re
from elsian.extract.html_tables import (
    _SECTION_HEADER_RE, _DATE_DMY_RE, _YEAR_RE, _DATE_COL_RE, _MONTH_MAP
)

with open("cases/KAR/filings/SRC_001_annual_FY2025.txt") as f:
    lines = f.read().split("\n")

# Find sections
sections = []
for i, line in enumerate(lines):
    s = line.strip()
    m = _SECTION_HEADER_RE.search(s)
    if not m or len(s) > 120 or m.start() > 15:
        continue
    sections.append((i, s))

print(f"Total sections: {len(sections)}")

# Check which sections now have parseable period headers
for idx, (start, header) in enumerate(sections):
    end = sections[idx + 1][0] if idx + 1 < len(sections) else min(start + 120, len(lines))
    end = min(end, start + 120)
    sec_lines = lines[start:end]
    found_header = False
    for j, sline in enumerate(sec_lines[:10]):
        # Check DD MMM YY
        dmy_matches = list(_DATE_DMY_RE.finditer(sline))
        label_area_end = len(sline) // 3
        data_dmy = [dm for dm in dmy_matches if dm.start() > label_area_end]
        if len(data_dmy) >= 2:
            print(f"  SEC {start:5d} DMY: {header[:60]} -> {[dm.group() for dm in data_dmy]}")
            found_header = True
            break
        # Check YEAR
        ym = list(_YEAR_RE.finditer(sline))
        data_yrs = [y for y in ym if y.start() > label_area_end]
        if len(data_yrs) >= 2:
            print(f"  SEC {start:5d} YR:  {header[:60]} -> {[y.group() for y in data_yrs]}")
            found_header = True
            break
    if not found_header:
        print(f"  SEC {start:5d} ---: {header[:60]}")
