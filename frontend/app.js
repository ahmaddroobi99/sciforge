/**
 * SciForge Client Application Logic
 * Orchestrates real-time interactive lecture playback, compilation polling,
 * theme switching, simulation executions, and classroom projector integration.
 */

// Application State
const state = {
    currentProjectId: null,
    selectedSample: "kalman_filter",
    theme: "blueprint",
    persona: "engineer",
    audience: "graduate_students",
    duration: 600,
    resolution: "1080p",
    isPlaying: false,
    currentSceneIndex: 0,
    currentTime: 0,
    totalDuration: 600,
    projectData: null,
    animFrameId: null
};

// DOM Elements
const el = {
    dropZone: document.getElementById('drop-zone'),
    fileInput: document.getElementById('file-input'),
    btnBrowse: document.getElementById('btn-browse-file'),
    sampleChips: document.querySelectorAll('.sample-chip'),
    selectTheme: document.getElementById('select-theme'),
    selectPersona: document.getElementById('select-persona'),
    selectAudience: document.getElementById('select-audience'),
    selectDuration: document.getElementById('select-duration'),
    toggleBtns: document.querySelectorAll('.toggle-btn'),
    btnCompile: document.getElementById('btn-compile'),
    progressContainer: document.getElementById('progress-container'),
    progressBar: document.getElementById('progress-bar-fill'),
    progressText: document.getElementById('progress-status-text'),
    tabBtns: document.querySelectorAll('.tab-btn'),
    tabContents: document.querySelectorAll('.tab-content'),
    // Player elements
    masterVideo: document.getElementById('master-video'),
    interactiveStage: document.getElementById('interactive-stage'),
    stageCanvas: document.getElementById('stage-canvas'),
    stageThemeTag: document.getElementById('stage-theme-tag'),
    stageSceneTag: document.getElementById('stage-scene-tag'),
    stageTitle: document.getElementById('stage-title'),
    stageEquationBox: document.getElementById('stage-equation-box'),
    stageEquationRender: document.getElementById('stage-equation-render'),
    stageCodeBox: document.getElementById('stage-code-box'),
    stageCodeRender: document.getElementById('stage-code-render'),
    stageBullets: document.getElementById('stage-bullets'),
    stagePlotImg: document.getElementById('stage-plot-img'),
    stagePlotPlaceholder: document.getElementById('stage-plot-placeholder'),
    stageNarratorName: document.getElementById('stage-narrator-name'),
    stageCitation: document.getElementById('stage-citation'),
    sceneAudio: document.getElementById('scene-audio'),
    subtitleText: document.getElementById('subtitle-text'),
    btnPlayPause: document.getElementById('btn-play-pause'),
    iconPlay: document.getElementById('icon-play'),
    timelineSlider: document.getElementById('timeline-slider'),
    timeCurrent: document.getElementById('time-current'),
    timeTotal: document.getElementById('time-total'),
    sceneJumpPills: document.getElementById('scene-jump-pills'),
    btnFullscreen: document.getElementById('btn-fullscreen'),
    videoCompStatus: document.getElementById('video-comp-status'),
    btnDownloadVideo: document.getElementById('btn-download-video'),
    btnRender4k: document.getElementById('btn-render-4k'),
    // Scenes & Sim
    scenesList: document.getElementById('scenes-list'),
    scenesReviewStatus: document.getElementById('scenes-review-status'),
    btnCompileReviewed: document.getElementById('btn-compile-reviewed'),
    simCodeEditor: document.getElementById('simulation-code-editor'),
    simFullPlot: document.getElementById('sim-full-plot'),
    simMetricsBox: document.getElementById('sim-metrics-box'),
    btnRunCode: document.getElementById('btn-run-code'),
    kgNodesGrid: document.getElementById('kg-nodes-grid'),
    // Export Links
    linkOpenSlides: document.getElementById('link-open-slides'),
    linkDownloadMp4: document.getElementById('link-download-mp4'),
    linkDownloadLatex: document.getElementById('link-download-latex'),
    linkDownloadPy: document.getElementById('link-download-py'),
    ytTitleInput: document.getElementById('yt-title-input'),
    ytDescInput: document.getElementById('yt-desc-input'),
    // Classroom Modal
    btnClassroomQuick: document.getElementById('btn-classroom-quick'),
    classroomModal: document.getElementById('classroom-modal'),
    classroomIframe: document.getElementById('classroom-iframe'),
    btnCloseModal: document.getElementById('btn-close-modal')
};

// Initialize Canvas
const ctx = el.stageCanvas.getContext('2d');

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    setupEventListeners();
    setupCanvasAnimation();
    // Default initial sample loading
    initDefaultProject();
});

function setupEventListeners() {
    // Theme selection
    el.selectTheme.addEventListener('change', (e) => {
        state.theme = e.target.value;
        document.body.className = `theme-${state.theme}`;
        if (state.projectData && state.projectData.lecture_plan) {
            updateStageDisplay();
        }
    });

    // Persona selection
    el.selectPersona.addEventListener('change', (e) => {
        state.persona = e.target.value;
    });

    // Duration selection
    el.selectDuration.addEventListener('change', (e) => {
        state.duration = parseInt(e.target.value);
    });

    // Audience selection
    el.selectAudience.addEventListener('change', (e) => {
        state.audience = e.target.value;
    });

    // Resolution toggle buttons
    el.toggleBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            el.toggleBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.resolution = btn.dataset.res;
        });
    });

    // Sample paper chips
    el.sampleChips.forEach(chip => {
        chip.addEventListener('click', () => {
            el.sampleChips.forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            state.selectedSample = chip.dataset.sample;
        });
    });

    // Tab buttons
    el.tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.dataset.tab;
            el.tabBtns.forEach(b => b.classList.remove('active'));
            el.tabContents.forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(targetTab).classList.add('active');
            lucide.createIcons();
        });
    });

    // File Upload handling
    el.btnBrowse.addEventListener('click', () => el.fileInput.click());
    el.dropZone.addEventListener('click', (e) => {
        if (e.target !== el.btnBrowse) el.fileInput.click();
    });

    el.fileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        await uploadUserFile(file);
    });

    // Drag and Drop
    el.dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        el.dropZone.style.borderColor = 'var(--primary-color)';
    });
    el.dropZone.addEventListener('dragleave', () => {
        el.dropZone.style.borderColor = 'var(--border-color)';
    });
    el.dropZone.addEventListener('drop', async (e) => {
        e.preventDefault();
        el.dropZone.style.borderColor = 'var(--border-color)';
        if (e.dataTransfer.files.length > 0) {
            await uploadUserFile(e.dataTransfer.files[0]);
        }
    });

    // Compile Action Button
    el.btnCompile.addEventListener('click', triggerCompilation);
    el.btnCompileReviewed.addEventListener('click', triggerCompilation);

    // Player Controls
    el.btnPlayPause.addEventListener('click', togglePlayback);
    el.timelineSlider.addEventListener('input', (e) => {
        const pct = parseFloat(e.target.value);
        seekToPercent(pct);
    });

    // Fullscreen video
    el.btnFullscreen.addEventListener('click', () => {
        const cont = document.getElementById('video-container');
        if (!document.fullscreenElement) {
            cont.requestFullscreen();
        } else {
            document.exitFullscreen();
        }
    });

    // Execute Custom Python in Simulation tab
    el.btnRunCode.addEventListener('click', async () => {
        const code = el.simCodeEditor.value;
        if (!code || !state.currentProjectId) return;
        el.btnRunCode.innerHTML = '<i data-lucide="loader" class="spin"></i> Executing...';
        try {
            const resp = await fetch(`/api/project/${state.currentProjectId}/execute-python`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code })
            });
            const res = await resp.json();
            if (res.success && res.image) {
                el.simFullPlot.src = res.image;
                if (el.stagePlotImg) el.stagePlotImg.src = res.image;
            } else {
                alert(`Execution error: ${res.error}`);
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        } finally {
            el.btnRunCode.innerHTML = '<i data-lucide="play"></i> Execute Code';
            lucide.createIcons();
        }
    });

    // Classroom quick modal
    el.btnClassroomQuick.addEventListener('click', openClassroomModal);
    el.btnCloseModal.addEventListener('click', () => {
        el.classroomModal.style.display = 'none';
    });

    // Re-render 4K
    el.btnRender4k.addEventListener('click', async () => {
        if (!state.currentProjectId) return;
        el.btnRender4k.innerHTML = '<i data-lucide="loader" class="spin"></i> Rendering 4K...';
        try {
            const res = await fetch(`/api/project/${state.currentProjectId}/render-video?resolution=4K`, { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                alert("4K Video compilation complete!");
                el.videoCompStatus.innerText = "Master 4K Video Ready";
                el.btnDownloadVideo.disabled = false;
                el.btnDownloadVideo.onclick = () => window.open(data.video_url, '_blank');
            }
        } catch (e) {
            alert(`Render error: ${e.message}`);
        } finally {
            el.btnRender4k.innerHTML = '<i data-lucide="sparkles"></i> Render 4K via FFmpeg';
            lucide.createIcons();
        }
    });
}

async function initDefaultProject() {
    // Check system status
    try {
        const health = await (await fetch('/api/health')).json();
        document.getElementById('engine-status').innerText = health.status.toUpperCase();
        document.getElementById('ffmpeg-status').innerText = health.ffmpeg_installed ? 'READY (9.0)' : 'FALLBACK';
        const llmEl = document.getElementById('llm-status');
        llmEl.innerText = health.llm.available ? `${health.llm.provider.toUpperCase()} · ${health.llm.model}` : 'TEMPLATES';
        llmEl.title = health.llm.available ? 'Lectures are planned by the LLM' : `No LLM: ${health.llm.reason}`;
    } catch (e) {
        console.warn("Backend not yet responding, awaiting start...");
    }
}

async function uploadUserFile(file) {
    el.dropZone.querySelector('.drop-primary-text').innerText = `Uploading ${file.name}...`;
    try {
        // Create project first if needed
        const createRes = await fetch('/api/project/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: file.name.replace(/\.[^/.]+$/, ""),
                topic: file.name.replace(/\.[^/.]+$/, ""),
                theme: state.theme,
                persona: state.persona,
                audience: state.audience,
                target_duration: state.duration,
                resolution: state.resolution
            })
        });
        const proj = await createRes.json();
        state.currentProjectId = proj.id;

        // Upload file
        const formData = new FormData();
        formData.append('file', file);
        const upRes = await fetch(`/api/project/${proj.id}/upload-paper`, {
            method: 'POST',
            body: formData
        });
        const updated = await upRes.json();
        state.projectData = updated;

        el.dropZone.querySelector('.drop-primary-text').innerText = `Loaded: ${file.name}`;
        el.dropZone.querySelector('.drop-secondary-text').innerText = `${updated.document.num_pages} pages | ${updated.document.equations.length} equations extracted`;
        alert(`Successfully ingested ${file.name}! Now click "COMPILE SCIENTIFIC LECTURE".`);
    } catch (e) {
        alert(`Upload error: ${e.message}`);
        el.dropZone.querySelector('.drop-primary-text').innerText = 'Drop PDF, Scanned Notes, or Code';
    }
}

async function triggerCompilation() {
    el.btnCompile.disabled = true;
    el.progressContainer.style.display = 'flex';
    el.progressBar.style.width = '10%';
    el.progressText.innerText = 'Creating project workspace...';

    try {
        let projId = state.currentProjectId;

        // If not uploaded yet, create with chosen benchmark sample
        if (!projId) {
            const createResp = await fetch('/api/project/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: `Lecture: ${state.selectedSample.replace('_', ' ').toUpperCase()}`,
                    topic: state.selectedSample.replace('_', ' '),
                    theme: state.theme,
                    persona: state.persona,
                    audience: state.audience,
                    target_duration: state.duration,
                    resolution: state.resolution
                })
            });
            const proj = await createResp.json();
            projId = proj.id;
            state.currentProjectId = projId;

            // Load benchmark sample paper
            await fetch(`/api/project/${projId}/load-sample/${state.selectedSample}`, { method: 'POST' });
        }

        // Trigger compilation pipeline
        await fetch(`/api/project/${projId}/compile`, { method: 'POST' });

        // Poll pipeline status
        pollCompilationStatus(projId);

    } catch (err) {
        alert(`Compilation trigger error: ${err.message}`);
        el.btnCompile.disabled = false;
    }
}

async function pollCompilationStatus(projId) {
    const interval = setInterval(async () => {
        try {
            const resp = await fetch(`/api/project/${projId}`);
            if (!resp.ok) return;
            const proj = await resp.json();
            state.projectData = proj;

            el.progressBar.style.width = `${proj.progress_pct}%`;
            el.progressText.innerText = proj.status_message;

            if (proj.status === 'ready') {
                clearInterval(interval);
                el.btnCompile.disabled = false;
                el.progressText.innerText = "Compilation complete!";
                onCompilationSuccess(proj);
            } else if (proj.status === 'error') {
                clearInterval(interval);
                el.btnCompile.disabled = false;
                alert(`Compilation failed: ${proj.status_message}`);
            }
        } catch (e) {
            console.error("Polling error:", e);
        }
    }, 1000);
}

function onCompilationSuccess(proj) {
    const plan = proj.lecture_plan;
    state.totalDuration = plan.actual_duration_sec || state.duration;
    el.timeTotal.innerText = formatTime(state.totalDuration);

    // Update status badge
    el.videoCompStatus.innerText = proj.review_dirty
        ? "Scene changes need recompilation"
        : proj.video_path ? `Master ${proj.resolution} MP4 Ready` : "Draft Preview Ready";
    el.btnRender4k.disabled = Boolean(proj.review_dirty);
    el.btnDownloadVideo.disabled = !proj.video_path || Boolean(proj.review_dirty);
    el.scenesReviewStatus.innerText = proj.review_dirty
        ? "Saved scene edits are not reflected in audio or exports yet. Compile the reviewed lecture to refresh them."
        : "Review narration and equations, save scene edits, then compile to refresh the teaching pack.";

    if (proj.video_path) {
        el.btnDownloadVideo.disabled = false;
        el.btnDownloadVideo.onclick = () => window.open(proj.video_path, '_blank');
        el.linkDownloadMp4.href = proj.video_path;
        el.linkDownloadMp4.download = `lecture_${proj.resolution}.mp4`;
        el.linkDownloadMp4.removeAttribute('aria-disabled');
    }

    // Populate Scene Jump Pills
    el.sceneJumpPills.innerHTML = '';
    plan.scenes.forEach((scene, idx) => {
        const pill = document.createElement('button');
        pill.className = `scene-pill ${idx === 0 ? 'active' : ''}`;
        pill.innerText = `Scene ${scene.index}`;
        pill.title = scene.title;
        pill.addEventListener('click', () => jumpToScene(idx));
        el.sceneJumpPills.appendChild(pill);
    });

    // Populate Scenes Director Tab
    populateScenesTab(plan);

    // Populate Simulation Tab
    if (proj.simulation_output) {
        el.simCodeEditor.value = proj.simulation_output.runnable_python_code || "";
        if (proj.simulation_output.plot_url) {
            el.simFullPlot.src = proj.simulation_output.plot_url;
            el.stagePlotImg.src = proj.simulation_output.plot_url;
            el.stagePlotImg.style.display = 'block';
            el.stagePlotPlaceholder.style.display = 'none';
        }
        // Metrics
        el.simMetricsBox.innerHTML = '';
        if (proj.simulation_output.metrics) {
            for (const [k, v] of Object.entries(proj.simulation_output.metrics)) {
                const item = document.createElement('div');
                item.className = 'metric-item';
                item.innerHTML = `${k.replace(/_/g, ' ')}: <strong>${v}</strong>`;
                el.simMetricsBox.appendChild(item);
            }
        }
    }

    // Populate Knowledge Graph Tab
    if (proj.knowledge_graph) {
        populateKnowledgeGraph(proj.knowledge_graph);
    }

    // Populate Exports
    if (proj.slides_path) {
        el.linkOpenSlides.href = proj.slides_path;
        el.linkOpenSlides.removeAttribute('aria-disabled');
        el.btnClassroomQuick.onclick = () => openClassroomModal(proj.slides_path);
    }
    if (proj.latex_path) {
        el.linkDownloadLatex.href = proj.latex_path;
        el.linkDownloadLatex.removeAttribute('aria-disabled');
    }
    el.linkDownloadPy.href = `/outputs/${proj.id}/simulation.py`;

    if (plan.youtube_metadata) {
        el.ytTitleInput.value = plan.youtube_metadata.title || "";
        el.ytDescInput.value = plan.youtube_metadata.description || "";
    }

    // Switch to first scene
    state.currentSceneIndex = 0;
    updateStageDisplay();

    lucide.createIcons();
}

function populateScenesTab(plan) {
    el.scenesList.replaceChildren();
    plan.scenes.forEach((scene) => {
        const card = document.createElement('div');
        card.className = 'scene-item-card';

        const header = document.createElement('div');
        header.className = 'scene-card-header';
        const badge = document.createElement('span');
        badge.className = 'scene-index-badge';
        badge.textContent = `SCENE ${scene.index.toString().padStart(2, '0')}`;
        const type = document.createElement('span');
        type.className = 'scene-type-tag';
        type.textContent = `${scene.type.replace(/_/g, ' ')} [${scene.duration}s]`;
        const previewButton = document.createElement('button');
        previewButton.className = 'btn btn-outline btn-sm btn-play-scene';
        previewButton.type = 'button';
        previewButton.innerHTML = '<i data-lucide="play"></i> Preview Scene';
        previewButton.addEventListener('click', () => {
            jumpToScene(scene.index - 1);
            el.tabBtns[0].click();
            playAudioForCurrentScene();
        });
        header.append(badge, type, previewButton);

        const titleLabel = document.createElement('label');
        titleLabel.className = 'input-label';
        titleLabel.textContent = 'Scene title';
        const titleInput = document.createElement('input');
        titleInput.className = 'form-input scene-title-input';
        titleInput.dataset.field = 'title';
        titleInput.value = scene.title;

        const equationLabel = document.createElement('label');
        equationLabel.className = 'input-label';
        equationLabel.textContent = 'Equation (LaTeX)';
        const equationInput = document.createElement('textarea');
        equationInput.className = 'scene-script-textarea scene-equation-input';
        equationInput.dataset.field = 'equation';
        equationInput.rows = 2;
        equationInput.placeholder = 'No equation';
        equationInput.value = scene.equation || '';

        const narrationLabel = document.createElement('label');
        narrationLabel.className = 'input-label';
        narrationLabel.textContent = 'Spoken narration';
        const narrationInput = document.createElement('textarea');
        narrationInput.className = 'scene-script-textarea';
        narrationInput.dataset.field = 'narration';
        narrationInput.rows = 5;
        narrationInput.value = scene.narration;

        const metadata = document.createElement('div');
        metadata.className = 'scene-review-metadata';
        const citation = document.createElement('span');
        citation.textContent = `Citation: ${scene.citation || 'None'}`;
        const timecode = document.createElement('span');
        timecode.textContent = `Timecode: ${scene.timestamp_start}s - ${scene.timestamp_end}s`;
        metadata.append(citation, timecode);

        const actions = document.createElement('div');
        actions.className = 'scene-review-actions';
        const saveButton = document.createElement('button');
        saveButton.className = 'btn btn-primary btn-sm';
        saveButton.type = 'button';
        saveButton.innerHTML = '<i data-lucide="save"></i> Save Scene';
        saveButton.addEventListener('click', () => saveSceneReview(card, scene.id, scene.index - 1));
        const regenerateButton = document.createElement('button');
        regenerateButton.className = 'btn btn-outline btn-sm';
        regenerateButton.type = 'button';
        regenerateButton.innerHTML = '<i data-lucide="refresh-cw"></i> Regenerate Scene';
        regenerateButton.title = 'Ask the configured model to revise this scene';
        regenerateButton.addEventListener('click', () => regenerateSceneReview(card, scene.id, scene.index - 1));
        actions.append(saveButton, regenerateButton);

        card.append(header, titleLabel, titleInput, equationLabel, equationInput, narrationLabel, narrationInput, metadata, actions);
        el.scenesList.appendChild(card);
    });

    lucide.createIcons();
}

async function saveSceneReview(card, sceneId, sceneIndex) {
    await submitSceneReview(card, sceneId, sceneIndex, 'PUT', {
        title: card.querySelector('[data-field="title"]').value,
        equation: card.querySelector('[data-field="equation"]').value || null,
        narration: card.querySelector('[data-field="narration"]').value
    });
}

async function regenerateSceneReview(card, sceneId, sceneIndex) {
    await submitSceneReview(card, sceneId, sceneIndex, 'POST');
}

async function submitSceneReview(card, sceneId, sceneIndex, method, body) {
    card.querySelectorAll('button').forEach(button => { button.disabled = true; });
    el.scenesReviewStatus.textContent = method === 'POST' ? 'Regenerating this scene…' : 'Saving scene…';
    try {
        const response = await fetch(`/api/project/${state.currentProjectId}/scenes/${sceneId}${method === 'POST' ? '/regenerate' : ''}`, {
            method,
            headers: body ? { 'Content-Type': 'application/json' } : {},
            body: body ? JSON.stringify(body) : undefined
        });
        const project = await response.json();
        if (!response.ok) throw new Error(project.detail || 'Scene update failed');
        showReviewedProject(project, sceneIndex);
    } catch (error) {
        el.scenesReviewStatus.textContent = error.message;
    } finally {
        card.querySelectorAll('button').forEach(button => { button.disabled = false; });
        lucide.createIcons();
    }
}

function showReviewedProject(project, sceneIndex) {
    state.projectData = project;
    state.totalDuration = project.lecture_plan.actual_duration_sec || state.duration;
    state.currentSceneIndex = Math.min(sceneIndex, project.lecture_plan.scenes.length - 1);
    el.timeTotal.textContent = formatTime(state.totalDuration);
    populateScenesTab(project.lecture_plan);
    project.lecture_plan.scenes.forEach((scene, index) => {
        const pill = el.sceneJumpPills.children[index];
        if (pill) {
            pill.textContent = `Scene ${scene.index}`;
            pill.title = scene.title;
        }
    });
    el.videoCompStatus.textContent = 'Scene changes need recompilation';
    el.scenesReviewStatus.textContent = 'Scene saved. Compile the reviewed lecture to refresh narration and exports.';
    el.btnDownloadVideo.disabled = true;
    el.btnDownloadVideo.onclick = null;
    el.btnRender4k.disabled = true;
    for (const link of [el.linkOpenSlides, el.linkDownloadMp4, el.linkDownloadLatex]) {
        link.removeAttribute('href');
        link.setAttribute('aria-disabled', 'true');
    }
    el.ytTitleInput.value = '';
    el.ytDescInput.value = '';
    updateStageDisplay();
    updateTimelineUI();
}

function populateKnowledgeGraph(kg) {
    el.kgNodesGrid.innerHTML = '';
    kg.nodes.forEach(node => {
        const card = document.createElement('div');
        card.className = 'concept-node-card';
        card.innerHTML = `
            <span class="node-type-pill type-${node.type}">${node.type}</span>
            <h4 style="font-size: 1rem; color: #fff;">${node.name}</h4>
            <p style="font-size: 0.8rem; color: var(--text-muted);">${node.description}</p>
            ${node.formula ? `<div style="font-size: 0.9rem; color: var(--secondary-accent); margin-top: 4px;">$$${node.formula}$$</div>` : ''}
            <div style="font-size: 0.7rem; color: var(--primary-color); margin-top: auto;">Source Page: ${node.source_page || 1}</div>
        `;
        el.kgNodesGrid.appendChild(card);
    });

    if (window.renderMathInElement) {
        renderMathInElement(el.kgNodesGrid);
    }
}

function jumpToScene(idx) {
    if (!state.projectData || !state.projectData.lecture_plan) return;
    const scenes = state.projectData.lecture_plan.scenes;
    if (idx < 0 || idx >= scenes.length) return;

    state.currentSceneIndex = idx;
    const scene = scenes[idx];
    state.currentTime = scene.timestamp_start;
    updateStageDisplay();
    updateTimelineUI();

    // Update active pill
    document.querySelectorAll('.scene-pill').forEach((p, i) => {
        p.classList.toggle('active', i === idx);
    });

    if (state.isPlaying) {
        playAudioForCurrentScene();
    }
}

function updateStageDisplay() {
    if (!state.projectData || !state.projectData.lecture_plan) return;
    const plan = state.projectData.lecture_plan;
    const scene = plan.scenes[state.currentSceneIndex];
    if (!scene) return;

    el.stageThemeTag.innerText = `SCIFORGE // ${state.theme.toUpperCase()}`;
    el.stageSceneTag.innerText = `SCENE ${scene.index.toString().padStart(2, '0')} / ${plan.scenes.length.toString().padStart(2, '0')} [${scene.type.toUpperCase()}]`;
    el.stageTitle.innerText = scene.title;
    el.stageNarratorName.innerText = plan.persona.toUpperCase().replace('_', ' ');
    el.stageCitation.innerText = scene.citation || '[Paper Source]';
    el.subtitleText.innerText = scene.narration;

    // Equations
    if (scene.equation) {
        el.stageEquationBox.style.display = 'block';
        if (window.katex) {
            try {
                katex.render(scene.equation, el.stageEquationRender, { displayMode: true, throwOnError: false });
            } catch (e) {
                el.stageEquationRender.innerText = scene.equation;
            }
        } else {
            el.stageEquationRender.innerText = scene.equation;
        }
    } else {
        el.stageEquationBox.style.display = 'none';
    }

    // Code
    if (scene.code_snippet) {
        el.stageCodeBox.style.display = 'block';
        el.stageCodeRender.innerText = scene.code_snippet;
    } else {
        el.stageCodeBox.style.display = 'none';
    }

    // Bullets
    el.stageBullets.innerHTML = '';
    scene.bullet_points.forEach(bp => {
        const li = document.createElement('li');
        li.innerText = bp;
        el.stageBullets.appendChild(li);
    });

    // Plot image
    if (scene.figure_url && state.projectData.simulation_output) {
        el.stagePlotImg.src = state.projectData.simulation_output.plot_url;
        el.stagePlotImg.style.display = 'block';
        el.stagePlotPlaceholder.style.display = 'none';
    }
}

function togglePlayback() {
    if (!state.projectData || !state.projectData.lecture_plan) {
        alert("Please compile or load a lecture first.");
        return;
    }

    state.isPlaying = !state.isPlaying;
    if (state.isPlaying) {
        el.iconPlay.setAttribute('data-lucide', 'pause');
        playAudioForCurrentScene();
    } else {
        el.iconPlay.setAttribute('data-lucide', 'play');
        el.sceneAudio.pause();
    }
    lucide.createIcons();
}

function playAudioForCurrentScene() {
    const scenes = state.projectData.lecture_plan.scenes;
    const scene = scenes[state.currentSceneIndex];
    if (scene.audio_file) {
        el.sceneAudio.src = scene.audio_file;
        el.sceneAudio.play().catch(e => console.log("Audio play error:", e));

        el.sceneAudio.onended = () => {
            if (state.currentSceneIndex < scenes.length - 1) {
                jumpToScene(state.currentSceneIndex + 1);
            } else {
                state.isPlaying = false;
                el.iconPlay.setAttribute('data-lucide', 'play');
                lucide.createIcons();
            }
        };

        el.sceneAudio.ontimeupdate = () => {
            const sceneTime = el.sceneAudio.currentTime;
            state.currentTime = scene.timestamp_start + sceneTime;
            updateTimelineUI();
        };
    }
}

function seekToPercent(pct) {
    if (!state.projectData || !state.projectData.lecture_plan) return;
    const scenes = state.projectData.lecture_plan.scenes;
    const targetTime = (pct / 100) * state.totalDuration;
    state.currentTime = targetTime;

    // Find corresponding scene
    for (let i = 0; i < scenes.length; i++) {
        if (targetTime >= scenes[i].timestamp_start && targetTime <= scenes[i].timestamp_end) {
            state.currentSceneIndex = i;
            break;
        }
    }
    updateStageDisplay();
    updateTimelineUI();

    if (state.isPlaying) {
        playAudioForCurrentScene();
    }
}

function updateTimelineUI() {
    el.timeCurrent.innerText = formatTime(state.currentTime);
    const pct = (state.currentTime / state.totalDuration) * 100;
    el.timelineSlider.value = pct;
}

function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function openClassroomModal(url) {
    const targetUrl = url || (state.projectData && state.projectData.slides_path);
    if (!targetUrl) {
        alert("Classroom deck not yet compiled. Click 'Compile Scientific Lecture' first.");
        return;
    }
    el.classroomIframe.src = targetUrl;
    el.classroomModal.style.display = 'flex';
    lucide.createIcons();
}

// Background Canvas Dynamic Grid & Particles
function setupCanvasAnimation() {
    let t = 0;
    function renderGrid() {
        ctx.clearRect(0, 0, el.stageCanvas.width, el.stageCanvas.height);
        const w = el.stageCanvas.width;
        const h = el.stageCanvas.height;

        // Theme colors
        let strokeColor = 'rgba(0, 173, 181, 0.12)';
        if (state.theme === 'laboratory') strokeColor = 'rgba(16, 185, 129, 0.1)';
        if (state.theme === 'chalkboard') strokeColor = 'rgba(255, 255, 255, 0.05)';
        if (state.theme === 'expedition') strokeColor = 'rgba(245, 158, 11, 0.1)';

        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = 1;

        // Grid spacing
        const step = 40;
        ctx.beginPath();
        for (let x = 0; x < w; x += step) {
            ctx.moveTo(x, 0);
            ctx.lineTo(x, h);
        }
        for (let y = 0; y < h; y += step) {
            ctx.moveTo(0, y);
            ctx.lineTo(w, y);
        }
        ctx.stroke();

        // Subtle oscillating technical coordinate lines
        if (state.theme === 'blueprint' || state.theme === 'laboratory') {
            const waveY = h * 0.75 + Math.sin(t * 0.03) * 15;
            ctx.beginPath();
            ctx.strokeStyle = 'rgba(0, 173, 181, 0.3)';
            ctx.lineWidth = 1.5;
            ctx.setLineDash([8, 8]);
            ctx.moveTo(0, waveY);
            ctx.lineTo(w, waveY);
            ctx.stroke();
            ctx.setLineDash([]);
        }

        t += 1;
        state.animFrameId = requestAnimationFrame(renderGrid);
    }
    renderGrid();
}
