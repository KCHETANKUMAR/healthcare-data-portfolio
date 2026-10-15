"""Streamlit front end for a fictional pharmacovigilance training simulator."""
from datetime import date
import pandas as pd
import streamlit as st
import database as db

db.initialize_database()
st.set_page_config(page_title="PV ICSR Simulator", page_icon="🧪", layout="wide")
st.title("Pharmacovigilance ICSR Case Processing Simulator")
st.error("Educational simulation only. Not for processing real safety reports or regulatory submission.")
st.info("Meeting minimum criteria does not mean every field is complete. Unknown details stay unknown; this is an educational simulation, not a validated regulatory system.")

PAGES = ["Dashboard", "New case", "Case management", "Follow-ups", "QC checklist"]
page = st.sidebar.radio("Navigate", PAGES)

def case_form(prefix: str, current: dict | None = None) -> dict:
    c = current or {}
    with st.form(prefix):
        cols = st.columns(2)
        choices = ["Unknown", "Yes", "No"]
        data = {}
        labels = [("patient_identifiable", "Patient identifiable"), ("reporter_identifiable", "Reporter identifiable"), ("product_identified", "Suspect product identified"), ("reaction_reported", "Suspected reaction reported")]
        for i, (key, label) in enumerate(labels):
            with cols[i % 2]: data[key] = st.selectbox(label, choices, index=choices.index(c.get(key, "Unknown")))
        data["event_description"] = st.text_area("Event description as reported *", value=c.get("event_description", ""), help="Preserve source wording; do not infer missing details.")
        a, b, d = st.columns(3)
        with a: data["patient_age"] = st.text_input("Patient age (optional)", c.get("patient_age", ""))
        with b: data["patient_sex"] = st.selectbox("Patient sex", ["Unknown", "Female", "Male", "Other / as reported"], index=["Unknown", "Female", "Male", "Other / as reported"].index(c.get("patient_sex", "Unknown")))
        with d: data["product_name"] = st.text_input("Suspect product name", c.get("product_name", ""))
        a, b = st.columns(2)
        with a: data["onset_date"] = st.date_input("Event onset date (if known)", value=date.fromisoformat(c["onset_date"]) if c.get("onset_date") else None)
        with b: data["received_date"] = st.date_input("Report received date *", value=date.fromisoformat(c["received_date"]) if c.get("received_date") else date.today())
        data["seriousness"] = st.text_input("Seriousness information", c.get("seriousness", ""), placeholder="Record source information; do not guess")
        data["outcome"] = st.text_input("Event outcome", c.get("outcome", ""))
        data["source_notes"] = st.text_area("Source notes", c.get("source_notes", ""))
        submitted = st.form_submit_button("Save case")
    data["onset_date"] = data["onset_date"].isoformat() if data["onset_date"] else ""
    data["received_date"] = data["received_date"].isoformat()
    if submitted:
        if not data["event_description"].strip(): st.error("Enter the event description as reported.")
        else: return data
    return {}

if page == "Dashboard":
    cases = db.get_cases()
    total = len(cases); meets = sum(c["validation_status"] == "Meets minimum criteria" for c in cases)
    open_count = sum(f["status"] == "Open" for c in cases for f in db.get_follow_ups(c["case_id"]))
    metrics = st.columns(4)
    for col, label, val in zip(metrics, ["Total cases", "Meet four criteria", "Do not yet meet", "Open follow-ups"], [total, meets, total-meets, open_count]): col.metric(label, val)
    if st.button("Insert fictional sample cases (once)"):
        n = db.insert_sample_data(); st.success(f"Added {n} fictional case(s). Existing sample IDs were skipped."); st.rerun()
    q = st.text_input("Search by case ID or product")
    shown = [c for c in cases if q.lower() in (c["case_id"] + " " + (c["product_name"] or "")).lower()]
    st.dataframe(pd.DataFrame([{k: c[k] for k in ("case_id", "product_name", "received_date", "validation_status", "follow_up_needed", "fictional")} for c in shown]), use_container_width=True, hide_index=True)
    st.caption("Fictional training data is labeled in the table. CSV export omits event narratives and source notes.")
    csv_rows = [{"data_label": "Simulated training data", **{k: c[k] for k in ("case_id", "product_name", "received_date", "validation_status", "follow_up_needed", "fictional")}} for c in cases]
    csv = pd.DataFrame(csv_rows, columns=["data_label", "case_id", "product_name", "received_date", "validation_status", "follow_up_needed", "fictional"]).to_csv(index=False).encode("utf-8")
    st.download_button("Export simulated training case list (CSV)", csv, "simulated_training_cases.csv", "text/csv")
elif page == "New case":
    st.subheader("Case intake")
    data = case_form("new_case")
    if data:
        existing = db.get_cases(); serial = max([int(c["case_id"].split("-")[-1]) for c in existing if c["case_id"].startswith("SIM-") and c["case_id"].split("-")[-1].isdigit()] + [0]) + 1
        data["case_id"] = f"SIM-{serial:04d}"
        try:
            db.create_case(data); st.success(f"Saved {data['case_id']}.")
            if not db.meets_minimum(data): st.warning("This case does not yet meet minimum criteria and is flagged for review/follow-up.")
        except Exception as e: st.error(f"Could not save case: {e}")
elif page == "Case management":
    cases = db.get_cases()
    query = st.text_input("Search case ID or product")
    validation = st.selectbox("Validation status", ["All", "Meets minimum criteria", "Does not yet meet minimum criteria"])
    follow = st.selectbox("Follow-up flag", ["All", "Needed", "Not needed"])
    rows = [c for c in cases if query.lower() in (c["case_id"] + " " + (c["product_name"] or "")).lower() and (validation == "All" or c["validation_status"] == validation) and (follow == "All" or bool(c["follow_up_needed"]) == (follow == "Needed"))]
    st.dataframe(pd.DataFrame([{k: c[k] for k in ("case_id", "product_name", "received_date", "validation_status", "follow_up_needed")} for c in rows]), use_container_width=True, hide_index=True)
    if rows:
        selected = st.selectbox("View or edit case", [c["case_id"] for c in rows]); chosen = db.get_case(selected)
        st.json(chosen)
        if chosen["validation_status"] != "Meets minimum criteria": st.warning("Missing criteria: " + ", ".join(k.replace("_", " ") for k in db.CASE_FIELDS if chosen[k] != "Yes"))
        edits = case_form("edit_" + selected, chosen)
        if edits:
            db.update_case(selected, edits); st.success("Case updated."); st.rerun()
elif page == "Follow-ups":
    cases = db.get_cases()
    if not cases: st.info("Add a case before recording a follow-up.")
    else:
        cid = st.selectbox("Case", [c["case_id"] for c in cases])
        with st.form("add_follow"):
            missing = st.text_input("Missing field *"); question = st.text_area("Follow-up question *"); raised = st.date_input("Date raised", value=date.today()); submitted = st.form_submit_button("Add follow-up")
        if submitted:
            if not missing.strip() or not question.strip(): st.error("Missing field and question are required.")
            else: db.add_follow_up(cid, {"missing_field": missing, "question": question, "date_raised": raised.isoformat()}); st.success("Follow-up saved."); st.rerun()
        for item in db.get_follow_ups(cid):
            with st.expander(f"#{item['id']} · {item['missing_field']} · {item['status']}"):
                st.write(item["question"])
                with st.form(f"fu_{item['id']}"):
                    response = st.text_input("Response received date (optional)", item["response_received"] or "")
                    notes = st.text_area("Response notes", item["response_notes"])
                    status = st.selectbox("Status", ["Open", "Answered", "Closed"], index=["Open", "Answered", "Closed"].index(item["status"]))
                    if st.form_submit_button("Save follow-up"):
                        db.update_follow_up(item["id"], {**item, "response_received": response, "response_notes": notes, "status": status}); st.success("Follow-up updated."); st.rerun()
elif page == "QC checklist":
    cases = db.get_cases()
    if not cases: st.info("Add a case before using the QC checklist.")
    else:
        cid = st.selectbox("Case", [c["case_id"] for c in cases]); current = db.get_qc(cid)
        labels = [("source_transcribed", "Source information transcribed accurately"), ("description_preserved", "Event description preserved"), ("criteria_reviewed", "Four minimum criteria reviewed"), ("facts_distinguished", "Known and unknown facts distinguished"), ("seriousness_checked", "Seriousness checked without guessing"), ("followup_reviewed", "Missing information and follow-up reviewed"), ("dates_checked", "Dates checked"), ("final_review", "Final QC review complete")]
        with st.form("qc"):
            vals = {key: st.checkbox(label, value=bool(current.get(key, 0))) for key, label in labels}
            if st.form_submit_button("Save QC progress"): db.save_qc(cid, vals); st.success("QC checklist saved.")
