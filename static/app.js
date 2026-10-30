const taskInput = document.getElementById("task");
const counter = document.getElementById("counter");
const submitButton = document.getElementById("submit");
const message = document.getElementById("message");
const jobList = document.getElementById("job-list");

taskInput.addEventListener("input", () => {
  counter.textContent = `${taskInput.value.length} / 4000`;
});

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[ch]));
}

async function loadJobs() {
  try {
    const response = await fetch("/api/jobs");
    const jobs = await response.json();
    if (!jobs.length) {
      jobList.innerHTML = '<div class="empty">Пока нет задач. Отправь первую задачу выше.</div>';
      return;
    }
    jobList.innerHTML = jobs.map(job => `
      <article class="job">
        <div class="job-top"><span class="job-id">ЗАДАЧА #${job.id}</span><span class="badge">${escapeHtml(job.status)}</span></div>
        <p>${escapeHtml(job.task)}</p>
        <small>${escapeHtml(new Date(job.created_at).toLocaleString())}</small>
        ${job.result ? `<small>${escapeHtml(job.result)}</small>` : ""}
      </article>`).join("");
  } catch {
    jobList.innerHTML = '<div class="empty">Не удалось загрузить задачи. Проверь, что сервер запущен.</div>';
  }
}

submitButton.addEventListener("click", async () => {
  const task = taskInput.value.trim();
  if (!task) {
    message.textContent = "Сначала опиши задачу.";
    return;
  }
  submitButton.disabled = true;
  message.textContent = "Сохраняем задачу…";
  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({task})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Не удалось отправить задачу.");
    message.textContent = data.message || "Задача отправлена.";
    taskInput.value = "";
    counter.textContent = "0 / 4000";
    await loadJobs();
  } catch (error) {
    message.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
});

document.getElementById("refresh").addEventListener("click", loadJobs);
loadJobs();
