document.addEventListener('DOMContentLoaded', () => {
    const fileListEl = document.getElementById('fileList');
    const searchInput = document.getElementById('searchInput');
    const tagFiltersEl = document.getElementById('tagFilters');
    const selectAllBtn = document.getElementById('selectAllBtn');
    const deselectAllBtn = document.getElementById('deselectAllBtn');
    const refreshBtn = document.getElementById('refreshBtn');
    const generateBtn = document.getElementById('generateBtn');
    const tempUploadZone = document.getElementById('tempUploadZone');
    const tempUploadInput = document.getElementById('tempUploadInput');
    const rawUploadZone = document.getElementById('rawUploadZone');
    const rawUploadInput = document.getElementById('rawUploadInput');
    
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

    const store = {
        allFiles: [],
        currentData: null,
        chartType: 'boxplot',
        allTags: [],
        activeTagFilters: [],
        selectedCPs: [],
        isolatedTrendSN: null,
        editingFileName: null,
        editingTags: [],
        dataType: 'delta',
    };

    // Load files list
    function loadFiles() {
        const originalHTML = refreshBtn.innerHTML;
        refreshBtn.disabled = true;
        
        fetch('/api/files?t=' + new Date().getTime(), { cache: 'no-store' })
            .then(res => res.json())
            .then(data => {
                store.allFiles = data.files || [];
                store.allTags = data.all_tags || [];
                renderTagFilters(store.allTags);
                renderFiles(store.allFiles);
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
            if (store.activeTagFilters.includes(tag)) chip.classList.add('active');
            chip.textContent = tag;
            chip.onclick = () => {
                if (store.activeTagFilters.includes(tag)) {
                    store.activeTagFilters = store.activeTagFilters.filter(t => t !== tag);
                    chip.classList.remove('active');
                } else {
                    store.activeTagFilters.push(tag);
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
            const source = fileObj.source || 'raw';
            const fileTags = fileObj.tags || [];
            const parsed = fileObj.parsed || null;
            
            const item = document.createElement('div');
            item.className = 'file-item';
            item.dataset.name = fileName;
            item.dataset.tags = JSON.stringify(fileTags);
            item.title = fileName; // Full filename on hover
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = `file-${index}`;
            checkbox.value = fileId;
            checkbox.addEventListener('change', updateGenerateBtn);

            const infoDiv = document.createElement('div');
            infoDiv.className = 'file-info';

            // Line 1: Structured display name
            const displayLabel = document.createElement('label');
            displayLabel.htmlFor = `file-${index}`;
            if (parsed && parsed.display_parts && parsed.display_parts.length > 0) {
                displayLabel.textContent = parsed.display_parts.join(' · ');
            } else {
                // Fallback: strip prefix/suffix for cleaner display
                displayLabel.textContent = fileName
                    .replace(/^Organized_/, '')
                    .replace(/[-_]?OTA_Data.*$/i, '')
                    .replace(/[-_]?BT-OTA-[\d.]+.*$/i, '')
                    .replace(/\.csv$/i, '');
            }
            displayLabel.className = 'file-display-name';

            // Line 2: Tags only (no source badge for raw files)
            const tagsDiv = document.createElement('div');
            tagsDiv.className = 'file-tags';
            
            // Show source badge only for uploaded files
            if (source === 'upload') {
                const sourceBadge = document.createElement('span');
                sourceBadge.className = 'source-badge upload';
                sourceBadge.textContent = '临时';
                tagsDiv.appendChild(sourceBadge);
            }
            
            fileTags.forEach(tag => {
                // Skip "Uploaded" tag since we already show the badge
                if (tag === 'Uploaded') return;
                const tagSpan = document.createElement('span');
                tagSpan.className = 'mini-tag';
                tagSpan.textContent = tag;
                tagsDiv.appendChild(tagSpan);
            });

            infoDiv.appendChild(displayLabel);
            // Only add tags row if there are visible tags
            if (tagsDiv.children.length > 0) {
                infoDiv.appendChild(tagsDiv);
            }

            const editBtn = document.createElement('button');
            editBtn.className = 'edit-tags-btn';
            editBtn.innerHTML = '<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"></path></svg>';
            editBtn.disabled = source === 'upload';
            editBtn.title = source === 'upload' ? '临时文件不保存标签' : '编辑标签';
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
            const tagMatch = store.activeTagFilters.length === 0 || store.activeTagFilters.every(t => fileTags.includes(t));
            
            item.style.display = (textMatch && tagMatch) ? 'flex' : 'none';
        });
    }

    searchInput.addEventListener('input', applyFilters);

    function setUploadBusy(zone, isBusy) {
        zone.classList.toggle('busy', isBusy);
    }

    async function uploadFiles(files, endpoint, zone, input, successMessage) {
        const csvFiles = Array.from(files || []).filter(file => file.name.toLowerCase().endsWith('.csv'));
        if (csvFiles.length === 0) {
            alert('请选择 CSV 文件');
            return;
        }

        const formData = new FormData();
        csvFiles.forEach(file => formData.append('files', file));
        setUploadBusy(zone, true);

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                body: formData
            });
            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || '上传失败');
            }
            await loadFiles();
            if (successMessage) console.log(successMessage);
        } catch (error) {
            console.error(error);
            alert('上传失败: ' + error.message);
        } finally {
            setUploadBusy(zone, false);
            input.value = '';
        }
    }

    function bindUpload(zone, input, endpoint, successMessage) {
        zone.addEventListener('click', () => input.click());
        input.addEventListener('change', (e) => uploadFiles(e.target.files, endpoint, zone, input, successMessage));
        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            zone.classList.add('dragover');
        });
        zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');
            uploadFiles(e.dataTransfer.files, endpoint, zone, input, successMessage);
        });
    }

    bindUpload(tempUploadZone, tempUploadInput, '/api/upload', '临时数据上传完成');
    bindUpload(rawUploadZone, rawUploadInput, '/api/rawdata/upload', 'Raw Data 上传完成');

    // Upload panel toggle
    const uploadToggleBtn = document.getElementById('uploadToggleBtn');
    const uploadPanel = document.getElementById('uploadPanel');
    const uploadBar = uploadToggleBtn.parentElement;

    uploadToggleBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isCollapsed = uploadPanel.classList.contains('collapsed');
        uploadPanel.classList.toggle('collapsed', !isCollapsed);
    });

    // Close upload panel on outside click
    document.addEventListener('click', (e) => {
        if (!uploadPanel.contains(e.target) && !uploadToggleBtn.contains(e.target)) {
            uploadPanel.classList.add('collapsed');
        }
    });

    // Modal Logic
    function openTagModal(fileName, tags) {
        store.editingFileName = fileName;
        store.editingTags = [...tags];
        modalFileName.textContent = fileName;
        newTagInput.value = '';
        renderModalTags();
        tagModal.classList.remove('hidden');
        setTimeout(() => newTagInput.focus(), 50);
    }

    function closeTagModal() {
        tagModal.classList.add('hidden');
        store.editingFileName = null;
        store.editingTags = [];
    }

    function renderModalTags() {
        modalTagList.innerHTML = '';
        store.editingTags.forEach(tag => {
            const tagEl = document.createElement('div');
            tagEl.className = 'removable-tag';
            tagEl.innerHTML = `
                <span>${tag}</span>
                <button class="remove-tag-btn" data-tag="${tag}">&times;</button>
            `;
            tagEl.querySelector('.remove-tag-btn').onclick = () => {
                store.editingTags = store.editingTags.filter(t => t !== tag);
                renderModalTags();
            };
            modalTagList.appendChild(tagEl);
        });
    }

    newTagInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            const newTag = newTagInput.value.trim();
            if (newTag && !store.editingTags.includes(newTag)) {
                store.editingTags.push(newTag);
                renderModalTags();
                newTagInput.value = '';
            }
        }
    });

    closeModalBtn.addEventListener('click', closeTagModal);
    cancelTagBtn.addEventListener('click', closeTagModal);

    saveTagBtn.addEventListener('click', async () => {
        if (!store.editingFileName) return;
        const originalText = saveTagBtn.textContent;
        saveTagBtn.disabled = true;
        saveTagBtn.textContent = '保存中...';

        try {
            const res = await fetch('/api/tags', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: store.editingFileName, tags: store.editingTags })
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
        const dataType = document.getElementById('dataTypeSelect').value;

        if (selectedFiles.length === 0) return;

        store.dataType = dataType;
        emptyState.classList.add('hidden');
        resultContainer.classList.add('hidden');
        loading.classList.remove('hidden');
        generateBtn.disabled = true;

        try {
            const response = await fetch('/api/fetch_chart_data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ files: selectedFiles, includeFailData: includeFailData, data_type: dataType })
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || '获取数据失败');
            }

            store.currentData = await response.json();
            store.selectedCPs = [];
            renderSummary(store.currentData);
            renderCPSelector();
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
            store.chartType = e.currentTarget.dataset.type;
            if (store.currentData) renderChart();
        });
    });

    // ── CP Multi-Select Dropdown ──
    const cpMultiSelect = document.getElementById('cpMultiSelect');
    const cpSelectTrigger = document.getElementById('cpSelectTrigger');
    const cpSelectDropdown = document.getElementById('cpSelectDropdown');
    const cpSelectText = document.getElementById('cpSelectText');
    const cpAllCheckbox = document.getElementById('cpAll');
    const cpOptionList = document.getElementById('cpOptionList');

    function renderCPSelector() {
        const cpFilter = document.getElementById('cpFilter');

        if (!store.currentData || !store.currentData.unique_cps || store.currentData.unique_cps.length === 0) {
            cpFilter.classList.add('hidden');
            return;
        }

        cpFilter.classList.remove('hidden');

        // Populate checkboxes
        const allCPs = store.currentData.unique_cps;
        cpOptionList.innerHTML = '';
        allCPs.forEach(cp => {
            const label = document.createElement('label');
            label.className = 'multi-select-option';
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.value = cp;
            cb.checked = store.selectedCPs.includes(cp);
            cb.addEventListener('change', () => {
                if (cb.checked) {
                    store.selectedCPs = [...store.selectedCPs, cp];
                } else {
                    store.selectedCPs = store.selectedCPs.filter(c => c !== cp);
                }
                updateCPSelectState();
                renderChart();
            });
            label.appendChild(cb);
            label.appendChild(document.createTextNode(cp));
            cpOptionList.appendChild(label);
        });

        updateCPSelectState();
    }

    function updateCPSelectState() {
        const allCPs = store.currentData ? store.currentData.unique_cps : [];
        const selected = store.selectedCPs;

        if (selected.length === 0 || selected.length === allCPs.length) {
            cpSelectText.textContent = 'All';
            cpAllCheckbox.checked = true;
            cpAllCheckbox.indeterminate = false;
        } else {
            cpSelectText.textContent = `${selected.length} selected`;
            cpAllCheckbox.checked = false;
            cpAllCheckbox.indeterminate = true;
        }
    }

    cpSelectTrigger.addEventListener('click', (e) => {
        e.stopPropagation();
        cpSelectDropdown.classList.toggle('hidden');
        cpMultiSelect.classList.toggle('open');
    });

    cpAllCheckbox.addEventListener('change', () => {
        if (cpAllCheckbox.checked) {
            store.selectedCPs = [];
        } else {
            store.selectedCPs = [...store.currentData.unique_cps];
        }
        renderCPSelector();
        renderChart();
    });

    // Close dropdown on outside click
    document.addEventListener('click', (e) => {
        if (!cpMultiSelect.contains(e.target)) {
            cpSelectDropdown.classList.add('hidden');
            cpMultiSelect.classList.remove('open');
        }
    });

    // ── ResizeObserver: auto-resize Plotly whenever the chart container changes size ──
    let chartResizeObserver = null;
    function ensureChartResizeObserver() {
        if (chartResizeObserver) return;
        chartResizeObserver = new ResizeObserver(() => {
            if (store.currentData && plotlyChart && plotlyChart._fullLayout) {
                Plotly.Plots.resize(plotlyChart);
            }
        });
        chartResizeObserver.observe(plotlyChart);
    }

    function renderChart() {
        if (!store.currentData) return;

        const chartType = store.chartType;
        const selectedChannels = Array.from(channelCheckboxes)
            .filter(cb => cb.checked)
            .map(cb => cb.value);

        let filteredData = store.currentData.data.filter(d => selectedChannels.includes(d.Channel));

        // Apply CP filter — empty = show all
        if (store.selectedCPs.length > 0) {
            filteredData = filteredData.filter(d => store.selectedCPs.includes(d.CheckPoint));
        }

        // Remove previous click listeners to prevent duplicates
        if (plotlyChart.removeAllListeners) {
            plotlyChart.removeAllListeners('plotly_click');
        }

        // Filter categories to only those in the filtered data
        const activeCPs = store.selectedCPs.length > 0
            ? store.selectedCPs.filter(cp => filteredData.some(d => d.CheckPoint === cp))
            : store.currentData.unique_cps;

        if (chartType === 'boxplot') {
            renderBoxplot(filteredData, activeCPs, selectedChannels);
        } else if (chartType === 'trend') {
            renderTrendPlot(filteredData, activeCPs, selectedChannels);
        }

        // Start observing the chart container for size changes (CP chips toggle, flex relayout, etc.)
        ensureChartResizeObserver();
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
        if (store.currentData) renderChart();
    });

    const defaultColors = [
        '#2563eb', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', 
        '#ec4899', '#06b6d4', '#f97316', '#64748b', '#84cc16'
    ];

    function renderBoxplot(data, categories, channels) {
        const isDark = document.body.classList.contains('dark-mode');
        const isRaw = store.dataType === 'raw';
        const traces = [];
        const nChannels = channels.length;

        const yUnit = isRaw ? 'dBm' : 'dB';
        const chartTitle = isRaw ? 'Tx Power — Raw Measurement (Boxplot)' : 'OTA Tx Power Drop (Boxplot)';

        channels.forEach((ch, chIdx) => {
            store.currentData.sources.forEach((source, sIdx) => {
                const subset = data.filter(d => d.Channel === ch && d.Source === source);
                if (subset.length === 0) return;

                traces.push({
                    x: subset.map(d => d.CheckPoint),
                    y: subset.map(d => d.Delta),
                    name: source,
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
            title: { text: chartTitle, font: { color: isDark ? '#f8fafc' : '#0f172a', size: 16 } },
            grid: { rows: nChannels, columns: 1, pattern: 'independent' },
            autosize: true,
            hovermode: 'closest',
            margin: { t: 30, b: 30, l: 40, r: 10 },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { color: isDark ? '#94a3b8' : '#475569', family: 'Inter, sans-serif' },
            boxmode: 'group'
        };

        const limitValue = isRaw ? 2 : -6;
        const limitLabel = isRaw ? 'Limit: 2 dBm' : 'Limit: -6 dB';
        const limitColor = isDark ? '#f87171' : '#ef4444';

        layout.shapes = [];
        layout.annotations = [];

        channels.forEach((ch, i) => {
            layout[`yaxis${i + 1}`] = {
                title: `${ch} (${yUnit})`,
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
            // Horizontal limit line per subplot
            layout.shapes.push({
                type: 'line',
                x0: 0, x1: 1,
                xref: 'paper',
                y0: limitValue, y1: limitValue,
                yref: `y${i + 1}`,
                line: { color: limitColor, width: 2, dash: 'dash' }
            });
            layout.annotations.push({
                x: 1, y: limitValue,
                xref: 'paper', yref: `y${i + 1}`,
                text: limitLabel,
                showarrow: false,
                xanchor: 'right', yanchor: 'bottom',
                font: { color: limitColor, size: 10 }
            });
        });

        Plotly.newPlot(plotlyChart, traces, layout, { responsive: true, useResizeHandler: true }).then(() => {
            Plotly.Plots.resize(plotlyChart);
        });
    }

    function renderTrendPlot(data, categories, channels) {
        const isDark = document.body.classList.contains('dark-mode');
        const isRaw = store.dataType === 'raw';
        const traces = [];
        const nChannels = channels.length;

        const yUnit = isRaw ? 'dBm' : 'dB';
        const chartTitle = isRaw ? 'Individual Unit Trends — Raw Power (dBm)' : 'Individual Unit Trends — Tx Power Drop (Click a line to isolate)';

        channels.forEach((ch, chIdx) => {
            const chData = data.filter(d => d.Channel === ch);
            const sns = [...new Set(chData.map(d => d.SerialNumber))];
            
            sns.forEach(sn => {
                const subset = chData.filter(d => d.SerialNumber === sn);
                subset.sort((a, b) => categories.indexOf(a.CheckPoint) - categories.indexOf(b.CheckPoint));
                
                // Find source index for consistent coloring
                const source = subset[0]?.Source;
                const sIdx = store.currentData.sources.indexOf(source);
                
                const isIsolated = store.isolatedTrendSN === sn;
                const isDimmed = store.isolatedTrendSN !== null && !isIsolated;

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

        const limitValue = isRaw ? 2 : -6;
        const limitLabel = isRaw ? 'Limit: 2 dBm' : 'Limit: -6 dB';
        const limitColor = isDark ? '#f87171' : '#ef4444';

        const layout = {
            title: { text: chartTitle, font: { color: isDark ? '#f8fafc' : '#0f172a', size: 16 } },
            grid: { rows: nChannels, columns: 1, pattern: 'independent' },
            autosize: true,
            hovermode: 'closest',
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { color: isDark ? '#94a3b8' : '#475569', family: 'Inter, sans-serif' },
            margin: { t: 30, b: 30, l: 40, r: 10 },
            shapes: [],
            annotations: []
        };

        channels.forEach((ch, i) => {
            layout[`yaxis${i + 1}`] = {
                title: `${ch} (${yUnit})`,
                gridcolor: isDark ? '#1e293b' : '#f1f5f9'
            };
            layout[`xaxis${i + 1}`] = {
                categoryorder: 'array',
                categoryarray: categories,
                gridcolor: isDark ? '#1e293b' : '#f1f5f9',
                tickangle: 45,
                tickfont: { size: 10 }
            };
            // Horizontal limit line per subplot
            layout.shapes.push({
                type: 'line',
                x0: 0, x1: 1,
                xref: 'paper',
                y0: limitValue, y1: limitValue,
                yref: `y${i + 1}`,
                line: { color: limitColor, width: 2, dash: 'dash' }
            });
            layout.annotations.push({
                x: 1, y: limitValue,
                xref: 'paper', yref: `y${i + 1}`,
                text: limitLabel,
                showarrow: false,
                xanchor: 'right', yanchor: 'bottom',
                font: { color: limitColor, size: 10 }
            });
        });

        Plotly.newPlot(plotlyChart, traces, layout, { responsive: true, useResizeHandler: true }).then(() => {
            Plotly.Plots.resize(plotlyChart);
            plotlyChart.on('plotly_click', function(clickData) {
                if (store.chartType !== 'trend') return;
                
                const clickedSN = clickData.points[0].data.name;
                // Toggle isolation
                store.isolatedTrendSN = (store.isolatedTrendSN === clickedSN) ? null : clickedSN;
                
                const update = {
                    opacity: plotlyChart.data.map(t => store.isolatedTrendSN ? (t.name === store.isolatedTrendSN ? 1.0 : 0.05) : 0.5),
                    'line.width': plotlyChart.data.map(t => store.isolatedTrendSN ? (t.name === store.isolatedTrendSN ? 3 : 1.5) : 1.5),
                    'marker.size': plotlyChart.data.map(t => store.isolatedTrendSN ? (t.name === store.isolatedTrendSN ? 6 : 4) : 4)
                };
                
                Plotly.restyle(plotlyChart, update);
            });
        });
    }

    // Handle Window Resize to make sure Plotly resizes
    window.addEventListener('resize', () => {
        if (store.currentData) {
            Plotly.Plots.resize(plotlyChart);
        }
    });

    // Event Listeners for Dashboard Controls
    channelCheckboxes.forEach(cb => cb.addEventListener('change', renderChart));
    generateBtn.addEventListener('click', fetchData);
    refreshBtn.addEventListener('click', loadFiles);

    // Data type selector: re-fetch when switching delta ↔ raw
    document.getElementById('dataTypeSelect').addEventListener('change', () => {
        const hasSelection = document.querySelectorAll('.file-item input[type="checkbox"]:checked').length > 0;
        if (hasSelection) fetchData();
    });

    // Initial Load
    loadFiles();
});
