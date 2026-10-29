function localDateValue(date = new Date()) {
    const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return localDate.toISOString().slice(0, 10);
}

let savedSubjectExams = [];

function getDaysUntilExam(examDate) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(examDate || "")) return null;
    const [year, month, day] = examDate.split("-").map(Number);
    const examDay = Date.UTC(year, month - 1, day);
    const parsedDate = new Date(examDay);
    if (
        parsedDate.getUTCFullYear() !== year ||
        parsedDate.getUTCMonth() !== month - 1 ||
        parsedDate.getUTCDate() !== day
    ) return null;
    const now = new Date();
    const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
    return Math.round((examDay - today) / 86400000);
}

function renderSubjectCountdowns(serializedSubjects) {
    const list = document.getElementById("subjectCountdownList");
    if (!list) return;

    savedSubjectExams = JSON.parse(serializedSubjects).filter((subject) =>
        subject && typeof subject.name === "string" && typeof subject.exam_date === "string"
    );
    list.replaceChildren();

    if (savedSubjectExams.length === 0) {
        const empty = document.createElement("p");
        empty.className = "subject-countdown-empty";
        empty.textContent = "Generate a study plan to add your first subject countdown.";
        list.appendChild(empty);
        return;
    }

    const sortedSubjects = [...savedSubjectExams].sort((first, second) =>
        first.exam_date.localeCompare(second.exam_date)
    );
    sortedSubjects.forEach((subject) => {
        const daysLeft = getDaysUntilExam(subject.exam_date);
        const card = document.createElement("article");
        card.className = "subject-countdown-item";

        const details = document.createElement("div");
        details.className = "subject-countdown-details";
        const name = document.createElement("strong");
        name.className = "subject-countdown-name";
        name.textContent = subject.name;
        const date = document.createElement("span");
        date.className = "subject-countdown-date";
        date.textContent = daysLeft === null ? "Invalid date" : new Intl.DateTimeFormat(undefined, {
            year: "numeric",
            month: "short",
            day: "numeric"
        }).format(new Date(`${subject.exam_date}T00:00:00`));
        details.append(name, date);

        const status = document.createElement("span");
        status.className = "subject-countdown-days";
        status.textContent = daysLeft === null ? "Invalid date"
            : daysLeft < 0 ? "Passed"
            : daysLeft === 0 ? "Today"
            : `${daysLeft} days`;
        if (daysLeft !== null && daysLeft < 0) {
            card.classList.add("is-past");
        } else if (daysLeft === 0) {
            card.classList.add("is-today");
        }

        const removeButton = document.createElement("button");
        removeButton.className = "remove-subject-countdown";
        removeButton.type = "button";
        removeButton.textContent = "×";
        removeButton.setAttribute("data-subject-id", subject.id || "");
        removeButton.setAttribute("aria-label", `Remove ${subject.name} countdown`);

        card.append(details, status, removeButton);
        list.appendChild(card);
    });
}

function formatChartDate(date) {
    return new Intl.DateTimeFormat(undefined, {
        weekday: "long",
        month: "short",
        day: "numeric"
    }).format(date);
}

function renderWeeklyStudyChart(tasks) {
    const chart = document.getElementById("weeklyChart");
    if (!chart) return;

    chart.replaceChildren();
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const days = Array.from({ length: 7 }, (_, index) => {
        const day = new Date(today);
        day.setDate(today.getDate() - 6 + index);
        return day;
    });
    const totals = new Map(days.map((day) => [
        localDateValue(day),
        { planned: 0, completed: 0 }
    ]));

    tasks.forEach((task) => {
        if (task.done && totals.has(task.day)) {
            const dayTotals = totals.get(task.day);
            dayTotals.planned += Number(task.minutes || 0);
            dayTotals.completed += Number(task.minutes || 0);
        } else if (totals.has(task.day)) {
            totals.get(task.day).planned += Number(task.minutes || 0);
        }
    });

    const maximum = Math.max(...[...totals.values()].map((value) => value.planned), 0);
    const message = document.getElementById("weeklyChartMessage");
    const hasStudyTasks = [...totals.values()].some((value) => value.planned > 0);
    if (message) {
        message.hidden = hasStudyTasks;
    }

    days.forEach((day) => {
        const dayKey = localDateValue(day);
        const { planned, completed } = totals.get(dayKey);
        const dayColumn = document.createElement("div");
        dayColumn.className = "chart-day";
        dayColumn.tabIndex = 0;
        dayColumn.setAttribute(
            "aria-label",
            `${formatChartDate(day)}: ${completed} completed, ${planned} planned study minutes`
        );
        dayColumn.title = `${formatChartDate(day)} · ${completed} done / ${planned} planned min`;

        const value = document.createElement("span");
        value.className = "chart-day-value";
        value.textContent = `${completed}/${planned}`;
        dayColumn.appendChild(value);

        const track = document.createElement("div");
        track.className = "chart-bar-track";
        const plannedBar = document.createElement("div");
        plannedBar.className = "chart-bar-planned";
        plannedBar.style.height = maximum
            ? `${Math.max(4, (planned / maximum) * 100)}%`
            : "4%";
        const completedBar = document.createElement("div");
        completedBar.className = "chart-bar-fill";
        completedBar.style.height = planned
            ? `${(completed / planned) * 100}%`
            : "0%";
        plannedBar.appendChild(completedBar);
        track.appendChild(plannedBar);
        dayColumn.appendChild(track);

        const label = document.createElement("span");
        label.className = "chart-day-label";
        label.textContent = dayKey === localDateValue(today)
            ? "Today"
            : new Intl.DateTimeFormat(undefined, { weekday: "short" }).format(day);
        dayColumn.appendChild(label);
        chart.appendChild(dayColumn);
    });
}

function renderSubjectStudyChart(tasks) {
    const chart = document.getElementById("studyGraph");
    if (!chart) return;

    chart.replaceChildren();
    const today = localDateValue();
    const totals = new Map();
    tasks.forEach((task) => {
        if (task.day !== today) return;
        const subject = task.name.replace(/ - Topic \d+$/, "").trim();
        if (!totals.has(subject)) {
            totals.set(subject, { planned: 0, completed: 0 });
        }
        const subjectTotals = totals.get(subject);
        subjectTotals.planned += Number(task.minutes || 0);
        if (task.done) {
            subjectTotals.completed += Number(task.minutes || 0);
        }
    });

    const subjects = [...totals.entries()].sort(
        (first, second) => second[1].planned - first[1].planned
    );
    if (subjects.length === 0) {
        const empty = document.createElement("div");
        empty.className = "chart-empty";
        empty.textContent = "Add a study task to see planned and completed time by subject.";
        chart.appendChild(empty);
        return;
    }

    const maximum = subjects[0][1].planned;
    subjects.forEach(([subject, subjectTotals]) => {
        const { planned, completed } = subjectTotals;
        const row = document.createElement("div");
        row.className = "subject-row";
        row.title = `${subject}: ${completed} completed, ${planned} planned minutes`;

        const heading = document.createElement("div");
        heading.className = "subject-row-heading";
        const name = document.createElement("span");
        name.textContent = subject;
        const total = document.createElement("span");
        total.textContent = `${completed} / ${planned} min`;
        heading.append(name, total);

        const track = document.createElement("div");
        track.className = "subject-bar-track";
        const plannedBar = document.createElement("div");
        plannedBar.className = "subject-bar-planned";
        plannedBar.style.width = `${(planned / maximum) * 100}%`;
        const fill = document.createElement("div");
        fill.className = "subject-bar-fill";
        fill.style.width = `${planned ? (completed / planned) * 100 : 0}%`;
        plannedBar.appendChild(fill);
        track.appendChild(plannedBar);
        row.append(heading, track);
        chart.appendChild(row);
    });
}

function updateStudyCharts(serializedTasks) {
    const tasks = JSON.parse(serializedTasks);
    renderWeeklyStudyChart(tasks);
    renderSubjectStudyChart(tasks);
}

function updateGoalRing() {
    const percent = document.getElementById("goalPercent");
    const circle = document.querySelector(".goal-circle");
    if (!percent || !circle) return;

    const value = Number.parseInt(percent.textContent, 10);
    circle.style.setProperty(
        "--goal-progress",
        `${Number.isFinite(value) ? Math.min(100, Math.max(0, value)) : 0}%`
    );
}

function initializeDashboardEnhancements() {
    const today = localDateValue();
    const plannerDate = document.getElementById("plannerDate");
    if (plannerDate) plannerDate.min = today;

    document.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" || event.isComposing) return;
        const target = event.target;
        if (!(target instanceof HTMLInputElement) || target.type === "date") return;

        if (["taskName", "taskOutcome", "taskMinutes"].includes(target.id)) {
            event.preventDefault();
            document.querySelector(".add-task-button")?.click();
        } else if (["subjectName", "topics", "hours", "plannerOutcome"].includes(target.id)) {
            event.preventDefault();
            document.querySelector("#planner .button-primary")?.click();
        }
    });

    const goalPercent = document.getElementById("goalPercent");
    if (goalPercent) {
        new MutationObserver(updateGoalRing).observe(goalPercent, {
            childList: true,
            characterData: true,
            subtree: true
        });
    }
    updateGoalRing();
    const savedDashboard = localStorage.getItem("exammate_dashboard");
    if (savedDashboard) {
        const dashboardData = JSON.parse(savedDashboard);
        updateStudyCharts(JSON.stringify(dashboardData.tasks || []));
        renderSubjectCountdowns(JSON.stringify(dashboardData.subjects || []));
    } else {
        updateStudyCharts("[]");
        renderSubjectCountdowns("[]");
    }
    window.setInterval(() => {
        renderSubjectCountdowns(JSON.stringify(savedSubjectExams));
    }, 60 * 60 * 1000);

    const navigationLinks = [...document.querySelectorAll(".navigation a")];
    navigationLinks.forEach((link) => {
        link.addEventListener("click", () => {
            navigationLinks.forEach((item) => item.classList.toggle("active", item === link));
        });
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeDashboardEnhancements);
} else {
    initializeDashboardEnhancements();
}
