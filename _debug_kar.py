"""Debug: check what sections are detected in SRC_003."""
import re
import sys

with open('cases/KAR/filings/SRC_003_annual_FY2024.txt') as f:
    lines = f.readlines()

_SECTION_PATTERNS = {
    "income_statement": re.compile(
        r"(?:consolidated\s+)?(?:statement|statements)\s+of\s+"
        r"(?:income|operations|earnings|profit\s+or\s+loss|comprehensive\s+income"
        r"|loss|profit\s+and\s+loss)",
        re.I,
    ),
    "balance_sheet": re.compile(
        r"(?:consolidated\s+)?(?:balance\s+sheet|statement\s+of\s+financial\s+position)",
        re.I,
    ),
    "cash_flow": re.compile(
        r"(?:consolidated\s+)?(?:statement|statements)\s+of\s+cash\s+flow",
        re.I,
    ),
}

found = []
for i, line in enumerate(lines):
    text = line.strip()
    for section_type, pattern in _SECTION_PATTERNS.items():
        if pattern.search(text):
            found.append((i+1, section_type, text[:120]))

print(f'Section matches in SRC_003 ({len(found)}):')
for ln, st, txt in found:
    print(f'  L{ln} [{st}]: {txt}')

# Also check what the actual section header looks like near line 5177
print('\n--- Lines 5175-5182 of SRC_003 ---')
for i in range(5174, min(5185, len(lines))):
    print(f'  L{i+1}: {lines[i].rstrip()!r}')

# Check CFS section
print('\n--- Looking for cash flow ---')
for i, line in enumerate(lines):
    if 'cash flow' in line.lower() and ('statement' in line.lower() or 'consolidated' in line.lower()):
        print(f'  L{i+1}: {line.strip()[:120]}')
