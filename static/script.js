const totalQuestions = 20;
let questions = [];
let selectedQuestions = [];
let timerInterval;

function startTest() {
  fetch("/static/questions.json")
    .then((res) => res.json())
    .then((data) => {
      questions = data;
      selectedQuestions = shuffle(questions).slice(0, totalQuestions);
      displayQuestions();
      startTimer(20 * 60);
    })
    .catch((err) => console.error("Failed to load questions:", err));

  const startButton = document.getElementById("start-button");
  if (startButton) startButton.style.display = "none";
  const quizContainer = document.getElementById("quiz-container");
  if (quizContainer) quizContainer.style.display = "block";
}

function shuffle(array) {
  return array.sort(() => Math.random() - 0.5);
}

function displayQuestions() {
  const form = document.getElementById("quiz-form");
  if (!form) return;
  form.innerHTML = "";
  selectedQuestions.forEach((q, index) => {
    form.innerHTML += `
      <div class="question-block">
        <p><strong>${index + 1}. ${q.question}</strong></p>
        ${q.options
          .map(
            (opt) =>
              `<label><input type="radio" name="q${index}" value="${opt}"> ${opt}</label><br>`
          )
          .join("")}
      </div><hr>
    `;
  });
}

function startTimer(duration) {
  const display = document.getElementById("timer");
  if (!display) return;
  let time = duration;
  timerInterval = setInterval(() => {
    const minutes = String(Math.floor(time / 60)).padStart(2, "0");
    const seconds = String(time % 60).padStart(2, "0");
    display.textContent = `Time Left: ${minutes}:${seconds}`;
    if (--time < 0) {
      clearInterval(timerInterval);
      submitTest();
    }
  }, 1000);
}

function submitTest() {
  clearInterval(timerInterval);
  const form = document.getElementById("quiz-form");
  if (!form) return;

  let score = 0;
  selectedQuestions.forEach((q, index) => {
    const selected = form.querySelector(`input[name="q${index}"]:checked`);
    if (selected && selected.value.trim() === String(q.answer).trim()) score++;
  });

  // Hide quiz
  const quizContainer = document.getElementById("quiz-container");
  const resultDiv = document.getElementById("result");
  if (quizContainer) quizContainer.style.display = "none";
  if (resultDiv) {
    resultDiv.style.display = "block";
    resultDiv.innerHTML = `<h2>Ugize Amanota: ${score} / ${totalQuestions}</h2>`;

    // Send score to Flask
    fetch("/save_score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ score: score, total: totalQuestions }),
    });

    const homeButton = document.createElement("button");
    homeButton.textContent = "Subira Ahabanza";
    homeButton.onclick = () => {
      window.location.href = "/home";
    };
    resultDiv.appendChild(homeButton);
  }
}
