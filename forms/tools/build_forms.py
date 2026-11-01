"""Build the NESFIC D-32 XLSForm files (.xlsx) from code.

Usage (from the project root, with the forms venv):
    forms/.venv/Scripts/python.exe forms/tools/build_forms.py [--ref-year-start 2026-04-01] [--version 2026-11-01]

Every form is defined here as survey / choices / settings rows. Re-run to rebuild.
Assamese text is machine-drafted and must be checked by a native speaker.
"""
import argparse
from pathlib import Path

from openpyxl import Workbook

EN = "label::English (en)"
AS = "label::Assamese (as)"
LANGS = ("English (en)", "Assamese (as)")
OUT_DIR = Path(__file__).resolve().parent.parent

# Extra per-language columns: key in Q(...) kwargs -> column prefix
ML_KEYS = {"hint": "hint", "msg": "constraint_message", "reqmsg": "required_message"}

# ---------------------------------------------------------------- helpers


def Q(type_, name, en=None, as_=None, **kw):
    """One survey row. msg/hint/reqmsg take an (en, as) tuple."""
    row = {"type": type_, "name": name}
    if en is not None:
        row[EN] = en
        row[AS] = as_
    for key, val in kw.items():
        if key in ML_KEYS:
            row[f"{ML_KEYS[key]}::{LANGS[0]}"] = val[0]
            row[f"{ML_KEYS[key]}::{LANGS[1]}"] = val[1]
        else:
            row[key] = val
    return row


def note(name, en, as_, **kw):
    return Q("note", name, en, as_, **kw)


def begin(name, en, as_, **kw):
    return Q("begin_group", name, en, as_, **kw)


def end():
    return {"type": "end_group"}


def choices(list_name, items):
    """items: list of (name, en, as)."""
    return [{"list_name": list_name, "name": n, EN: e, AS: a} for n, e, a in items]


def write_xlsx(path, survey, choice_rows, settings):
    wb = Workbook()
    wb.remove(wb.active)
    for title, rows in (("survey", survey), ("choices", choice_rows), ("settings", [settings])):
        ws = wb.create_sheet(title)
        cols = []
        for r in rows:
            for k in r:
                if k not in cols:
                    cols.append(k)
        ws.append(cols)
        for r in rows:
            ws.append([r.get(c, None) for c in cols])
    wb.save(path)


def settings_row(form_id, title, version):
    return {
        "form_title": title,
        "form_id": form_id,
        "version": version,
        "default_language": "English (en)",
    }


# --------------------------------------------------------- shared pieces

YESNO = choices("yesno", [("yes", "Yes", "হয়"), ("no", "No", "নহয়")])
SPECIES = choices(
    "species",
    [
        ("imc", "Indian major carps (rohu, catla, mrigal)", "ভাৰতীয় প্ৰধান কাৰ্প (ৰুই, কাতলা, মৃগেল)"),
        ("exotic", "Exotic carps (grass, silver, common carp)", "বিদেশী কাৰ্প (ঘাঁহ কাৰ্প, ৰূপালী কাৰ্প, কমন কাৰ্প)"),
        ("catfish", "Catfish", "মাগুৰ জাতীয় মাছ (কেটফিছ)"),
        ("prawn", "Prawn", "চিংৰী"),
        ("other", "Other", "অন্যান্য"),
    ],
)
TYPE = choices("pond_tank", [("pond", "Pond", "পুখুৰী"), ("tank", "Tank", "টেংক")])

ID_REGEX = "regex(., '^\\S+$')"
ID_MSG = ("The ID must not be empty or contain spaces.", "আইডি খালী হ’ব নোৱাৰে আৰু তাত ফাঁক থাকিব নালাগে।")


def meta_start_end():
    return [Q("start", "start"), Q("end", "end")]


def unit_id_q(relevant=None):
    kw = dict(required="yes", constraint=ID_REGEX, msg=ID_MSG)
    if relevant:
        kw["relevant"] = relevant
    return Q(
        "text", "unit_id",
        "Unit ID (from the sampling frame)",
        "এককৰ আইডি (নমুনা তালিকাৰ পৰা)",
        **kw,
    )


def enumerator_q():
    return Q("text", "enumerator_id", "Enumerator ID", "গণকৰ আইডি", required="yes")


# ------------------------------------------------------------- 1. listing


def build_listing(ref_start, version):
    s = meta_start_end() + [
        Q("today", "today"),
        enumerator_q(),
        unit_id_q(),
        Q("select_one yesno", "consent",
          "Does the operator agree to take part in this survey? (Read the consent statement first.)",
          "পৰিচালকে এই জৰিপত অংশগ্ৰহণ কৰিবলৈ সন্মত হৈছেনে? (প্ৰথমে সন্মতিৰ বক্তব্য পঢ়ি শুনাওক।)",
          required="yes"),
        note("note_no_consent",
             "Consent refused. Thank the operator. The interview ends here. Submit the form.",
             "সন্মতি নাপালে। পৰিচালকক ধন্যবাদ দিয়ক। সাক্ষাৎকাৰ ইয়াতে শেষ। ফৰ্মটো জমা দিয়ক।",
             relevant="${consent} = 'no'"),
        begin("g_listing", "Listing details", "তালিকাভুক্তিৰ তথ্য", relevant="${consent} = 'yes'"),
        Q("text", "district", "District", "জিলা", required="yes"),
        Q("text", "block", "Block", "ব্লক", required="yes"),
        Q("text", "village", "Village", "গাঁও", required="yes"),
        Q("select_one pond_tank", "type", "Water body type", "জলাশয়ৰ ধৰণ", required="yes"),
        Q("decimal", "area_ha", "Water area as observed (hectares)", "চকুৰে দেখা পানীৰ ক্ষেত্ৰফল (হেক্টৰ)",
          required="yes", constraint=". > 0",
          msg=("Area must be more than 0.", "ক্ষেত্ৰফল ০তকৈ অধিক হ’ব লাগিব।"),
          hint=("1 hectare = 100 m x 100 m", "১ হেক্টৰ = ১০০ মিটাৰ x ১০০ মিটাৰ")),
        note("warn_area_large",
             "Warning: area is more than 20 ha. Check the value. If it is correct, continue.",
             "সতৰ্কবাণী: ক্ষেত্ৰফল ২০ হেক্টৰতকৈ অধিক। মান পৰীক্ষা কৰক। সঠিক হ’লে আগবাঢ়ক।",
             relevant="${area_ha} > 20"),
        Q("geopoint", "gps", "GPS location of the water body", "জলাশয়ৰ জিপিএছ অৱস্থান"),
        Q("text", "operator_name", "Operator name", "পৰিচালকৰ নাম", required="yes"),
        Q("text", "operator_phone", "Operator phone number", "পৰিচালকৰ ফোন নম্বৰ"),
        note("warn_phone",
             "Warning: the phone number should have 10 digits. Check it. If it is correct, continue.",
             "সতৰ্কবাণী: ফোন নম্বৰত ১০টা অংক থাকিব লাগে। পৰীক্ষা কৰক। সঠিক হ’লে আগবাঢ়ক।",
             relevant="string-length(${operator_phone}) > 0 and not(regex(${operator_phone}, '^[0-9]{10}$'))"),
        Q("select_multiple species", "species_groups", "Species groups stocked this year",
          "এই বছৰ পোণা এৰা প্ৰজাতিৰ গোট", required="yes"),
        Q("text", "species_other", "Other species (name)", "অন্য প্ৰজাতি (নাম)",
          relevant="selected(${species_groups}, 'other')", required="yes"),
        Q("date", "stocking_date", "Stocking date", "পোণা এৰাৰ তাৰিখ", required="yes",
          constraint=". <= today()",
          msg=("The date cannot be in the future.", "তাৰিখ ভৱিষ্যতৰ হ’ব নোৱাৰে।")),
        Q("integer", "seed_qty", "Seed quantity stocked (number of fish)", "এৰা পোণাৰ পৰিমাণ (মাছৰ সংখ্যা)",
          required="yes", constraint=". >= 0",
          msg=("The number cannot be negative.", "সংখ্যা ঋণাত্মক হ’ব নোৱাৰে।")),
        Q("select_one feeding", "feeding_practice", "Feeding practice", "খাদ্য প্ৰদানৰ পদ্ধতি", required="yes"),
        Q("select_one yesno", "phase2_flag", "Phase-2 (verified) unit?", "দ্বিতীয় পৰ্যায়ৰ (সত্যাপিত) এককনে?",
          hint=("Fill from the sampling list. Ask the supervisor if unsure.",
                "নমুনা তালিকাৰ পৰা পূৰ কৰক। সন্দেহ হ’লে পৰ্যবেক্ষকক সোধক।")),
        end(),
    ]
    c = (YESNO + SPECIES + TYPE
         + choices("feeding", [
             ("none", "None", "নাই"),
             ("supplementary", "Supplementary feed", "অতিৰিক্ত খাদ্য"),
             ("formulated", "Formulated feed", "প্ৰস্তুত কৰা খাদ্য (ফৰ্মুলেটেড)"),
         ]))
    return s, c, settings_row("d32_listing", "D-32 Listing schedule", version)


# ---------------------------------------------------------- 2. harvest diary


def build_harvest(ref_start, version):
    date_c = f". <= today() and . >= date('{ref_start}')"
    sum_expr = ("(${in_kg_sold} + ${in_kg_home} + ${in_kg_gift} + ${in_kg_labour} + .)")
    s = [
        Q("calculate", "event_id", calculation="once(uuid())"),
        unit_id_q(),
        Q("date", "harvest_date", "Harvest date", "মাছ ধৰা তাৰিখ", required="yes",
          constraint=date_c,
          msg=(f"The date cannot be in the future or before {ref_start}.",
               f"তাৰিখ ভৱিষ্যতৰ বা {ref_start}ৰ আগৰ হ’ব নোৱাৰে।")),
        Q("select_one harvest_type", "harvest_type", "Harvest type", "মাছ ধৰাৰ ধৰণ", required="yes"),
        Q("select_one species_h", "species_group", "Which fish?", "কোনটো মাছ?", required="yes"),
        Q("decimal", "quantity_kg", "Total fish harvested (kg)", "মুঠ ধৰা মাছ (কেজি)", required="yes",
          constraint=". > 0",
          msg=("The quantity must be more than 0 kg.", "পৰিমাণ ০ কেজিতকৈ অধিক হ’ব লাগিব।")),
        note("warn_qty_large",
             "Warning: more than 2000 kg in one harvest. Check the value. If it is correct, continue.",
             "সতৰ্কবাণী: এবাৰতে ২০০০ কেজিতকৈ অধিক। মান পৰীক্ষা কৰক। সঠিক হ’লে আগবাঢ়ক।",
             relevant="${quantity_kg} > 2000"),
        Q("select_one disposal_mode", "disposal_mode", "What happened to the fish?", "মাছবোৰ কি কৰা হ’ল?",
          required="yes"),
        begin("g_split", "Split of the harvest (kg)", "মাছৰ ভাগ (কেজি)", relevant="${disposal_mode} = 'split'"),
        Q("decimal", "in_kg_sold", "Sold (kg)", "বিক্ৰী কৰা (কেজি)", required="yes", default="0",
          constraint=". >= 0", msg=("Cannot be negative.", "ঋণাত্মক হ’ব নোৱাৰে।")),
        Q("decimal", "in_kg_home", "Used at home (kg)", "ঘৰুৱা ব্যৱহাৰ (কেজি)", required="yes", default="0",
          constraint=". >= 0", msg=("Cannot be negative.", "ঋণাত্মক হ’ব নোৱাৰে।")),
        Q("decimal", "in_kg_gift", "Given as gift (kg)", "উপহাৰ দিয়া (কেজি)", required="yes", default="0",
          constraint=". >= 0", msg=("Cannot be negative.", "ঋণাত্মক হ’ব নোৱাৰে।")),
        Q("decimal", "in_kg_labour", "Given to labour (kg)", "শ্ৰমিকক দিয়া (কেজি)", required="yes", default="0",
          constraint=". >= 0", msg=("Cannot be negative.", "ঋণাত্মক হ’ব নোৱাৰে।")),
        Q("decimal", "in_kg_other", "Other use (kg)", "অন্য ব্যৱহাৰ (কেজি)", required="yes", default="0",
          constraint=f". >= 0 and abs({sum_expr} - ${{quantity_kg}}) <= 1",
          msg=("The parts must add up to the total harvest (difference of 1 kg is allowed).",
               "অংশবোৰৰ যোগফল মুঠ ধৰা মাছৰ সৈতে সমান হ’ব লাগিব (১ কেজিলৈ পাৰ্থক্য গ্ৰহণযোগ্য)।")),
        end(),
        Q("calculate", "kg_sold", calculation=(
            "if(${disposal_mode} = 'all_sold', ${quantity_kg}, if(${disposal_mode} = 'split', ${in_kg_sold}, 0))")),
        Q("calculate", "kg_home", calculation=(
            "if(${disposal_mode} = 'all_home', ${quantity_kg}, if(${disposal_mode} = 'split', ${in_kg_home}, 0))")),
        Q("calculate", "kg_gift", calculation="if(${disposal_mode} = 'split', ${in_kg_gift}, 0)"),
        Q("calculate", "kg_labour", calculation="if(${disposal_mode} = 'split', ${in_kg_labour}, 0)"),
        Q("calculate", "kg_other", calculation="if(${disposal_mode} = 'split', ${in_kg_other}, 0)"),
        Q("decimal", "price_per_kg", "Price per kg (rupees). Leave empty if not known.",
          "প্ৰতি কেজিৰ দাম (টকা)। নাজানিলে খালী ৰাখক।",
          relevant="${kg_sold} > 0", constraint=". >= 0",
          msg=("The price cannot be negative.", "দাম ঋণাত্মক হ’ব নোৱাৰে।")),
        begin("g_recorder", "For enumerator or helper", "গণক বা সহায়কৰ বাবে"),
        Q("select_one source", "source", "Source of this record", "এই তথ্যৰ উৎস", required="yes", default="diary"),
        Q("select_one recorder", "recorder", "Who filled this form?", "ফৰ্মটো কোনে পূৰণ কৰিলে?",
          required="yes", default="farmer"),
        Q("geopoint", "gps", "GPS location (optional)", "জিপিএছ অৱস্থান (ঐচ্ছিক)"),
        end(),
        Q("calculate", "device_time", calculation="now()"),
        note("note_event_code", "Event code: ${event_id}", "ঘটনাৰ ক'ড: ${event_id}"),
    ]
    c = (choices("harvest_type", [("partial", "Partial harvest", "আংশিক মাছ ধৰা"),
                                  ("final", "Final (drain) harvest", "সম্পূৰ্ণ (শেষ) মাছ ধৰা")])
         + choices("species_h", [
             ("imc", "Indian major carps (rohu, catla, mrigal)", "ভাৰতীয় প্ৰধান কাৰ্প (ৰুই, কাতলা, মৃগেল)"),
             ("exotic", "Exotic carps (grass, silver, common carp)", "বিদেশী কাৰ্প (ঘাঁহ কাৰ্প, ৰূপালী কাৰ্প, কমন কাৰ্প)"),
             ("catfish", "Catfish", "মাগুৰ জাতীয় মাছ (কেটফিছ)"),
             ("prawn", "Prawn", "চিংৰী"),
             ("mixed", "Mixed groups", "মিশ্ৰিত প্ৰজাতি"),
             ("other", "Other", "অন্যান্য"),
         ])
         + choices("disposal_mode", [
             ("all_sold", "All sold", "সকলো বিক্ৰী কৰা হ’ল"),
             ("all_home", "All used at home", "সকলো ঘৰতে ব্যৱহাৰ কৰা হ’ল"),
             ("split", "Divided in parts", "কিছু ভাগত ভাগ কৰা হ’ল"),
         ])
         + choices("source", [
             ("diary", "Diary", "ডায়েৰী"),
             ("monthly_check", "Monthly check", "মাহেকীয়া পৰীক্ষা"),
             ("verified", "Verified by enumerator", "গণকে সত্যাপিত কৰা"),
             ("recall", "Recall", "স্মৃতিৰ পৰা"),
         ])
         + choices("recorder", [
             ("farmer", "Farmer", "খেতিয়ক"),
             ("helper", "Helper", "সহায়ক"),
             ("enumerator", "Enumerator", "গণক"),
         ]))
    return s, c, settings_row("d32_harvest_diary", "D-32 Harvest diary", version)


# ---------------------------------------------------------- 3. verification


def build_verification(ref_start, version):
    s = meta_start_end() + [
        Q("today", "today"),
        enumerator_q(),
        Q("barcode", "event_id_scan", "Scan the event code from the diary (optional)",
          "ডায়েৰীৰ ঘটনা ক'ড স্কেন কৰক (ঐচ্ছিক)"),
        Q("text", "event_id_typed", "Type the event code from the diary", "ডায়েৰীৰ ঘটনা ক'ড টাইপ কৰক",
          relevant="${event_id_scan} = ''", required="yes"),
        Q("calculate", "event_id", calculation="if(${event_id_scan} != '', ${event_id_scan}, ${event_id_typed})"),
        note("warn_event_id",
             "Warning: an event code usually has 36 characters. Check the code against the diary.",
             "সতৰ্কবাণী: ঘটনা ক'ডত সাধাৰণতে ৩৬টা আখৰ থাকে। ডায়েৰীৰ সৈতে মিলাই চাওক।",
             relevant="string-length(${event_id}) > 0 and string-length(${event_id}) != 36"),
        unit_id_q(),
        Q("text", "scale_id", "Scale ID", "তুলাচনীৰ আইডি", required="yes"),
        Q("date", "scale_calibration_date", "Last calibration date of the scale", "তুলাচনীৰ শেহতীয়া কেলিব্ৰেচনৰ তাৰিখ",
          required="yes", constraint=". <= today()",
          msg=("The date cannot be in the future.", "তাৰিখ ভৱিষ্যতৰ হ’ব নোৱাৰে।")),
        note("warn_calibration_old",
             "Warning: the last calibration is more than 12 months ago. Note this in the remarks.",
             "সতৰ্কবাণী: শেহতীয়া কেলিব্ৰেচন ১২ মাহতকৈ অধিক আগৰ। মন্তব্যত লিখি থওক।",
             relevant="${scale_calibration_date} != '' and (today() - ${scale_calibration_date}) > 365"),
        Q("select_one vmethod", "method", "How was the catch measured?", "মাছৰ ওজন কেনেকৈ ল’লে?", required="yes"),
        begin("g_weighed", "Weighed", "ওজন কৰা", relevant="${method} = 'weighed'"),
        Q("decimal", "weighed_kg", "Weighed quantity (kg)", "ওজন কৰা পৰিমাণ (কেজি)", required="yes",
          constraint=". > 0", msg=("The quantity must be more than 0 kg.", "পৰিমাণ ০ কেজিতকৈ অধিক হ’ব লাগিব।")),
        Q("image", "scale_photo", "Photo of the scale reading", "তুলাচনীৰ পাঠৰ ফটো", required="yes",
          appearance="new", parameters="max-pixels=1024"),
        end(),
        begin("g_crates", "Crate count", "ক্ৰেট গণনা", relevant="${method} = 'crates'"),
        Q("integer", "crate_count", "Number of crates", "ক্ৰেটৰ সংখ্যা", required="yes", constraint=". > 0",
          msg=("There must be at least 1 crate.", "কমেও ১টা ক্ৰেট থাকিব লাগিব।")),
        Q("decimal", "kg_per_crate", "Weight of one full crate (kg, with the crate)",
          "এটা ভৰ্তি ক্ৰেটৰ ওজন (কেজি, ক্ৰেটসহ)", required="yes", constraint=". > 0",
          msg=("The weight must be more than 0 kg.", "ওজন ০ কেজিতকৈ অধিক হ’ব লাগিব।")),
        Q("decimal", "tare_kg", "Weight of one empty crate (tare, kg)", "এটা খালী ক্ৰেটৰ ওজন (কেজি)",
          required="yes", constraint=". >= 0 and . < ${kg_per_crate}",
          msg=("The tare must be 0 or more, and less than the full crate weight.",
               "খালী ক্ৰেটৰ ওজন ০ বা অধিক আৰু ভৰ্তি ক্ৰেটতকৈ কম হ’ব লাগিব।")),
        Q("calculate", "crate_net_kg", calculation="${crate_count} * (${kg_per_crate} - ${tare_kg})"),
        note("note_crate_net", "Fish weight from crates: ${crate_net_kg} kg", "ক্ৰেটৰ পৰা মাছৰ ওজন: ${crate_net_kg} কেজি"),
        end(),
        Q("calculate", "verified_kg",
          calculation="if(${method} = 'weighed', ${weighed_kg}, if(${method} = 'crates', ${crate_net_kg}, ''))"),
        Q("decimal", "farmer_stated_kg", "Quantity stated by the farmer (kg)", "খেতিয়কে কোৱা পৰিমাণ (কেজি)",
          required="yes", constraint=". > 0",
          msg=("The quantity must be more than 0 kg.", "পৰিমাণ ০ কেজিতকৈ অধিক হ’ব লাগিব।"),
          hint=("Ask before showing the weighed value.", "ওজন দেখুওৱাৰ আগতে সোধক।")),
        Q("calculate", "rel_diff",
          calculation="if(${verified_kg} > 0, abs(${farmer_stated_kg} - ${verified_kg}) div ${verified_kg}, '')"),
        note("warn_rel_diff",
             "Warning: the farmer's quantity differs from the verified quantity by more than 50% "
             "(difference: ${rel_diff_pct}%). This is only a flag. Record the true weight. Add a note.",
             "সতৰ্কবাণী: খেতিয়কৰ পৰিমাণ সত্যাপিত পৰিমাণতকৈ ৫০%ৰো অধিক পৃথক (পাৰ্থক্য: ${rel_diff_pct}%)। "
             "এয়া কেৱল সংকেত। প্ৰকৃত ওজন লিখক। মন্তব্য যোগ কৰক।",
             relevant="${rel_diff} > 0.5"),
        Q("geopoint", "gps", "GPS location", "জিপিএছ অৱস্থান"),
        Q("text", "notes", "Notes", "মন্তব্য", appearance="multiline"),
    ]
    # rel_diff_pct must exist before the note that uses it: insert after rel_diff
    idx = next(i for i, r in enumerate(s) if r.get("name") == "rel_diff")
    s.insert(idx + 1, Q("calculate", "rel_diff_pct", calculation="if(${rel_diff} != '', round(${rel_diff} * 100, 0), '')"))
    c = (choices("vmethod", [("weighed", "Weighed on a scale", "তুলাচনীত ওজন কৰা"),
                             ("crates", "Crate count with tare", "ক্ৰেট গণনা (খালী ক্ৰেটৰ ওজনসহ)")]))
    return s, c, settings_row("d32_verification", "D-32 Verification at harvest", version)


# --------------------------------------------------------------- 4. recall


def build_recall(ref_start, version):
    s = meta_start_end() + [
        Q("today", "today"),
        enumerator_q(),
        Q("select_one yesno", "on_list", "Is this unit on the sampling list?", "এই এককটো নমুনা তালিকাত আছেনে?",
          required="yes"),
        unit_id_q(relevant="${on_list} = 'yes'"),
        begin("g_notonlist", "Unit not on the list", "তালিকাত নথকা একক", relevant="${on_list} = 'no'"),
        Q("calculate", "provisional_id", calculation="once(concat('NOL-', substr(uuid(), 0, 8)))"),
        note("note_prov_id", "Provisional ID of this unit: ${provisional_id}",
             "এই এককৰ অস্থায়ী আইডি: ${provisional_id}"),
        Q("text", "area_cell_id", "Area cell ID", "এলাকা কোষৰ আইডি", required="yes"),
        Q("geopoint", "gps", "GPS location of the water body", "জলাশয়ৰ জিপিএছ অৱস্থান", required="yes"),
        Q("decimal", "area_ha", "Water area (hectares)", "পানীৰ ক্ষেত্ৰফল (হেক্টৰ)", required="yes",
          constraint=". > 0", msg=("Area must be more than 0.", "ক্ষেত্ৰফল ০তকৈ অধিক হ’ব লাগিব।")),
        note("warn_area_large",
             "Warning: area is more than 20 ha. Check the value. If it is correct, continue.",
             "সতৰ্কবাণী: ক্ষেত্ৰফল ২০ হেক্টৰতকৈ অধিক। মান পৰীক্ষা কৰক। সঠিক হ’লে আগবাঢ়ক।",
             relevant="${area_ha} > 20"),
        end(),
        Q("calculate", "unit_key",
          calculation="if(${on_list} = 'yes', ${unit_id}, ${provisional_id})"),
        Q("decimal", "total_harvest_kg", "Total harvest last year (kg)", "যোৱা বছৰৰ মুঠ উৎপাদন (কেজি)",
          required="yes", constraint=". >= 0",
          msg=("The quantity cannot be negative. Enter 0 if there was no harvest.",
               "পৰিমাণ ঋণাত্মক হ’ব নোৱাৰে। উৎপাদন নহ’লে ০ লিখক।"),
          hint=(f"Reference year starts {ref_start}.", f"প্ৰসংগ বছৰ {ref_start}ৰ পৰা আৰম্ভ।")),
        Q("integer", "n_harvests", "Number of harvests last year", "যোৱা বছৰ মাছ ধৰাৰ সংখ্যা",
          required="yes", constraint=". >= 0",
          msg=("The number cannot be negative.", "সংখ্যা ঋণাত্মক হ’ব নোৱাৰে।")),
        note("warn_harvests_zero",
             "Warning: total harvest is above 0 but the number of harvests is 0. Check both values.",
             "সতৰ্কবাণী: মুঠ উৎপাদন ০তকৈ অধিক কিন্তু মাছ ধৰাৰ সংখ্যা ০। দুয়োটা মান পৰীক্ষা কৰক।",
             relevant="${total_harvest_kg} > 0 and ${n_harvests} = 0"),
        Q("integer", "share_self_consumed_pct", "Share eaten or used by the household (percent, 0 to 100)",
          "পৰিয়ালে খোৱা বা ব্যৱহাৰ কৰা অংশ (শতাংশ, ০ ৰ পৰা ১০০)", required="yes",
          constraint=". >= 0 and . <= 100",
          msg=("Enter a number from 0 to 100.", "০ ৰ পৰা ১০০ ৰ ভিতৰত এটা সংখ্যা লিখক।")),
        Q("select_one yesno", "diary_completed", "Did the farmer complete the diary for the whole year?",
          "খেতিয়কে সম্পূৰ্ণ বছৰ ডায়েৰী পূৰণ কৰিছিলনে?", required="yes", relevant="${on_list} = 'yes'"),
        Q("select_one dropout_reason", "dropout_reason", "Main reason the diary was not completed",
          "ডায়েৰী সম্পূৰ্ণ নোহোৱাৰ মূল কাৰণ", required="yes",
          relevant="${on_list} = 'yes' and ${diary_completed} = 'no'"),
        Q("text", "dropout_reason_other", "Other reason (write)", "অন্য কাৰণ (লিখক)", required="yes",
          relevant="${dropout_reason} = 'other'"),
        Q("text", "notes", "Notes", "মন্তব্য", appearance="multiline"),
    ]
    c = (YESNO + choices("dropout_reason", [
        ("no_time", "No time", "সময় নাছিল"),
        ("difficult", "Form was difficult to use", "ফৰ্মটো ব্যৱহাৰ কৰাত অসুবিধা হ’ল"),
        ("phone", "Phone problem (lost, broken, no network)", "ফোনৰ সমস্যা (হেৰোৱা, ভঙা, নেটৱৰ্ক নাই)"),
        ("no_harvest", "No harvest happened, so nothing to record", "মাছ ধৰা নহ’ল, গতিকে লিখিবলৈ একো নাছিল"),
        ("lost_interest", "Lost interest", "আগ্ৰহ নাইকিয়া হ’ল"),
        ("sold_unit", "Unit sold or leased out", "জলাশয় বিক্ৰী বা ভাড়ালৈ দিয়া হ’ল"),
        ("other", "Other", "অন্যান্য"),
    ]))
    return s, c, settings_row("d32_recall", "D-32 End-of-year recall", version)


# ---------------------------------------------------------- 5. monthly check


def build_monthly(ref_start, version):
    s = meta_start_end() + [
        Q("today", "today"),
        enumerator_q(),
        unit_id_q(),
        Q("date", "month", "Month checked", "পৰীক্ষা কৰা মাহ", required="yes", appearance="month-year",
          constraint=f". >= date('{ref_start}') and . <= today()",
          msg=(f"The month cannot be in the future or before {ref_start}.",
               f"মাহ ভৱিষ্যতৰ বা {ref_start}ৰ আগৰ হ’ব নোৱাৰে।")),
        Q("select_one visit_mode", "visit_mode", "Visit or phone call?", "পৰিদৰ্শন নে ফোন কল?", required="yes"),
        Q("select_one yesno", "any_harvest", "Was there any harvest this month?", "এই মাহত মাছ ধৰা হৈছিলনে?",
          required="yes"),
        begin("g_harvest", "Harvest events", "মাছ ধৰাৰ ঘটনা", relevant="${any_harvest} = 'yes'"),
        Q("integer", "n_happened", "How many harvests happened this month?", "এই মাহত কিমানবাৰ মাছ ধৰা হৈছিল?",
          required="yes", constraint=". >= 1",
          msg=("Enter 1 or more.", "১ বা অধিক লিখক।")),
        Q("integer", "n_in_diary", "How many of these are in the diary?", "ইয়াৰে কিমানটা ডায়েৰীত লিখা আছে?",
          required="yes", constraint=". >= 0",
          msg=("The number cannot be negative.", "সংখ্যা ঋণাত্মক হ’ব নোৱাৰে।")),
        Q("calculate", "n_missing", calculation="${n_happened} - ${n_in_diary}"),
        note("warn_missing",
             "Warning: ${n_missing} harvest(s) are missing from the diary. Help the farmer add them.",
             "সতৰ্কবাণী: ${n_missing}টা মাছ ধৰাৰ ঘটনা ডায়েৰীত নাই। খেতিয়কক সেইবোৰ যোগ কৰাত সহায় কৰক।",
             relevant="${n_missing} > 0"),
        note("warn_extra",
             "Warning: the diary has more events than happened. Check for duplicates.",
             "সতৰ্কবাণী: ডায়েৰীত ঘটনাৰ সংখ্যা প্ৰকৃততকৈ অধিক। দুবাৰ লিখা হৈছে নেকি পৰীক্ষা কৰক।",
             relevant="${n_missing} < 0"),
        end(),
        Q("text", "notes", "Notes", "মন্তব্য", appearance="multiline"),
    ]
    c = (YESNO + choices("visit_mode", [("visit", "Visit", "পৰিদৰ্শন"), ("call", "Phone call", "ফোন কল")]))
    return s, c, settings_row("d32_monthly_check", "D-32 Monthly check", version)


BUILDERS = {
    "d32_listing": build_listing,
    "d32_harvest_diary": build_harvest,
    "d32_verification": build_verification,
    "d32_recall": build_recall,
    "d32_monthly_check": build_monthly,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref-year-start", default="2026-04-01",
                    help="First day of the reference year (assumption A1: 1 April). One parameter.")
    ap.add_argument("--version", default="2026-11-01", help="Form version, a date string.")
    args = ap.parse_args()
    for form_id, fn in BUILDERS.items():
        survey, ch, st = fn(args.ref_year_start, args.version)
        # drop any choice list not used by a select in the survey (keeps files clean)
        used = {r["type"].split()[1] for r in survey if r["type"].startswith(("select_one", "select_multiple"))}
        ch = [r for r in ch if r["list_name"] in used]
        path = OUT_DIR / f"{form_id}.xlsx"
        write_xlsx(path, survey, ch, st)
        print("wrote", path)


if __name__ == "__main__":
    main()
