"""Print the export columns (name, XLSForm type, group) of each built form."""
import sys
from pathlib import Path
from openpyxl import load_workbook

FORMS = Path(__file__).resolve().parent.parent
for x in sorted(FORMS.glob("d32_*.xlsx")):
    ws = load_workbook(x)["survey"]
    hdr = [c.value for c in ws[1]]
    ti, ni = hdr.index("type"), hdr.index("name")
    print("##", x.stem)
    grp = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        t, n = row[ti], row[ni]
        if t == "begin_group":
            grp.append(n); continue
        if t == "end_group":
            grp.pop(); continue
        if t == "note":
            continue
        print(f"{'/'.join(grp+[n])}\t{t}")
