"""
app.py
PawPal+ Streamlit UI — Phase 6 Step 1.
Reflects all algorithmic features in the UI:
  - Priority emoji color-coding
  - Chronological sort toggle
  - Conflict warnings via st.error / st.warning
  - Skipped task explanation
  - Utilization metric

Run with:
    streamlit run app.py
"""

import streamlit as st
from pawpal_system import (
    Owner,
    Pet,
    Task,
    Scheduler,
    ScheduleResult,
    Priority,
    Species,
)

# ─────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────
st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")
st.caption("Smart pet care scheduling.")

# ─────────────────────────────────────────────
# Priority color-coding helper
# ─────────────────────────────────────────────
PRIORITY_EMOJI = {
    "HIGH":   "🔴",
    "MEDIUM": "🟡",
    "LOW":    "🟢",
}

# ─────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────
if "owner" not in st.session_state:
    st.session_state.owner = None

# ─────────────────────────────────────────────
# Sidebar — Owner setup
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("👤 Owner Setup")

    owner_name  = st.text_input("Your name",               value="Jordan")
    avail_start = st.text_input("Available from (HH:MM)",  value="08:00")
    avail_end   = st.text_input("Available until (HH:MM)", value="20:00")

    if st.button("💾 Save Owner", use_container_width=True):
        if st.session_state.owner is None:
            st.session_state.owner = Owner(
                name=owner_name,
                available_start=avail_start,
                available_end=avail_end,
            )
        else:
            st.session_state.owner.name            = owner_name
            st.session_state.owner.available_start = avail_start
            st.session_state.owner.available_end   = avail_end
        st.success(f"Saved! Hello, {owner_name} 👋")

    if st.session_state.owner and st.session_state.owner.pets:
        st.divider()
        st.caption("Registered pets")
        for p in st.session_state.owner.pets:
            st.write(f"• {p.name} ({p.species.value}, {p.age_years}y)")

# ─────────────────────────────────────────────
# Guard
# ─────────────────────────────────────────────
if st.session_state.owner is None:
    st.info("👈 Fill in your name and availability in the sidebar, then click Save Owner.")
    st.stop()

owner: Owner = st.session_state.owner

# ─────────────────────────────────────────────
# Section 1 — Add a Pet
# ─────────────────────────────────────────────
st.subheader("🐾 Add a Pet")

with st.form("add_pet_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        pet_name    = st.text_input("Pet name", placeholder="Mochi")
    with col2:
        species_str = st.selectbox("Species", ["dog", "cat", "other"])
    with col3:
        pet_age     = st.number_input("Age (years)", min_value=0.0,
                                       max_value=30.0, value=1.0, step=0.5)

    submitted = st.form_submit_button("➕ Add Pet", use_container_width=True)

    if submitted:
        if not pet_name.strip():
            st.warning("Please enter a pet name.")
        else:
            existing_names = [p.name.lower() for p in owner.pets]
            if pet_name.strip().lower() in existing_names:
                st.warning(f"'{pet_name}' is already registered.")
            else:
                new_pet = Pet(
                    name=pet_name.strip(),
                    species=Species(species_str),
                    age_years=pet_age,
                )
                owner.add_pet(new_pet)
                st.success(f"Added {new_pet.name} ({species_str})!")

if owner.pets:
    st.markdown("**Registered pets**")
    rows = [
        {
            "Name":    p.name,
            "Species": p.species.value,
            "Age":     f"{p.age_years}y",
            "Tasks":   len(p.tasks),
            "Pending": len(p.pending_tasks()),
        }
        for p in owner.pets
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
else:
    st.info("No pets yet. Add one above.")

st.divider()

# ─────────────────────────────────────────────
# Section 2 — Add a Task
# ─────────────────────────────────────────────
st.subheader("📋 Add a Task")

if not owner.pets:
    st.warning("Add a pet first before adding tasks.")
else:
    with st.form("add_task_form", clear_on_submit=True):
        pet_names   = [p.name for p in owner.pets]
        target_name = st.selectbox("Assign to pet", pet_names)

        col1, col2, col3 = st.columns(3)
        with col1:
            task_title   = st.text_input("Task title", placeholder="Morning walk")
        with col2:
            duration     = st.number_input("Duration (min)", min_value=1,
                                            max_value=480, value=30)
        with col3:
            priority_str = st.selectbox("Priority", ["high", "medium", "low"])

        col4, col5 = st.columns(2)
        with col4:
            pref_time = st.selectbox(
                "Preferred time", ["(none)", "morning", "afternoon", "evening"]
            )
        with col5:
            recurring = st.checkbox("Recurring (repeats daily)")

        notes     = st.text_input("Notes (optional)", placeholder="e.g. Give with food")
        submitted = st.form_submit_button("➕ Add Task", use_container_width=True)

        if submitted:
            if not task_title.strip():
                st.warning("Please enter a task title.")
            else:
                target_pet = next(p for p in owner.pets if p.name == target_name)
                new_task   = Task(
                    title=task_title.strip(),
                    duration_minutes=int(duration),
                    priority=Priority.from_str(priority_str),
                    preferred_time=None if pref_time == "(none)" else pref_time,
                    recurring=recurring,
                    notes=notes.strip(),
                )
                target_pet.add_task(new_task)
                st.success(f"Added '{new_task.title}' to {target_name}!")

    # Show pending tasks with priority color-coding
    for pet in owner.pets:
        pending = pet.pending_tasks()
        if not pending:
            continue
        st.markdown(f"**{pet.name}** — {len(pending)} pending task(s)")
        rows = [
            {
                "":          PRIORITY_EMOJI[t.priority.name],
                "Task":      t.title,
                "Min":       t.duration_minutes,
                "Priority":  t.priority.name,
                "Time":      t.preferred_time or "—",
                "Recurring": "🔁" if t.recurring else "—",
                "Notes":     t.notes or "—",
            }
            for t in pending
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)

st.divider()

# ─────────────────────────────────────────────
# Section 3 — Generate Schedule
# ─────────────────────────────────────────────
st.subheader("🗓️ Generate Schedule")

all_pending = owner.all_pending_tasks()

if not all_pending:
    st.info("Add at least one task before generating a schedule.")
else:
    # Sort mode toggle — surfaces sort_by_time() to the user
    sort_mode = st.radio(
        "Display order",
        ["Priority (default)", "Chronological"],
        horizontal=True,
    )

    if st.button("⚡ Build Today's Schedule", use_container_width=True):
        scheduler = Scheduler(owner)
        result    = scheduler.build_schedule()

        # ── Metrics ──────────────────────────────────────────────────────
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Scheduled",   len(result.scheduled))
        col2.metric("Skipped",     len(result.skipped))
        col3.metric("Time used",   f"{result.total_minutes} min")
        col4.metric("Utilization", f"{result.utilization_pct}%")

        # ── Conflict warnings — surfaced via st.error + st.warning ───────
        if result.conflicts:
            st.error("⚠️ Scheduling conflicts detected:")
            for warning in result.conflicts:
                st.warning(warning)
        else:
            st.success("✅ No conflicts — schedule is clean.")

        # ── Scheduled tasks with sort toggle ─────────────────────────────
        if result.scheduled:
            display = (
                Scheduler.sort_by_time(result.scheduled)
                if sort_mode == "Chronological"
                else result.scheduled
            )
            st.markdown("**Scheduled tasks**")
            rows = [
                {
                    "":         PRIORITY_EMOJI[t.priority.name],
                    "Start":    t.scheduled_start.strftime("%I:%M %p"),
                    "End":      t.scheduled_end.strftime("%I:%M %p"),
                    "Task":     t.title,
                    "Priority": t.priority.name,
                    "Min":      t.duration_minutes,
                    "Notes":    t.notes or "—",
                }
                for t in display
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)

        # ── Skipped tasks with explanation ────────────────────────────────
        if result.skipped:
            st.warning(
                f"{len(result.skipped)} task(s) were skipped because they "
                f"didn't fit within your {owner.available_start}–"
                f"{owner.available_end} window:"
            )
            for t in result.skipped:
                st.write(
                    f"  {PRIORITY_EMOJI[t.priority.name]} {t.title} "
                    f"({t.duration_minutes} min, {t.priority.name})"
                )

        # ── Plain-text export ─────────────────────────────────────────────
        with st.expander("📄 Plain-text summary (copy for README)"):
            st.code(Scheduler.explain(result), language="text")

st.divider()

# ─────────────────────────────────────────────
# Section 4 — Mark Tasks Done
# ─────────────────────────────────────────────
st.subheader("✅ Mark Tasks Done")
st.caption("Recurring tasks automatically generate tomorrow's occurrence.")

if not owner.pets:
    st.info("No pets registered yet.")
else:
    pet_options   = ["All pets"] + [p.name for p in owner.pets]
    filter_choice = st.selectbox("Show tasks for", pet_options, key="done_filter")

    pairs: list[tuple] = []
    for pet in owner.pets:
        if filter_choice != "All pets" and pet.name != filter_choice:
            continue
        for task in pet.pending_tasks():
            pairs.append((pet, task))

    if not pairs:
        st.info("No pending tasks. Add some in the section above.")
    else:
        for pet, task in pairs:
            col_info, col_btn = st.columns([5, 1])

            with col_info:
                recurring_badge = " 🔁" if task.recurring else ""
                st.write(
                    f"{PRIORITY_EMOJI[task.priority.name]} "
                    f"**{task.title}**{recurring_badge} "
                    f"— {pet.name}, {task.duration_minutes} min"
                )
                if task.notes:
                    st.caption(f"📝 {task.notes}")

            with col_btn:
                if st.button("Done", key=f"done_{task.task_id}"):
                    next_task = Scheduler.complete_and_recur(task, pet)
                    if next_task and next_task.scheduled_start:
                        next_date = next_task.scheduled_start.strftime("%A, %b %d")
                        st.success(
                            f"✅ Done! Next '{task.title}' queued for {next_date}."
                        )
                    else:
                        st.success(f"✅ '{task.title}' marked complete.")
                    st.rerun()