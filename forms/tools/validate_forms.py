"""Convert each forms/*.xlsx to XForm XML with pyxform, then run ODK Validate on it.

Why not just `xls2xform`? On this Windows machine pyxform 4.5.0 starts Java with a
stripped environment (only TEMP/TMP/TMPDIR). Java then crashes with exit code
0xC0000409 and pyxform reports an empty "ODK Validate Errors". So this script
converts with --skip_validate and runs the bundled ODK_Validate.jar itself, with
the normal environment. The jar and the Java command are the same as pyxform's.
"""
import subprocess
import sys
from pathlib import Path

import pyxform
from pyxform.xls2xform import xls2xform_convert

FORMS = Path(__file__).resolve().parent.parent
JAR = Path(pyxform.__file__).parent / "validators" / "odk_validate" / "bin" / "ODK_Validate.jar"
OUT = FORMS / "build"


def main():
    OUT.mkdir(exist_ok=True)
    failed = 0
    for xlsx in sorted(FORMS.glob("d32_*.xlsx")):
        xml = OUT / (xlsx.stem + ".xml")
        print(f"== {xlsx.name}")
        try:
            warnings = xls2xform_convert(xlsform_path=str(xlsx), xform_path=str(xml), validate=False)
        except Exception as e:  # noqa: BLE001
            print("pyxform FAILED:", e)
            failed += 1
            continue
        print("pyxform: converted ->", xml.name, "| warnings:", warnings or "none")
        r = subprocess.run(
            ["java", "-Djava.awt.headless=true", "-jar", str(JAR), str(xml)],
            capture_output=True, text=True,
        )
        print("ODK Validate exit code:", r.returncode)
        print((r.stdout + r.stderr).strip())
        if r.returncode != 0:
            failed += 1
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
