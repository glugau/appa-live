const playPauseBtn = document.getElementById('play-pause');
const timeText = document.getElementById('time-text');
const slider = document.getElementById('slider');
let intervalId = null;

function updateTimeText(val) {
  timeText.textContent = `Time: ${val}`;
}

function togglePlayPause() {
  if (intervalId) {
    clearInterval(intervalId);
    intervalId = null;
    playPauseBtn.textContent = '▶️';
  } else {
    playPauseBtn.textContent = '⏸️';
    intervalId = setInterval(() => {
      let val = +slider.value;
      if (val >= +slider.max) {
        clearInterval(intervalId);
        intervalId = null;
        playPauseBtn.textContent = '▶️';
        return;
      }
      slider.value = val + 1;
      updateTimeText(slider.value);
    }, 1000);
  }
}

playPauseBtn.addEventListener('click', togglePlayPause);

// update slider input to also update time display and stop animation at max
slider.addEventListener('input', () => {
  updateTimeText(slider.value);
  if (intervalId && +slider.value >= +slider.max) {
    clearInterval(intervalId);
    intervalId = null;
    playPauseBtn.textContent = '▶️';
  }
});

const min = +slider.min;
const max = +slider.max;