document.addEventListener('DOMContentLoaded', () => {
    const fileListEl = document.getElementById('fileList');
    const searchInput = document.getElementById('searchInput');
    const tagFiltersEl = document.getElementById('tagFilters');
    const selectAllBtn = document.getElementById('selectAllBtn');
    const deselectAllBtn = document.getElementById('deselectAllBtn');
    const refreshBtn = document.getElementById('refreshBtn');
    const generateBtn = document.getElementById('generateBtn');
    const uploadZone = document.getElementById('uploadZone');
    const uploadInput = document.getElementById('uploadInput');
    
    const chartTabs = document.querySelectorAll('.tab');
    const channelCheckboxes = document.querySelectorAll('.channel-filter');
    const emptyState = document.getElementById('emptyState');
    const loading = document.getElementById('loading');
    const resultContainer = document.getElementById('resultContainer');
    const plotlyChart = document.getElementById('plotlyChart');
    const analysisSummary = document.getElementById('analysisSummary');
    const reportPanel = document.getElementById('reportPanel');

    // Modal elements
    const tagModal = document.getElementById('tagModal');
    const closeModalBtn = document.getElementById('closeModalBtn');
    const cancelTagBtn = document.getElementById('cancelTagBtn');
    const saveTagBtn = document.getElementById('saveTagBtn');
    const modalFileName = document.getElementById('modalFileName');
    const newTagInput = document.getElementById('newTagInput');
    const modalTagList = document.getElementById('modalTagList');

    let allFiles = [];
    let currentData = null; // Store fetched JSON data
    let currentChartType = 'boxplot';
    let globalAllTags = [];
    let activeTagFilters = [];
    
    let editingFileName = null;
    let editingTags = [];

    // Load files list
    function loadFiles() {
        const originalHTML = refreshBtn.innerHTML;
        refreshBtn.disabled = true;
        
        fetch('/api/files?t=' + new Date().getTime(), { cache: 'no-store' })
            .then(res => res.json())
            .then(data => {
                allFiles = data.files || [];
                globalAllTags = data.all_tags || [];
                renderTagFilters(globalAllTags);
                renderFiles(allFiles);
                applyFilters();
            })
            .catch(err => {
                console.error('Failed to load files:', err);
                fileListEl.innerHTML = '<p style="color:red; text-align:center; padding: 1rem;">加载文件失败</p>';
            })
            .finally(() => {
                refreshBtn.disabled = false;
                refreshBtn.innerHTML = originalHTML;
            });
    }

    function renderTagFilters(tags) {
        tagFiltersEl.innerHTML = '';
        tags.forEach(tag => {
            const chip = document.createElement('div');
            chip.className = 'tag-chip';
            if (activeTagFilters.includes(tag)) chip.classList.add('active');
            chip.textContent = tag;
            chip.onclick = () => {
                if (activeTagFilters.includes(tag)) {
                    activeTagFilters = activeTagFilters.filter(t => t !== tag);
                    chip.classList.remove('active');
                } else {
                    activeTagFilters.push(tag);
                    chip.classList.add('active');
                }
                applyFilters();
            };
            tagFiltersEl.appendChild(chip);
        });
    }

    function renderFiles(files) {
        fileListEl.innerHTML = '';
        if (!files || files.length === 0) {
            fileListEl.innerHTML = '<p style="text-align:center; color:var(--text-tertiary); padding: 1.5rem 0;">未找到任何文件</p>';
            return;
        }

        files.forEach((fileObj, index) => {
            const fileName = fileObj.name;
            const fileId = fileObj.id || fileName;
            const source = fileObj.source || 'server';
            const fileTags = fileObj.tags || [];
            
            const item = document.createElement('div');
            item.className = 'file-item';
            item.dataset.name = fileName;
            item.dataset.tags = JSON.stringify(fileTags);
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = `file-${index}`;
            checkbox.value = fileId;
            checkbox.addEventListener('change', updateGenerateBtn);

            const infoDiv = document.createElement('div');
            infoDiv.className = 'file-info';

            const label = document.createElement('label');
            label.htmlFor = `file-${index}`;
            label.textContent = fileName;

            const tagsDiv = document.createElement('div');
            tagsDiv.className = 'file-tags';
            const sourceBadge = document.createElement('span');
            sourceBadge.className = `source-badge ${source === 'upload' ? 'upload' : 'server'}`;
            sourceBadge.textContent = source === 'upload' ? '上传' : '服务器';
            tagsDiv.appendChild(sourceBadge);
            fileTags.forEach(tag => {
                const tagSpan = document.createElement('span');
                tagSpan.className = 'mini-tag';
                tagSpan.textContent = tag;
                tagsDiv.appendChild(tagSpan);
            });

            infoDiv.appendChild(label);
            infoDiv.appendChild(tagsDiv);

            const editBtn = document.createElement('button');
            editBtn.className = 'edit-tags-btn';
            editBtn.innerHTML = '<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"></path></svg>';
            editBtn.disabled = source === 'upload';
            editBtn.title = source === 'upload' ? '上传文件暂不保存标签' : '编辑标签';
            editBtn.onclick = (e) => {
                e.preventDefault();
                if (source === 'upload') return;
                openTagModal(fileName, fileTags);
            };

            item.appendChild(checkbox);
            item.appendChild(infoDiv);
            item.appendChild(editBtn);
            fileListEl.appendChild(item);
        });
        updateGenerateBtn();
    }

    function applyFilters() {
        const query = searchInput.value.toLowerCase().trim();
        const keywords = query.split(/\s+/).filter(k => k.length > 0);
        const items = fileListEl.querySelectorAll('.file-item');
        
        items.forEach(item => {
            const fileName = item.dataset.name.toLowerCase();
            const fileTagsRaw = item.dataset.tags;
            const fileTags = fileTagsRaw ? JSON.parse(fileTagsRaw) : [];
            
            // Text match
            const textMatch = keywords.length === 0 || keywords.every(kw => fileName.includes(kw) || fileTags.some(t => t.toLowerCase().includes(kw)));
            
            // Tag match (AND logic: must contain ALL active tags)
            const tagMatch = activeTagFilters.length === 0 || activeTagFilters.every(t => fileTags.includes(t));
            
            item.style.display = (textMatch && tagMatch) ? 'flex' : 'none';
        });
    }

    searchInput.addEventListener('input', applyFilters);

    function setUploadBusy(isBusy) {
        uploadZone.classList.toggle('busy', isBusy);
    }

    async function uploadFiles(files) {
        const csvFiles = Array.from(files || []).filter(file => file.name.toLowerCase().endsWith('.csv'));
        if (csvFiles.length === 0) {
            alert('请选择 CSV 文件');
            return;
        }

        const formData = new FormData();
        csvFiles.forEach(file => formData.append('files', file));
        setUploadBusy(true);

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || '上传失败');
            }
            await loadFiles();
        } catch (error) {
            console.error(error);
            alert('上传失败: ' + error.message);
        } finally {
            setUploadBusy(false);
            uploadInput.value = '';
        }
    }

    uploadZone.addEventListener('click', () => uploadInput.click());
    uploadInput.addEventListener('change', (e) => uploadFiles(e.target.files));
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });
    uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        uploadFiles(e.dataTransfer.files);
    });

    // Modal Logic
    function openTagModal(fileName, tags) {
        editingFileName = fileName;
        editingTags = [...tags];
        modalFileName.textContent = fileName;
        newTagInput.value = '';
        renderModalTags();
        tagModal.classList.remove('hidden');
        setTimeout(() => newTagInput.focus(), 50);
    }

    function closeTagModal() {
        tagModal.classList.add('hidden');
        editingFileName = null;
        editingTags = [];
    }

    function renderModalTags() {
        modalTagList.innerHTML = '';
        editingTags.forEach(tag => {
            const tagEl = document.createElement('div');
            tagEl.className = 'removable-tag';
            tagEl.innerHTML = `
                <span>${tag}</span>
                <button class="remove-tag-btn" data-tag="${tag}">&times;</button>
            `;
            tagEl.querySelector('.remove-tag-btn').onclick = () => {
                editingTags = editingTags.filter(t => t !== tag);
                renderModalTags();
            };
            modalTagList.appendChild(tagEl);
        });
    }

    newTagInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            const newTag = newTagInput.value.trim();
            if (newTag && !editingTags.includes(newTag)) {
                editingTags.push(newTag);
                renderModalTags();
                newTagInput.value = '';
            }
        }
    });

    closeModalBtn.addEventListener('click', closeTagModal);
    cancelTagBtn.addEventListener('click', closeTagModal);

    saveTagBtn.addEventListener('click', async () => {
        if (!editingFileName) return;
        const originalText = saveTagBtn.textContent;
        saveTagBtn.disabled = true;
        saveTagBtn.textContent = '保存中...';

        try {
            const res = await fetch('/api/tags', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: editingFileName, tags: editingTags })
            });
            if (!res.ok) throw new Error('Failed to save tags');
            closeTagModal();
            loadFiles(); // Reload to refresh list and filters
        } catch (error) {
            console.error(error);
            alert('保存标签失败');
        } finally {
            saveTagBtn.disabled = false;
            saveTagBtn.textContent = originalText;
        }
    });

    selectAllBtn.addEventListener('click', () => {
        const visibleCheckboxes = Array.from(fileListEl.querySelectorAll('.file-item'))
            .filter(item => item.style.display !== 'none')
            .map(item => item.querySelector('input[type="checkbox"]'));
        visibleCheckboxes.forEach(cb => cb.checked = true);
        updateGenerateBtn();
    });

    deselectAllBtn.addEventListener('click', () => {
        const visibleCheckboxes = Array.from(fileListEl.querySelectorAll('.file-item'))
            .filter(item => item.style.display !== 'none')
            .map(item => item.querySelector('input[type="checkbox"]'));
        visibleCheckboxes.forEach(cb => cb.checked = false);
        updateGenerateBtn();
    });

    function updateGenerateBtn() {
        const selectedCount = Array.from(document.querySelectorAll('.file-item input[type="checkbox"]:checked')).length;
        generateBtn.disabled = selectedCount === 0 || selectedCount > 10;
        generateBtn.textContent = `分析数据 (${selectedCount}/10)`;
    }

    async function fetchData() {
        const selectedFiles = Array.from(document.querySelectorAll('.file-item input[type="checkbox"]:checked'))
            .map(cb => cb.value);
        const includeFailData = document.getElementById('includeFailData').checked;

        if (selectedFiles.length === 0) return;

        emptyState.classList.add('hidden');
        resultContainer.classList.add('hidden');
        loading.classList.remove('hidden');
        generateBtn.disabled = true;

        try {
            const response = await fetch('/api/fetch_chart_data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ files: selectedFiles, includeFailData: includeFailData })
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || '获取数据失败');
            }

            currentData = await response.json();
            renderSummary(currentData);
            renderChart();

            loading.classList.add('hidden');
            resultContainer.classList.remove('hidden');

        } catch (error) {
            console.error(error);
            alert('发生错误: ' + error.message);
            loading.classList.add('hidden');
            emptyState.classList.remove('hidden');
        } finally {
            updateGenerateBtn();
        }
    }

    function renderSummary(payload) {
        const summary = payload.summary || {};
        const reports = payload.file_reports || [];
        const warnings = summary.warnings || [];
        const channels = payload.available_channels || [];
        const freqs = payload.available_frequencies || [];

        analysisSummary.innerHTML = `
            <div class="summary-card">
                <span>有效文件</span>
                <strong>${summary.valid_files ?? 0}/${summary.total_files ?? 0}</strong>
            </div>
            <div class="summary-card">
                <span>样本点</span>
                <strong>${summary.rows ?? 0}</strong>
            </div>
            <div class="summary-card">
                <span>通道</span>
                <strong>${channels.join(' / ') || '-'}</strong>
            </div>
            <div class="summary-card">
                <span>频点</span>
                <strong>${freqs.join(' / ') || '-'}</strong>
            </div>
            <button class="report-toggle" id="reportToggle">${warnings.length ? `查看 ${warnings.length} 条提示` : '识别正常'}</button>
        `;

        const skipped = reports.filter(r => r.status !== 'ok');
        if (skipped.length === 0) {
            reportPanel.classList.add('hidden');
            reportPanel.innerHTML = '';
        } else {
            reportPanel.innerHTML = skipped.map(r => `
                <div class="report-row">
                    <strong>${r.name}</strong>
                    <span>${r.message}</span>
                </div>
            `).join('');
        }

        const reportToggle = document.getElementById('reportToggle');
        reportToggle.addEventListener('click', () => {
            if (skipped.length > 0) reportPanel.classList.toggle('hidden');
        });
    }

    chartTabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            chartTabs.forEach(t => t.classList.remove('active'));
            e.currentTarget.classList.add('active');
            currentChartType = e.currentTarget.dataset.type;
            if (currentData) renderChart();
        });
    });

    function renderChart() {
        if (!currentData) return;

        const chartType = currentChartType;
        const selectedChannels = Array.from(channelCheckboxes)
            .filter(cb => cb.checked)
            .map(cb => cb.value);

        const filteredData = currentData.data.filter(d => selectedChannels.includes(d.Channel));
        
        // Remove previous click listeners to prevent duplicates
        if (plotlyChart.removeAllListeners) {
            plotlyChart.removeAllListeners('plotly_click');
        }

        if (chartType === 'boxplot') {
            renderBoxplot(filteredData, currentData.unique_cps, selectedChannels);
        } else if (chartType === 'trend') {
            renderTrendPlot(filteredData, currentData.unique_cps, selectedChannels);
        }
    }

    // Theme Toggle Logic
    const themeToggle = document.getElementById('themeToggle');
    const themeIcon = document.getElementById('themeIcon');
    
    if (localStorage.getItem('theme') === 'dark') {
        document.body.classList.add('dark-mode');
        themeIcon.textContent = '☀️';
    }

    themeToggle.addEventListener('click', () => {
        document.body.classList.toggle('dark-mode');
        const isDark = document.body.classList.contains('dark-mode');
        themeIcon.textContent = isDark ? '☀️' : '🌙';
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
        if (currentData) renderChart();
    });

    const defaultColors = [
        '#2563eb', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', 
        '#ec4899', '#06b6d4', '#f97316', '#64748b', '#84cc16'
    ];

    function renderBoxplot(data, categories, channels) {
        const isDark = document.body.classList.contains('dark-mode');
        const traces = [];
        const nChannels = channels.length;
        
        channels.forEach((ch, chIdx) => {
            currentData.sources.forEach((source, sIdx) => {
                const subset = data.filter(d => d.Channel === ch && d.Source === source);
                if (subset.length === 0) return;
                
                traces.push({
                    x: subset.map(d => d.CheckPoint),
                    y: subset.map(d => d.Delta),
                    name: nChannels > 1 ? `${ch} - ${source}` : source,
                    type: 'box',
                    boxpoints: 'suspectedoutliers',
                    jitter: 0.3,
                    marker: { size: 2, color: defaultColors[sIdx % defaultColors.length] },
                    legendgroup: source,
                    offsetgroup: source,
                    showlegend: chIdx === 0,
                    xaxis: `x${chIdx + 1}`,
                    yaxis: `y${chIdx + 1}`
                });
            });
        });

        const layout = {
            title: { text: 'OTA Tx Power Drop (Boxplot)', font: { color: isDark ? '#f8fafc' : '#0f172a', size: 16 } },
            grid: { rows: nChannels, columns: 1, pattern: 'independent' },
            autosize: true,
            hovermode: 'closest',
            margin: { t: 60, b: 80, l: 60, r: 20 },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { color: isDark ? '#94a3b8' : '#475569', family: 'Inter, sans-serif' },
            boxmode: 'group'
        };

        channels.forEach((ch, i) => {
            layout[`yaxis${i + 1}`] = { 
                title: ch, 
                zeroline: true, 
                zerolinecolor: isDark ? '#334155' : '#e2e8f0', 
                gridcolor: isDark ? '#1e293b' : '#f1f5f9'
            };
            layout[`xaxis${i + 1}`] = { 
                categoryorder: 'array', 
                categoryarray: categories,
                gridcolor: isDark ? '#1e293b' : '#f1f5f9',
                tickangle: 45,
                tickfont: { size: 10 }
            };
        });

        Plotly.newPlot(plotlyChart, traces, layout, { responsive: true });
    }

    let isolatedTrendSN = null;

    function renderTrendPlot(data, categories, channels) {
        const isDark = document.body.classList.contains('dark-mode');
        const traces = [];
        const nChannels = channels.length;

        channels.forEach((ch, chIdx) => {
            const chData = data.filter(d => d.Channel === ch);
            const sns = [...new Set(chData.map(d => d.SerialNumber))];
            
            sns.forEach(sn => {
                const subset = chData.filter(d => d.SerialNumber === sn);
                subset.sort((a, b) => categories.indexOf(a.CheckPoint) - categories.indexOf(b.CheckPoint));
                
                // Find source index for consistent coloring
                const source = subset[0]?.Source;
                const sIdx = currentData.sources.indexOf(source);
                
                const isIsolated = isolatedTrendSN === sn;
                const isDimmed = isolatedTrendSN !== null && !isIsolated;

                traces.push({
                    x: subset.map(d => d.CheckPoint),
                    y: subset.map(d => d.Delta),
                    name: sn,
                    mode: 'lines+markers',
                    type: 'scatter',
                    opacity: isIsolated ? 1.0 : (isDimmed ? 0.05 : 0.5),
                    line: { 
                        width: isIsolated ? 3 : 1.5, 
                        color: defaultColors[sIdx % defaultColors.length] 
                    },
                    marker: { 
                        size: isIsolated ? 6 : 4, 
                        color: defaultColors[sIdx % defaultColors.length] 
                    },
                    xaxis: `x${chIdx + 1}`,
                    yaxis: `y${chIdx + 1}`,
                    showlegend: false,
                    legendgroup: source,
                    hoverinfo: 'name+y+text',
                    text: subset.map(d => `SN: ${d.SerialNumber}<br>Source: ${d.Source}`)
                });
            });
        });

        const layout = {
            title: { text: 'Individual Unit Trends (Click a line to isolate)', font: { color: isDark ? '#f8fafc' : '#0f172a', size: 16 } },
            grid: { rows: nChannels, columns: 1, pattern: 'independent' },
            autosize: true,
            hovermode: 'closest',
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { color: isDark ? '#94a3b8' : '#475569', family: 'Inter, sans-serif' },
            margin: { t: 60, b: 80, l: 60, r: 20 }
        };

        channels.forEach((ch, i) => {
            layout[`yaxis${i + 1}`] = { 
                title: ch,
                gridcolor: isDark ? '#1e293b' : '#f1f5f9'
            };
            layout[`xaxis${i + 1}`] = { 
                categoryorder: 'array', 
                categoryarray: categories,
                gridcolor: isDark ? '#1e293b' : '#f1f5f9',
                tickangle: 45,
                tickfont: { size: 10 }
            };
        });

        Plotly.newPlot(plotlyChart, traces, layout, { responsive: true }).then(() => {
            plotlyChart.on('plotly_click', function(clickData) {
                if (currentChartType !== 'trend') return;
                
                const clickedSN = clickData.points[0].data.name;
                // Toggle isolation
                isolatedTrendSN = (isolatedTrendSN === clickedSN) ? null : clickedSN;
                
                const update = {
                    opacity: plotlyChart.data.map(t => isolatedTrendSN ? (t.name === isolatedTrendSN ? 1.0 : 0.05) : 0.5),
                    'line.width': plotlyChart.data.map(t => isolatedTrendSN ? (t.name === isolatedTrendSN ? 3 : 1.5) : 1.5),
                    'marker.size': plotlyChart.data.map(t => isolatedTrendSN ? (t.name === isolatedTrendSN ? 6 : 4) : 4)
                };
                
                Plotly.restyle(plotlyChart, update);
            });
        });
    }

    // Handle Window Resize to make sure Plotly resizes
    window.addEventListener('resize', () => {
        if (currentData) {
            Plotly.Plots.resize(plotlyChart);
        }
    });

    // Event Listeners for Dashboard Controls
    channelCheckboxes.forEach(cb => cb.addEventListener('change', renderChart));
    generateBtn.addEventListener('click', fetchData);
    refreshBtn.addEventListener('click', loadFiles);

    // Initial Load
    loadFiles();
});
