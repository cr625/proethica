(function() {
    const dataEl = document.getElementById('results-data');
    if (!dataEl) return;
    const results = JSON.parse(dataEl.textContent);
    if (!results || !results.n_completed_evals) return;

    // -------- Chart 1: Mean utility by view (bar with SD whiskers) --------
    const meansCanvas = document.getElementById('chart-view-means');
    if (meansCanvas) {
        const labels = results.view_means.map(r => r.label);
        const means = results.view_means.map(r => r.mean);
        const sds = results.view_means.map(r => r.sd || 0);
        const ns = results.view_means.map(r => r.n);

        // Custom plugin draws +/- 1 SD whiskers on top of each bar.
        const errorBarsPlugin = {
            id: 'errorBars',
            afterDatasetDraw(chart) {
                const { ctx, scales: { y } } = chart;
                const meta = chart.getDatasetMeta(0);
                ctx.save();
                ctx.strokeStyle = '#495057';
                ctx.lineWidth = 1.5;
                meta.data.forEach((bar, i) => {
                    const sd = sds[i];
                    if (!sd || means[i] == null) return;
                    const x = bar.x;
                    const yTop = y.getPixelForValue(means[i] + sd);
                    const yBot = y.getPixelForValue(Math.max(1, means[i] - sd));
                    ctx.beginPath();
                    ctx.moveTo(x, yTop);
                    ctx.lineTo(x, yBot);
                    ctx.moveTo(x - 6, yTop);
                    ctx.lineTo(x + 6, yTop);
                    ctx.moveTo(x - 6, yBot);
                    ctx.lineTo(x + 6, yBot);
                    ctx.stroke();
                });
                ctx.restore();
            }
        };

        new Chart(meansCanvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Mean Likert score',
                    data: means,
                    backgroundColor: ['#0d6efd', '#6610f2', '#d63384', '#fd7e14', '#198754', '#6c757d'],
                    borderWidth: 0,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { min: 1, max: 7, ticks: { stepSize: 1 }, title: { display: true, text: 'Mean (1-7)' } }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            afterLabel: (ctx) => {
                                const i = ctx.dataIndex;
                                const parts = [`n = ${ns[i]}`];
                                if (sds[i]) parts.push(`SD = ${sds[i]}`);
                                return parts.join(' · ');
                            }
                        }
                    }
                }
            },
            plugins: [errorBarsPlugin]
        });
    }

    // -------- Chart 2: Retrospective rankings (stacked horizontal bar) --------
    const ranksCanvas = document.getElementById('chart-rankings');
    if (ranksCanvas) {
        const labels = results.ranking_counts.map(r => r.label);
        // Rank colors: rank 1 dark/positive -> rank 5 light/negative.
        const rankPalette = ['#198754', '#5cb85c', '#ffc107', '#fd7e14', '#dc3545'];
        const datasets = [0, 1, 2, 3, 4].map(rankIdx => ({
            label: `Rank ${rankIdx + 1}`,
            data: results.ranking_counts.map(r => r.counts[rankIdx]),
            backgroundColor: rankPalette[rankIdx],
            borderWidth: 0,
        }));

        new Chart(ranksCanvas, {
            type: 'bar',
            data: { labels: labels, datasets: datasets },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { stacked: true, ticks: { stepSize: 1 }, title: { display: true, text: 'Participants' } },
                    y: { stacked: true }
                },
                plugins: {
                    legend: { position: 'bottom', labels: { boxWidth: 14 } },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.x}`
                        }
                    }
                }
            }
        });
    }

    // -------- Chart 3: Per-case mean overall utility (horizontal bar) --------
    const perCaseCanvas = document.getElementById('chart-per-case');
    if (perCaseCanvas && results.per_case_means && results.per_case_means.length) {
        const labels = results.per_case_means.map(r => `${r.case_id}: ${r.title.length > 60 ? r.title.slice(0, 57) + '…' : r.title}`);
        const means = results.per_case_means.map(r => r.mean);
        const ns = results.per_case_means.map(r => r.n);

        new Chart(perCaseCanvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Mean overall utility',
                    data: means,
                    backgroundColor: '#0d6efd',
                    borderWidth: 0,
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { min: 1, max: 7, ticks: { stepSize: 1 }, title: { display: true, text: 'Mean overall utility (1-7)' } }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            afterLabel: (ctx) => `n = ${ns[ctx.dataIndex]} rater(s)`
                        }
                    }
                }
            }
        });
    }
})();
