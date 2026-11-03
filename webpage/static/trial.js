// The only JavaScript: timing has to happen in the browser to be accurate.
// Shows the image for EXPOSURE_MS, then hides it, shows the answers and
// measures the reaction time from that moment to the answer click.
// Test mode (app.py --test) adds a visible countdown, marks the answer
// right/wrong and waits a few seconds before going to the next image.

const script = document.currentScript;
const EXPOSURE_MS = Number(script.dataset.exposureMs);
const TEST_MODE = script.hasAttribute("data-test-mode");
const TEST_NEXT_DELAY_S = Number(script.dataset.nextDelayS);

const image = document.getElementById("stimulus");
const form = document.getElementById("answer-form");
const countdown = document.getElementById("countdown");
let answersShownAt = 0;

function showAnswers() {
  // Remove the image (and its space) so the answers move up and fit on the screen without scrolling.
  document.getElementById("image-frame").hidden = true;
  form.hidden = false;
  answersShownAt = performance.now();
}

// Start the exposure only once the image has loaded (usually instant – it was preloaded on the intro page).
function startExposure() {
  const start = performance.now();
  setTimeout(showAnswers, EXPOSURE_MS);
  if (TEST_MODE) {
    const tick = setInterval(() => {
      const left = Math.max(0, EXPOSURE_MS - (performance.now() - start));
      countdown.textContent = `· ${(left / 1000).toFixed(1)} s`;
      if (left === 0) clearInterval(tick);
    }, 50);
  }
}
if (image.complete) startExposure();
else image.addEventListener("load", startExposure);

form.addEventListener("submit", (event) => {
  document.getElementById("rt").value = Math.round(performance.now() - answersShownAt);
  document.getElementById("answer").value = event.submitter.value;
  if (!TEST_MODE) return;

  // Test mode: show the result, then continue after a countdown.
  event.preventDefault();
  for (const button of form.querySelectorAll("button")) {
    button.disabled = true;
    if (button.value === script.dataset.correct) button.classList.add("correct");
    else if (button === event.submitter) button.classList.add("wrong");
  }
  let left = TEST_NEXT_DELAY_S;
  const tick = () => {
    countdown.textContent = `· RT ${document.getElementById("rt").value} ms · next in ${left} s`;
    if (left-- === 0) form.submit();
    else setTimeout(tick, 1000);
  };
  tick();
});
