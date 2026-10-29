
from pyscript import document
from js import localStorage, JSON, window
from pyodide.ffi import create_proxy, to_js
from datetime import date
import json
import uuid

tasks = []
subjects = []
study_sessions = []
event_proxies = []

# ---------- SAVE AND LOAD ----------

def save_data():
    data = {
        "tasks": tasks,
        "subjects": subjects,
        "sessions": study_sessions
    }
    localStorage.setItem("exammate_dashboard", JSON.stringify(to_js(data)))


def update_study_charts():
    if hasattr(window, "updateStudyCharts"):
        window.updateStudyCharts(json.dumps(tasks, ensure_ascii=False))


def update_subject_countdowns():
    if hasattr(window, "renderSubjectCountdowns"):
        window.renderSubjectCountdowns(json.dumps(subjects, ensure_ascii=False))


def load_data():
    global tasks, subjects, study_sessions

    try:
        saved = localStorage.getItem("exammate_dashboard")

        if saved:
            data = JSON.parse(saved).to_py()
            tasks = data.get("tasks", [])
            subjects = data.get("subjects", [])
            study_sessions = data.get("sessions", [])

    except Exception as error:
        print("Data loading error:", error)


# ---------- SAFE HTML HELPERS ----------

def get_element(element_id):
    return document.getElementById(element_id)


def set_text(element_id, text):
    element = get_element(element_id)
    if element:
        element.innerText = str(text)


def show_message(text):
    set_text("taskMessage", text)


# ---------- DAILY TASKS ----------

def add_task(event):
    name_element = get_element("taskName")
    minutes_element = get_element("taskMinutes")
    outcome_element = get_element("taskOutcome")

    name = name_element.value.strip()
    outcome = outcome_element.value.strip() if outcome_element else ""
    minutes_text = minutes_element.value

    if not name:
        show_message("Please enter a task name.")
        return

    try:
        minutes = int(minutes_text)
        if minutes < 5:
            show_message("Study time must be at least 5 minutes.")
            return
    except (ValueError, TypeError):
        show_message("Please enter valid study minutes.")
        return

    tasks.append({
        "id": str(uuid.uuid4()),
        "name": name,
        "minutes": minutes,
        "done": False,
        "day": date.today().isoformat(),
        "outcome": outcome
    })

    save_data()
    name_element.value = ""
    if outcome_element:
        outcome_element.value = ""
    minutes_element.value = "30"

    render_tasks()
    update_analytics()
    show_message("Task added successfully!")


def toggle_task(task_id):
    for task in tasks:
        if task["id"] == task_id:
            task["done"] = not task["done"]
            break

    save_data()
    render_tasks()
    update_analytics()


def delete_task(task_id):
    global tasks
    tasks = [task for task in tasks if task["id"] != task_id]

    save_data()
    render_tasks()
    update_analytics()
    show_message("Task deleted.")


def handle_task_list_click(event):
    button = event.target.closest("button[data-task-id]")
    if not button:
        return

    task_id = button.getAttribute("data-task-id")
    if button.classList.contains("delete-task"):
        delete_task(task_id)
    else:
        toggle_task(task_id)


def handle_plan_result_click(event):
    button = event.target.closest("button.add-plan-tasks")
    if button:
        add_plan_tasks(button)


def handle_subject_countdown_click(event):
    button = event.target.closest("button[data-subject-id]")
    if not button:
        return

    subject_id = button.getAttribute("data-subject-id")
    remaining = [subject for subject in subjects if subject.get("id") != subject_id]
    if len(remaining) == len(subjects):
        return

    subjects[:] = remaining
    save_data()
    update_subject_countdowns()


def render_tasks():
    box = get_element("taskList")
    if not box:
        return

    box.innerHTML = ""

    today = date.today().isoformat()
    today_tasks = [task for task in tasks if task.get("day") == today]

    if not today_tasks:
        empty_state = document.createElement("div")
        empty_state.className = "empty-state"
        empty_state.innerText = "Your list is clear. Add a task to get started."
        box.appendChild(empty_state)
        return

    for task in today_tasks:
        card = document.createElement("div")
        card.className = "task-item" + (" is-done" if task["done"] else "")

        status_icon = document.createElement("span")
        status_icon.className = "task-status-icon"
        status_icon.innerText = "✓"
        card.appendChild(status_icon)

        copy = document.createElement("div")
        copy.className = "task-copy"
        title_text = document.createElement("strong")
        title_text.innerText = task["name"]
        copy.appendChild(title_text)

        info_text = document.createElement("small")
        info_text.innerText = str(task["minutes"]) + " min · " + (
            "Completed" if task["done"] else "Ready when you are"
        )
        copy.appendChild(info_text)
        outcome = task.get("outcome", "").strip()
        if outcome:
            outcome_text = document.createElement("small")
            outcome_text.className = "task-outcome"
            outcome_text.innerText = "Outcome: " + outcome
            copy.appendChild(outcome_text)
        card.appendChild(copy)

        actions = document.createElement("div")
        actions.className = "task-actions"
        complete_btn = document.createElement("button")
        complete_btn.innerText = "Undo" if task["done"] else "Done"
        complete_btn.setAttribute("aria-label", (
            "Mark " + task["name"] + " as pending" if task["done"]
            else "Mark " + task["name"] + " as complete"
        ))
        complete_btn.setAttribute("data-task-id", task["id"])
        actions.appendChild(complete_btn)

        delete_btn = document.createElement("button")
        delete_btn.className = "delete-task"
        delete_btn.innerText = "×"
        delete_btn.setAttribute("aria-label", "Delete " + task["name"])
        delete_btn.setAttribute("data-task-id", task["id"])
        actions.appendChild(delete_btn)
        card.appendChild(actions)

        box.appendChild(card)


# ---------- AUTOMATIC STUDY PLANNER ----------

def greedy_daily_topic_target(topic_count, days_left):
    study_days = max(1, days_left)
    return max(1, (topic_count + study_days - 1) // study_days)


def generate_plan(event):
    subject_element = get_element("subjectName")
    topics_element = get_element("topics")
    hours_element = get_element("hours")
    date_element = get_element("plannerDate")
    outcome_element = get_element("plannerOutcome")
    result = get_element("planResult")

    name = subject_element.value.strip()
    exam_date = date_element.value
    outcome = outcome_element.value.strip() if outcome_element else ""

    try:
        topic_count = int(topics_element.value)
        hours = float(hours_element.value)
    except (ValueError, TypeError):
        result.innerText = "Enter valid topics and study hours."
        return

    if not name or not exam_date:
        result.innerText = "Enter the subject name and exam date."
        return

    if topic_count < 1 or hours <= 0 or hours > 16:
        result.innerText = "Use at least 1 topic and 0–16 study hours."
        return

    try:
        exam_day = date.fromisoformat(exam_date)
    except ValueError:
        result.innerText = "Please select a valid exam date."
        return

    today = date.today()
    days_left = (exam_day - today).days

    if days_left < 0:
        result.innerText = "This exam date has already passed."
        return

    save_subject_exam(name, exam_date, topic_count)

    result.innerHTML = ""

    heading = document.createElement("h3")
    heading.innerText = name + " — Your Study Plan"
    result.appendChild(heading)

    summary = document.createElement("p")
    summary.innerText = (
        str(days_left) + " days until the exam | "
        + str(topic_count) + " topics | "
        + str(hours) + " hours available today"
    )
    result.appendChild(summary)

    if outcome:
        outcome_note = document.createElement("p")
        outcome_note.innerText = "Learning outcome: " + outcome
        result.appendChild(outcome_note)

    if days_left == 0:
        per_day = topic_count
        info_text = "Exam is today. Prioritize revision and important topics."
    else:
        per_day = greedy_daily_topic_target(topic_count, days_left)
        info_text = (
            "Greedy target: focus on about " + str(per_day)
            + " topic(s) today to spread the remaining work across "
            + str(days_left) + " study day(s)."
        )

    note = document.createElement("p")
    note.innerText = info_text
    result.appendChild(note)

    heading2 = document.createElement("h3")
    heading2.innerText = "Today's timetable"
    result.appendChild(heading2)

    total_minutes = int(hours * 60)
    session_count = min(per_day, max(1, total_minutes // 30))
    session_length = total_minutes // session_count

    for i in range(session_count):
        line = document.createElement("p")
        line.innerText = (
            "Session " + str(i + 1) + ": Topic " + str(i + 1)
            + " — " + str(session_length) + " minutes"
        )
        result.appendChild(line)

    add_plan_btn = document.createElement("button")
    add_plan_btn.className = "add-plan-tasks"
    add_plan_btn.innerText = "Add Today's Sessions as Tasks"
    add_plan_btn.setAttribute("data-subject", name)
    add_plan_btn.setAttribute("data-count", str(session_count))
    add_plan_btn.setAttribute("data-minutes", str(session_length))
    add_plan_btn.setAttribute("data-outcome", outcome)
    result.appendChild(add_plan_btn)


def save_subject_exam(name, exam_date, topic_count):
    subject_key = name.casefold()
    for subject in subjects:
        if subject.get("name", "").strip().casefold() == subject_key:
            subject["name"] = name
            subject["exam_date"] = exam_date
            subject["topics"] = topic_count
            save_data()
            update_subject_countdowns()
            return

    subjects.append({
        "id": str(uuid.uuid4()),
        "name": name,
        "exam_date": exam_date,
        "topics": topic_count
    })
    save_data()
    update_subject_countdowns()


def add_plan_tasks(button):
    name = button.getAttribute("data-subject")
    count = int(button.getAttribute("data-count"))
    minutes = int(button.getAttribute("data-minutes"))
    outcome = button.getAttribute("data-outcome") or ""

    for i in range(count):
        tasks.append({
            "id": str(uuid.uuid4()),
            "name": name + " - Topic " + str(i + 1),
            "minutes": minutes,
            "done": False,
            "day": date.today().isoformat(),
            "outcome": outcome
        })

    save_data()
    render_tasks()
    update_analytics()
    button.disabled = True
    button.innerText = "Sessions added to today's tasks"


# ---------- EXAM COUNTDOWN ----------

# ---------- PROGRESS ANALYTICS ----------

def update_analytics():
    today = date.today().isoformat()
    today_tasks = [task for task in tasks if task.get("day") == today]

    completed = sum(1 for task in today_tasks if task["done"])
    pending = len(today_tasks) - completed

    total = len(today_tasks)
    rate = int(completed * 100 / total) if total else 0

    minutes = sum(
        task["minutes"] for task in today_tasks if task["done"]
    )

    set_text("completedCount", completed)
    set_text("pendingCount", pending)
    set_text("completionRate", str(rate) + "%")
    set_text("studyTime", str(minutes) + " min")
    set_text("goalPercent", str(rate) + "%")
    update_study_charts()

    bar = get_element("progressBar")
    if bar:
        bar.value = rate

    if total:
        set_text(
            "analyticsMessage",
            "You completed " + str(completed) + " of "
            + str(total) + " tasks today."
        )
    else:
        set_text(
            "analyticsMessage",
            "Add your first task to start tracking progress."
        )

    update_learning_outcomes()


def update_learning_outcomes():
    outcome_groups = {}
    for task in tasks:
        outcome = task.get("outcome", "").strip()
        if not outcome:
            continue

        key = outcome.casefold()
        if key not in outcome_groups:
            outcome_groups[key] = {"name": outcome, "tasks": []}
        outcome_groups[key]["tasks"].append(task)

    achieved = sum(
        1 for group in outcome_groups.values()
        if all(task["done"] for task in group["tasks"])
    )
    total = len(outcome_groups)
    rate = int(achieved * 100 / total) if total else 0

    set_text("outcomeCount", str(achieved) + " / " + str(total))
    progress = get_element("outcomeProgress")
    if progress:
        progress.value = rate

    if total:
        set_text(
            "outcomeMessage",
            "Outcomes are achieved when all linked study tasks are complete."
        )
    else:
        set_text(
            "outcomeMessage",
            "Add an outcome to a task or study plan to track what you can do."
        )

    outcome_list = get_element("outcomeList")
    if not outcome_list:
        return

    outcome_list.innerHTML = ""
    for group in list(outcome_groups.values())[:5]:
        is_achieved = all(task["done"] for task in group["tasks"])
        row = document.createElement("div")
        row.className = "outcome-item"

        name = document.createElement("span")
        name.className = "outcome-name"
        name.innerText = group["name"]
        row.appendChild(name)

        status = document.createElement("span")
        status.className = (
            "outcome-status achieved" if is_achieved
            else "outcome-status in-progress"
        )
        status.innerText = "Achieved" if is_achieved else "In progress"
        row.appendChild(status)
        outcome_list.appendChild(row)


# ---------- INITIALIZE ----------

load_data()
render_tasks()
update_analytics()
update_subject_countdowns()

task_date_label = get_element("taskDateLabel")
if task_date_label:
    task_date_label.innerText = date.today().strftime("%A, %b %d").upper()

task_list_element = get_element("taskList")
if task_list_element:
    event_proxies.append(create_proxy(handle_task_list_click))
    task_list_element.addEventListener("click", event_proxies[-1])

plan_result_element = get_element("planResult")
if plan_result_element:
    event_proxies.append(create_proxy(handle_plan_result_click))
    plan_result_element.addEventListener("click", event_proxies[-1])

subject_countdown_list = get_element("subjectCountdownList")
if subject_countdown_list:
    event_proxies.append(create_proxy(handle_subject_countdown_click))
    subject_countdown_list.addEventListener("click", event_proxies[-1])
