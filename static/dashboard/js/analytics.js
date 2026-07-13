(function () {
  if (typeof Chart === 'undefined') return;

  function readData(id) {
    const el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  }

  const styles = getComputedStyle(document.documentElement);
  const accent = styles.getPropertyValue('--accent').trim() || '#D4A24C';
  const positive = styles.getPropertyValue('--positive').trim() || '#3ECFB0';
  const negative = styles.getPropertyValue('--negative').trim() || '#E2685A';
  const muted = styles.getPropertyValue('--text-muted').trim() || '#8B93A3';
  const border = styles.getPropertyValue('--border-subtle').trim() || '#212836';

  Chart.defaults.color = muted;
  Chart.defaults.font.family = "'Inter', sans-serif";
  Chart.defaults.font.size = 11;

  const gridOpts = { color: border, drawTicks: false };
  const palette = [accent, positive, '#8AB4E8', '#E8B85E', negative, '#A78BDA', '#6FCF97', '#E29E4F'];

  function lineChart(canvasId, dataKey, color) {
    const data = readData(dataKey);
    const el = document.getElementById(canvasId);
    if (!data || !el) return;
    new Chart(el, {
      type: 'line',
      data: {
        labels: data.labels,
        datasets: [{
          data: data.data, borderColor: color, backgroundColor: color + '22',
          fill: true, tension: 0.35, pointRadius: 0, borderWidth: 2,
        }],
      },
      options: {
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { maxTicksLimit: 8 } },
          y: { grid: gridOpts, beginAtZero: true, ticks: { precision: 0 } },
        },
      },
    });
  }

  function doughnutChart(canvasId, dataKey) {
    const data = readData(dataKey);
    const el = document.getElementById(canvasId);
    if (!data || !el) return;
    new Chart(el, {
      type: 'doughnut',
      data: { labels: data.labels, datasets: [{ data: data.data, backgroundColor: palette, borderWidth: 0 }] },
      options: { plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, padding: 14 } } }, cutout: '65%' },
    });
  }

  function barChart(canvasId, dataKey, horizontal) {
    const data = readData(dataKey);
    const el = document.getElementById(canvasId);
    if (!data || !el) return;
    new Chart(el, {
      type: 'bar',
      data: { labels: data.labels, datasets: [{ data: data.data, backgroundColor: accent, borderRadius: 4, maxBarThickness: 28 }] },
      options: {
        indexAxis: horizontal ? 'y' : 'x',
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: horizontal ? gridOpts : { display: false }, beginAtZero: true, ticks: { precision: 0 } },
          y: { grid: horizontal ? { display: false } : gridOpts, beginAtZero: true, ticks: { precision: 0 } },
        },
      },
    });
  }

  function campaignChart() {
    const data = readData('data-campaigns');
    const el = document.getElementById('chart-campaigns');
    if (!data || !el || !data.labels.length) return;
    new Chart(el, {
      type: 'bar',
      data: {
        labels: data.labels,
        datasets: [
          { label: 'Sent', data: data.sent, backgroundColor: positive, borderRadius: 3 },
          { label: 'Opened', data: data.opened, backgroundColor: accent, borderRadius: 3 },
          { label: 'Failed', data: data.failed, backgroundColor: negative, borderRadius: 3 },
        ],
      },
      options: {
        plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, padding: 14 } } },
        scales: {
          x: { grid: { display: false }, stacked: false },
          y: { grid: gridOpts, beginAtZero: true, ticks: { precision: 0 } },
        },
      },
    });
  }

  lineChart('chart-registration-trend', 'data-registration-trend', accent);
  lineChart('chart-attendance-trend', 'data-attendance-trend', positive);
  doughnutChart('chart-gender', 'data-gender');
  doughnutChart('chart-returning', 'data-returning');
  barChart('chart-age', 'data-age', false);
  barChart('chart-departments', 'data-departments', false);
  barChart('chart-states', 'data-states', true);
  barChart('chart-countries', 'data-countries', true);
  campaignChart();
})();
