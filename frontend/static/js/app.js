/**
 * DocuScan AI - Main Frontend Application Logic
 * Integrates Projects, Persons, Batch Camera/Scans, Azure Storage & Azure Content Understanding.
 */

class DocuScanApp {
  constructor() {
    this.projects = [];
    this.currentProject = null;
    this.currentPerson = null;
    this.currentDoc = null;
    this.currentRotation = 0;
    this.stagedFiles = [];
    this.stagedAdditionalFiles = [];
    this.systemStatus = null;
    this.activeDocCategoryFilter = "all";

    this.init();
  }

  async init() {
    await this.fetchSystemStatus();
    await this.fetchProjects();
    this.initLucide();
  }

  initLucide() {
    if (window.lucide) {
      window.lucide.createIcons();
    }
  }

  showToast(message, isError = false) {
    const toast = document.getElementById("toast");
    const toastMsg = document.getElementById("toast-message");
    const toastIcon = document.getElementById("toast-icon");
    if (!toast) return;

    toastMsg.innerText = message;
    if (isError) {
      toast.firstElementChild.className = "bg-rose-900 border border-rose-700 text-white px-4 py-3 rounded-xl shadow-2xl flex items-center space-x-3 text-sm";
      toastIcon.setAttribute("data-lucide", "alert-circle");
    } else {
      toast.firstElementChild.className = "bg-slate-800 border border-slate-700 text-white px-4 py-3 rounded-xl shadow-2xl flex items-center space-x-3 text-sm";
      toastIcon.setAttribute("data-lucide", "check-circle");
    }
    this.initLucide();

    toast.classList.remove("translate-y-20", "opacity-0");
    setTimeout(() => {
      toast.classList.add("translate-y-20", "opacity-0");
    }, 3500);
  }

  // ============================================================================
  // Cloud & System Status
  // ============================================================================
  async fetchSystemStatus() {
    try {
      const res = await fetch("/api/system/status");
      if (res.ok) {
        this.systemStatus = await res.json();
        this.renderSystemBadges();
      }
    } catch (e) {
      console.warn("Could not fetch system status:", e);
    }
  }

  renderSystemBadges() {
    if (!this.systemStatus) return;

    // Database Badge
    const db = this.systemStatus.database;
    const dotDb = document.getElementById("dot-db");
    const textDb = document.getElementById("text-db");
    if (dotDb && textDb) {
      dotDb.className = db.connected ? "w-2 h-2 rounded-full bg-emerald-400" : "w-2 h-2 rounded-full bg-amber-400";
      textDb.innerText = db.connected ? "Azure SQL: Connected" : "Azure SQL: Local Dev";
    }

    // Storage Badge
    const st = this.systemStatus.storage;
    const dotSt = document.getElementById("dot-storage");
    const textSt = document.getElementById("text-storage");
    if (dotSt && textSt) {
      dotSt.className = st.connected ? "w-2 h-2 rounded-full bg-emerald-400" : "w-2 h-2 rounded-full bg-amber-400";
      textSt.innerText = st.connected ? "Azure Storage: Active" : "Storage: Local Dev";
    }

    // Content Understanding Badge
    const cu = this.systemStatus.content_understanding;
    const dotCu = document.getElementById("dot-cu");
    const textCu = document.getElementById("text-cu");
    if (dotCu && textCu) {
      dotCu.className = cu.connected ? "w-2 h-2 rounded-full bg-emerald-400" : "w-2 h-2 rounded-full bg-indigo-400";
      textCu.innerText = cu.connected ? "Azure Content Understanding" : "Intelligent Analyzer";
    }
  }

  openSystemModal() {
    const modal = document.getElementById("modal-system");
    const body = document.getElementById("system-status-body");
    if (!modal || !body) return;

    if (!this.systemStatus) {
      body.innerHTML = "<p class='text-slate-400'>Loading status...</p>";
    } else {
      const db = this.systemStatus.database;
      const st = this.systemStatus.storage;
      const cu = this.systemStatus.content_understanding;
      const ag = this.systemStatus.ai_agent;

      body.innerHTML = `
        <div class="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
          <div class="flex items-center justify-between mb-1">
            <span class="font-bold text-white flex items-center space-x-1.5">
              <span class="w-2 h-2 rounded-full ${db.connected ? 'bg-emerald-400' : 'bg-amber-400'}"></span>
              <span>1. Azure SQL Server Database</span>
            </span>
            <span class="text-[11px] px-2 py-0.5 rounded ${db.connected ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'}">
              ${db.provider}
            </span>
          </div>
          <div class="text-slate-400 text-[11px]">Server: <span class="text-slate-200 font-mono">${db.details.server}</span></div>
          <div class="text-slate-400 text-[11px]">Database: <span class="text-slate-200 font-mono">${db.details.database}</span></div>
        </div>

        <div class="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
          <div class="flex items-center justify-between mb-1">
            <span class="font-bold text-white flex items-center space-x-1.5">
              <span class="w-2 h-2 rounded-full ${st.connected ? 'bg-emerald-400' : 'bg-amber-400'}"></span>
              <span>2. Azure Account Storage (Blob)</span>
            </span>
            <span class="text-[11px] px-2 py-0.5 rounded ${st.connected ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'}">
              ${st.provider}
            </span>
          </div>
          <div class="text-slate-400 text-[11px]">Container: <span class="text-slate-200 font-mono">${st.details.container}</span></div>
          <div class="text-slate-400 text-[11px]">Account: <span class="text-slate-200 font-mono">${st.details.account || 'Local Fallback'}</span></div>
        </div>

        <div class="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
          <div class="flex items-center justify-between mb-1">
            <span class="font-bold text-white flex items-center space-x-1.5">
              <span class="w-2 h-2 rounded-full ${cu.connected ? 'bg-emerald-400' : 'bg-indigo-400'}"></span>
              <span>3. Azure Content Understanding Service</span>
            </span>
            <span class="text-[11px] px-2 py-0.5 rounded ${cu.connected ? 'bg-emerald-500/10 text-emerald-400' : 'bg-indigo-500/10 text-indigo-400'}">
              ${cu.provider}
            </span>
          </div>
          <div class="text-slate-400 text-[11px]">Endpoint: <span class="text-slate-200 font-mono">${cu.details.endpoint}</span></div>
          <div class="text-slate-400 text-[11px]">Handwriting, Stamps & Signature Detection: <span class="text-emerald-400 font-semibold">Active</span></div>
        </div>

        <div class="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
          <div class="flex items-center justify-between mb-1">
            <span class="font-bold text-white flex items-center space-x-1.5">
              <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
              <span>4. AI Document Verification Agent</span>
            </span>
            <span class="text-[11px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400">
              Operational
            </span>
          </div>
          <div class="text-slate-400 text-[11px]">Reasoning Engine: <span class="text-slate-200">Rule-based Cross-audit + Contextual Q&A</span></div>
        </div>
      `;
    }

    modal.classList.remove("hidden");
    this.initLucide();
  }

  closeSystemModal() {
    const modal = document.getElementById("modal-system");
    if (modal) modal.classList.add("hidden");
  }

  // ============================================================================
  // Navigation & Views
  // ============================================================================
  showProjectsView() {
    document.getElementById("view-projects").classList.remove("hidden");
    document.getElementById("view-project-detail").classList.add("hidden");
    document.getElementById("view-person-dossier").classList.add("hidden");
    this.currentProject = null;
    this.currentPerson = null;
    this.fetchProjects();
  }

  async showProjectDetail(projectId) {
    document.getElementById("view-projects").classList.add("hidden");
    document.getElementById("view-project-detail").classList.remove("hidden");
    document.getElementById("view-person-dossier").classList.add("hidden");

    try {
      const res = await fetch(`/api/projects/${projectId}`);
      if (res.ok) {
        this.currentProject = await res.json();
        this.renderProjectDetail();
      }
    } catch (e) {
      this.showToast("Failed to load project details", true);
    }
  }

  async showPersonDossier(personId) {
    document.getElementById("view-projects").classList.add("hidden");
    document.getElementById("view-project-detail").classList.add("hidden");
    document.getElementById("view-person-dossier").classList.remove("hidden");

    try {
      const res = await fetch(`/api/persons/${personId}`);
      if (res.ok) {
        this.currentPerson = await res.json();
        this.renderPersonDossier();
      }
    } catch (e) {
      this.showToast("Failed to load person dossier", true);
    }
  }

  backToProjectDetail() {
    if (this.currentProject) {
      this.showProjectDetail(this.currentProject.id);
    } else {
      this.showProjectsView();
    }
  }

  // ============================================================================
  // Projects Management
  // ============================================================================
  async fetchProjects() {
    try {
      const res = await fetch("/api/projects");
      if (res.ok) {
        this.projects = await res.json();
        this.renderProjectsGrid();
        this.updateStats();
      }
    } catch (e) {
      console.error("Error fetching projects:", e);
    }
  }

  updateStats() {
    const totalProjects = this.projects.length;
    let totalPersons = 0;
    let totalDocs = 0;
    this.projects.forEach(p => {
      totalPersons += p.persons_count || 0;
      totalDocs += p.documents_count || 0;
    });

    const elP = document.getElementById("stat-total-projects");
    const elU = document.getElementById("stat-total-persons");
    const elD = document.getElementById("stat-total-docs");
    if (elP) elP.innerText = totalProjects;
    if (elU) elU.innerText = totalPersons;
    if (elD) elD.innerText = totalDocs;
  }

  renderProjectsGrid(projectsToRender = this.projects) {
    const grid = document.getElementById("projects-grid");
    const empty = document.getElementById("projects-empty");
    const countEl = document.getElementById("projects-count");
    if (!grid || !empty) return;

    if (countEl) countEl.innerText = projectsToRender.length;

    if (projectsToRender.length === 0) {
      grid.innerHTML = "";
      empty.classList.remove("hidden");
      return;
    }

    empty.classList.add("hidden");
    grid.innerHTML = projectsToRender.map(p => {
      const typesList = p.person_types || [];
      const typesChips = typesList.slice(0, 3).map(t => `
        <span class="px-2 py-0.5 rounded-md text-[11px] font-medium bg-slate-800 text-slate-300 border border-slate-700/80">
          ${t}
        </span>
      `).join("") + (typesList.length > 3 ? `<span class="text-[11px] text-slate-400">+${typesList.length - 3}</span>` : "");

      return `
        <div class="bg-slate-900 border border-slate-800 hover:border-azure-500/50 rounded-2xl p-5 shadow-lg flex flex-col justify-between transition-all group">
          <div>
            <div class="flex items-start justify-between gap-3">
              <div class="w-10 h-10 rounded-xl bg-azure-500/10 text-azure-400 border border-azure-500/20 flex items-center justify-center font-bold">
                <i data-lucide="folder" class="w-5 h-5"></i>
              </div>
              <div class="flex items-center space-x-1">
                <button onclick="app.openProjectModal(app.getProjectById(${p.id}))" title="Edit Project" class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition">
                  <i data-lucide="edit-2" class="w-4 h-4"></i>
                </button>
                <button onclick="app.deleteProject(${p.id}, event)" title="Delete Project" class="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition">
                  <i data-lucide="trash-2" class="w-4 h-4"></i>
                </button>
              </div>
            </div>

            <h3 class="text-base font-bold text-white mt-3.5 group-hover:text-azure-400 transition cursor-pointer" onclick="app.showProjectDetail(${p.id})">
              ${p.title}
            </h3>
            <p class="text-xs text-slate-400 mt-1 line-clamp-2 leading-relaxed">
              ${p.description || "No description provided."}
            </p>

            <!-- Types of People -->
            <div class="mt-4 pt-3 border-t border-slate-800/80">
              <div class="text-[10px] text-slate-400 uppercase tracking-wider font-semibold mb-1.5">Manages Documents For:</div>
              <div class="flex flex-wrap items-center gap-1.5">
                ${typesChips || '<span class="text-xs text-slate-500">General</span>'}
              </div>
            </div>
          </div>

          <div class="mt-5 pt-3.5 border-t border-slate-800 flex items-center justify-between text-xs">
            <div class="flex items-center space-x-3 text-slate-400">
              <span class="flex items-center space-x-1">
                <i data-lucide="users" class="w-3.5 h-3.5 text-azure-400"></i>
                <span class="font-medium text-white">${p.persons_count || 0}</span>
              </span>
              <span class="flex items-center space-x-1">
                <i data-lucide="file-check" class="w-3.5 h-3.5 text-indigo-400"></i>
                <span class="font-medium text-white">${p.documents_count || 0}</span>
              </span>
            </div>
            <button onclick="app.showProjectDetail(${p.id})" class="text-azure-400 hover:text-azure-300 font-semibold flex items-center space-x-1 text-xs">
              <span>Open Project</span>
              <i data-lucide="chevron-right" class="w-3.5 h-3.5"></i>
            </button>
          </div>
        </div>
      `;
    }).join("");

    this.initLucide();
  }

  getProjectById(id) {
    return this.projects.find(p => p.id === id);
  }

  filterProjects() {
    const query = (document.getElementById("projects-search")?.value || "").toLowerCase();
    const filtered = this.projects.filter(p => 
      p.title.toLowerCase().includes(query) || (p.description && p.description.toLowerCase().includes(query))
    );
    this.renderProjectsGrid(filtered);
  }

  openProjectModal(project = null) {
    const modal = document.getElementById("modal-project");
    const title = document.getElementById("modal-project-title");
    const formId = document.getElementById("project-form-id");
    const formTitle = document.getElementById("project-form-title");
    const formDesc = document.getElementById("project-form-desc");
    const formTypes = document.getElementById("project-form-types");

    if (!modal) return;

    if (project) {
      title.innerText = "Edit Project";
      formId.value = project.id;
      formTitle.value = project.title;
      formDesc.value = project.description || "";
      formTypes.value = (project.person_types || []).join(", ");
    } else {
      title.innerText = "Create New Project";
      formId.value = "";
      formTitle.value = "";
      formDesc.value = "";
      formTypes.value = "Student, Applicant, Employee, Faculty";
    }

    modal.classList.remove("hidden");
    this.initLucide();
  }

  openEditProjectModal() {
    if (this.currentProject) {
      this.openProjectModal(this.currentProject);
    }
  }

  closeProjectModal() {
    const modal = document.getElementById("modal-project");
    if (modal) modal.classList.add("hidden");
  }

  async handleSaveProject(event) {
    event.preventDefault();
    const id = document.getElementById("project-form-id").value;
    const title = document.getElementById("project-form-title").value.trim();
    const description = document.getElementById("project-form-desc").value.trim();
    const rawTypes = document.getElementById("project-form-types").value.trim();

    const person_types = rawTypes.split(",").map(t => t.trim()).filter(Boolean);

    const payload = { title, description, person_types };
    const btn = document.getElementById("btn-save-project");
    btn.disabled = true;
    btn.innerText = "Saving...";

    try {
      let res;
      if (id) {
        res = await fetch(`/api/projects/${id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
      } else {
        res = await fetch("/api/projects", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
      }

      if (res.ok) {
        this.closeProjectModal();
        this.showToast(id ? "Project updated successfully" : "Project created successfully");
        if (id && this.currentProject && this.currentProject.id == id) {
          await this.showProjectDetail(id);
        } else {
          await this.fetchProjects();
        }
      } else {
        const err = await res.json();
        this.showToast(err.detail || "Error saving project", true);
      }
    } catch (e) {
      this.showToast("Network error saving project", true);
    } finally {
      btn.disabled = false;
      btn.innerText = "Save Project";
    }
  }

  async deleteProject(projectId, event) {
    if (event) event.stopPropagation();
    if (!confirm("Are you sure you want to delete this project? All associated persons and scanned documents will be deleted from Azure SQL and Azure Storage.")) {
      return;
    }

    try {
      const res = await fetch(`/api/projects/${projectId}`, { method: "DELETE" });
      if (res.ok) {
        this.showToast("Project deleted successfully");
        if (this.currentProject && this.currentProject.id === projectId) {
          this.showProjectsView();
        } else {
          await this.fetchProjects();
        }
      } else {
        this.showToast("Error deleting project", true);
      }
    } catch (e) {
      this.showToast("Error deleting project", true);
    }
  }

  // ============================================================================
  // Project Detail View (People & Scans)
  // ============================================================================
  renderProjectDetail() {
    if (!this.currentProject) return;

    document.getElementById("detail-project-crumb").innerText = this.currentProject.title;
    document.getElementById("detail-project-title").innerText = this.currentProject.title;
    document.getElementById("detail-project-desc").innerText = this.currentProject.description || "No description provided.";
    document.getElementById("detail-project-count").innerText = (this.currentProject.persons || []).length;

    // Render types chips
    const typesCont = document.getElementById("detail-project-types");
    const types = this.currentProject.person_types || [];
    typesCont.innerHTML = types.map(t => `
      <span class="px-2.5 py-0.5 rounded-full text-xs font-medium bg-azure-500/10 text-azure-400 border border-azure-500/30">
        ${t}
      </span>
    `).join("");

    // Populate type filter dropdown
    const filterSelect = document.getElementById("persons-type-filter");
    if (filterSelect) {
      filterSelect.innerHTML = `<option value="">All Person Types</option>` + 
        types.map(t => `<option value="${t}">${t}</option>`).join("");
    }

    this.renderPersonsGrid(this.currentProject.persons || []);
    this.initLucide();
  }

  renderPersonsGrid(personsToRender) {
    const grid = document.getElementById("persons-grid");
    const empty = document.getElementById("persons-empty");
    const countEl = document.getElementById("persons-filtered-count");
    if (!grid || !empty) return;

    if (countEl) countEl.innerText = personsToRender.length;

    if (personsToRender.length === 0) {
      grid.innerHTML = "";
      empty.classList.remove("hidden");
      return;
    }

    empty.classList.add("hidden");
    grid.innerHTML = personsToRender.map(p => {
      const initial = p.full_name.charAt(0).toUpperCase();
      return `
        <div class="bg-slate-900 border border-slate-800 hover:border-azure-500/40 rounded-2xl p-5 shadow-lg flex flex-col justify-between transition-all group">
          <div>
            <div class="flex items-start justify-between gap-3">
              <div class="flex items-center space-x-3">
                <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-azure-600 to-indigo-600 flex items-center justify-center font-bold text-white text-base">
                  ${initial}
                </div>
                <div>
                  <h4 class="text-sm font-bold text-white group-hover:text-azure-400 transition cursor-pointer" onclick="app.showPersonDossier(${p.id})">
                    ${p.full_name}
                  </h4>
                  <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-azure-500/10 text-azure-400 border border-azure-500/20">
                    ${p.person_type}
                  </span>
                </div>
              </div>
              <button onclick="app.deletePerson(${p.id}, event)" title="Delete Person" class="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition">
                <i data-lucide="trash-2" class="w-4 h-4"></i>
              </button>
            </div>

            <div class="mt-4 space-y-1 text-xs text-slate-400">
              ${p.national_id ? `<div class="flex items-center space-x-1.5"><i data-lucide="credit-card" class="w-3.5 h-3.5 text-slate-500"></i><span>ID: ${p.national_id}</span></div>` : ''}
              ${p.email ? `<div class="flex items-center space-x-1.5"><i data-lucide="mail" class="w-3.5 h-3.5 text-slate-500"></i><span>${p.email}</span></div>` : ''}
              ${p.phone ? `<div class="flex items-center space-x-1.5"><i data-lucide="phone" class="w-3.5 h-3.5 text-slate-500"></i><span>${p.phone}</span></div>` : ''}
            </div>
          </div>

          <div class="mt-5 pt-3.5 border-t border-slate-800 flex items-center justify-between text-xs">
            <span class="text-slate-400 flex items-center space-x-1.5">
              <i data-lucide="images" class="w-3.5 h-3.5 text-azure-400"></i>
              <span>${p.documents_count || 0} Scans Saved</span>
            </span>
            <button onclick="app.showPersonDossier(${p.id})" class="text-azure-400 hover:text-azure-300 font-semibold flex items-center space-x-1">
              <span>View Dossier</span>
              <i data-lucide="arrow-right" class="w-3.5 h-3.5"></i>
            </button>
          </div>
        </div>
      `;
    }).join("");

    this.initLucide();
  }

  filterPersons() {
    if (!this.currentProject || !this.currentProject.persons) return;
    const query = (document.getElementById("persons-search")?.value || "").toLowerCase();
    const type = document.getElementById("persons-type-filter")?.value || "";

    const filtered = this.currentProject.persons.filter(p => {
      const matchQuery = p.full_name.toLowerCase().includes(query) ||
        (p.national_id && p.national_id.toLowerCase().includes(query)) ||
        (p.phone && p.phone.toLowerCase().includes(query));
      const matchType = !type || p.person_type === type;
      return matchQuery && matchType;
    });

    this.renderPersonsGrid(filtered);
  }

  // ============================================================================
  // Add Person Modal — Upload Scans Only (person details auto-extracted by AI)
  // ============================================================================
  openAddPersonModal() {
    const modal = document.getElementById("modal-person");
    const select = document.getElementById("person-form-type");
    if (!modal || !this.currentProject) return;

    // Reset staged files
    this.stagedFiles = [];
    this.renderStagedFiles();

    // Populate person type dropdown from project configuration
    const types = this.currentProject.person_types || ["General"];
    select.innerHTML = types.map(t => `<option value="${t}">${t}</option>`).join("");

    // Reset optional fields
    const notesEl = document.getElementById("person-form-notes");
    if (notesEl) notesEl.value = "";
    document.getElementById("person-save-status").innerText = "";

    modal.classList.remove("hidden");
    this.initLucide();
  }

  closeAddPersonModal() {
    const modal = document.getElementById("modal-person");
    if (modal) modal.classList.add("hidden");
    this.stagedFiles = [];
  }

  handleFilesSelected(fileList) {
    if (!fileList || fileList.length === 0) return;

    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i];
      // Auto guess initial category from filename
      let category = "Other";
      const name = file.name.toLowerCase();
      if (name.includes("voucher") || name.includes("fee") || name.includes("challan") || name.includes("pay")) {
        category = "Fee Voucher";
      } else if (name.includes("id") || name.includes("cnic") || name.includes("card") || name.includes("passport")) {
        category = "ID Document";
      } else if (name.includes("cert") || name.includes("degree") || name.includes("diploma")) {
        category = "Certificate";
      } else if (name.includes("handwritten") || name.includes("note") || name.includes("letter")) {
        category = "Handwritten Note";
      } else if (name.includes("stamp") || name.includes("seal") || name.includes("affidavit")) {
        category = "Stamped Form";
      }

      this.stagedFiles.push({
        file: file,
        category: category,
        previewUrl: URL.createObjectURL(file)
      });
    }

    this.renderStagedFiles();
  }

  renderStagedFiles() {
    const container = document.getElementById("staged-files-container");
    const countEl = document.getElementById("batch-selected-count");
    if (!container) return;

    countEl.innerText = `${this.stagedFiles.length} document pictures staged`;

    if (this.stagedFiles.length === 0) {
      container.innerHTML = "";
      return;
    }

    const categories = [
      "Fee Voucher",
      "ID Document",
      "Certificate",
      "Handwritten Note",
      "Stamped Form",
      "Receipt",
      "Other"
    ];

    container.innerHTML = this.stagedFiles.map((item, idx) => `
      <div class="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs">
        <div class="flex items-center space-x-3 overflow-hidden">
          <img src="${item.previewUrl}" alt="thumb" class="w-10 h-10 rounded-lg object-cover bg-slate-900 border border-slate-800">
          <div class="overflow-hidden">
            <div class="font-semibold text-white truncate max-w-[180px] sm:max-w-xs">${item.file.name}</div>
            <div class="text-[10px] text-slate-400">${(item.file.size / 1024).toFixed(1)} KB</div>
          </div>
        </div>

        <div class="flex items-center space-x-2">
          <select onchange="app.updateStagedCategory(${idx}, this.value)" class="bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg px-2 py-1 focus:outline-none focus:border-azure-500">
            ${categories.map(c => `<option value="${c}" ${item.category === c ? 'selected' : ''}>${c}</option>`).join("")}
          </select>
          <button type="button" onclick="app.removeStagedFile(${idx})" class="p-1 text-slate-400 hover:text-rose-400 transition">
            <i data-lucide="x" class="w-4 h-4"></i>
          </button>
        </div>
      </div>
    `).join("");

    this.initLucide();
  }

  updateStagedCategory(index, category) {
    if (this.stagedFiles[index]) {
      this.stagedFiles[index].category = category;
    }
  }

  removeStagedFile(index) {
    this.stagedFiles.splice(index, 1);
    this.renderStagedFiles();
  }

  async handleSavePerson(event) {
    event.preventDefault();
    if (!this.currentProject) return;

    if (this.stagedFiles.length === 0) {
      this.showToast("Please upload at least one scanned document image.", true);
      return;
    }

    const btn = document.getElementById("btn-save-person");
    const statusText = document.getElementById("person-save-status");
    btn.disabled = true;
    btn.innerHTML = `<span class="animate-spin mr-1">⏳</span> Scanning & Extracting...`;
    statusText.innerText = "Azure Content Understanding is analyzing documents and extracting person details...";

    const formData = new FormData();
    // Only pass person_type and optional notes — all other details extracted from docs
    formData.append("person_type", document.getElementById("person-form-type").value);
    const notes = document.getElementById("person-form-notes")?.value?.trim();
    if (notes) formData.append("notes", notes);

    // Batch images and categories
    const categoriesList = [];
    this.stagedFiles.forEach(item => {
      formData.append("files", item.file);
      categoriesList.push(item.category);
    });
    formData.append("categories_json", JSON.stringify(categoriesList));

    try {
      const res = await fetch(`/api/projects/${this.currentProject.id}/scan`, {
        method: "POST",
        body: formData
      });

      if (res.ok) {
        const createdPerson = await res.json();
        this.closeAddPersonModal();
        const name = createdPerson.full_name || "Person";
        this.showToast(`✅ ${name} enrolled — person details extracted by Azure AI!`);
        // Refresh project details
        await this.showProjectDetail(this.currentProject.id);
      } else {
        const err = await res.json();
        this.showToast(err.detail || "Error processing scans", true);
        statusText.innerText = err.detail || "Error occurred";
      }
    } catch (e) {
      this.showToast("Network error uploading batch scans", true);
      statusText.innerText = "Network error";
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<i data-lucide="cloud-upload" class="w-4 h-4"></i><span>Scan &amp; Auto-Extract</span>`;
      this.initLucide();
    }
  }

  async deletePerson(personId, event) {
    if (event) event.stopPropagation();
    if (!confirm("Are you sure you want to delete this person and all their scanned documents?")) return;

    try {
      const res = await fetch(`/api/persons/${personId}`, { method: "DELETE" });
      if (res.ok) {
        this.showToast("Person and documents deleted");
        if (this.currentProject) {
          await this.showProjectDetail(this.currentProject.id);
        }
      } else {
        this.showToast("Error deleting person", true);
      }
    } catch (e) {
      this.showToast("Error deleting person", true);
    }
  }

  // ============================================================================
  // Person Dossier View & Scanned Documents Gallery
  // ============================================================================
  renderPersonDossier() {
    if (!this.currentPerson) return;

    const p = this.currentPerson;
    const displayName = p.full_name && p.full_name !== "Unknown Person" ? p.full_name : "Auto-Extracted Person";

    document.getElementById("dossier-back-label").innerText = this.currentProject ? this.currentProject.title : "Back to Project";
    document.getElementById("dossier-name-crumb").innerText = displayName;
    document.getElementById("dossier-avatar").innerText = displayName.charAt(0).toUpperCase();
    document.getElementById("dossier-full-name").innerText = displayName;
    document.getElementById("dossier-person-type").innerText = p.person_type;
    document.getElementById("dossier-national-id").innerText = p.national_id ? `ID: ${p.national_id}` : "ID: Extracting from docs...";
    document.getElementById("dossier-email").innerText = p.email || "—";
    document.getElementById("dossier-phone").innerText = p.phone || "—";

    // Extra details — show AI-extracted info panel
    const extraCont = document.getElementById("dossier-extra-info");

    // Gather extracted person data from the latest doc's analysis if person fields are sparse
    let extractedPerson = null;
    if (p.documents && p.documents.length > 0) {
      for (const doc of p.documents) {
        if (doc.analysis && doc.analysis.extracted_fields && doc.analysis.extracted_fields.extracted_person) {
          extractedPerson = doc.analysis.extracted_fields.extracted_person;
          break;
        }
      }
    }

    const aiInfoHtml = extractedPerson ? `
      <div class="mt-4 pt-3 border-t border-slate-800 w-full">
        <div class="flex items-center space-x-1.5 mb-2">
          <span class="text-[10px] font-bold uppercase tracking-wider text-indigo-400">🤖 Azure AI Extracted Details</span>
          ${extractedPerson.confidence ? `<span class="text-[10px] text-slate-500">(${Math.round(extractedPerson.confidence * 100)}% confidence)</span>` : ''}
        </div>
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
          ${extractedPerson.full_name ? `<div><span class="text-slate-400">Name:</span> <span class="text-white font-medium">${extractedPerson.full_name}</span></div>` : ''}
          ${extractedPerson.national_id ? `<div><span class="text-slate-400">National ID:</span> <span class="text-white font-medium">${extractedPerson.national_id}</span></div>` : ''}
          ${extractedPerson.date_of_birth ? `<div><span class="text-slate-400">Date of Birth:</span> <span class="text-white font-medium">${extractedPerson.date_of_birth}</span></div>` : ''}
          ${extractedPerson.email ? `<div><span class="text-slate-400">Email:</span> <span class="text-white font-medium">${extractedPerson.email}</span></div>` : ''}
          ${extractedPerson.phone ? `<div><span class="text-slate-400">Phone:</span> <span class="text-white font-medium">${extractedPerson.phone}</span></div>` : ''}
          ${extractedPerson.address ? `<div class="col-span-2"><span class="text-slate-400">Address:</span> <span class="text-white font-medium">${extractedPerson.address}</span></div>` : ''}
        </div>
      </div>
    ` : '';

    extraCont.innerHTML = `
      ${p.date_of_birth ? `<div><span class="text-slate-400">Date of Birth:</span> <span class="text-white">${p.date_of_birth}</span></div>` : ''}
      ${p.address ? `<div><span class="text-slate-400">Address / Notes:</span> <span class="text-white">${p.address}</span></div>` : ''}
      <div><span class="text-slate-400">Azure SQL Reference:</span> <span class="text-azure-400 font-mono">Person_ID #${p.id}</span></div>
      ${aiInfoHtml}
    `;

    document.getElementById("dossier-docs-count").innerText = (p.documents || []).length;
    this.renderDossierDocs(p.documents || []);
    this.initLucide();
  }

  renderDossierDocs(docsToRender) {
    const grid = document.getElementById("dossier-docs-grid");
    const empty = document.getElementById("dossier-docs-empty");
    if (!grid || !empty) return;

    if (docsToRender.length === 0) {
      grid.innerHTML = "";
      empty.classList.remove("hidden");
      return;
    }

    empty.classList.add("hidden");
    grid.innerHTML = docsToRender.map(doc => {
      const an = doc.analysis || {};
      const isStamped = an.has_stamp;
      const isSigned = an.has_signature;
      const isHw = an.is_handwritten;
      const hwPct = an.handwritten_percentage || 0;

      return `
        <div class="doc-card bg-slate-900 border border-slate-800 hover:border-azure-500/50 rounded-2xl overflow-hidden shadow-lg flex flex-col justify-between transition-all">
          
          <!-- Image Thumbnail with Camera Scan Overlay -->
          <div class="relative bg-slate-950 h-44 overflow-hidden flex items-center justify-center cursor-pointer" onclick="app.openDocViewer(${doc.id})">
            <img src="/api/documents/${doc.id}/file" alt="${doc.original_filename}" class="doc-card-thumb max-h-full max-w-full object-cover">
            
            <div class="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent to-transparent pointer-events-none"></div>
            
            <!-- Category Tag -->
            <div class="absolute top-2.5 left-2.5">
              <span class="px-2.5 py-1 rounded-lg text-[10px] font-bold bg-slate-900/90 text-white backdrop-blur-md border border-slate-700/80 shadow">
                ${doc.doc_category}
              </span>
            </div>

            <!-- Quick Delete Button -->
            <button onclick="app.deleteDocument(${doc.id}, event)" title="Delete Document" class="absolute top-2.5 right-2.5 p-1.5 rounded-lg bg-slate-900/80 hover:bg-rose-600 text-slate-300 hover:text-white backdrop-blur-md transition">
              <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
            </button>
          </div>

          <!-- Card Content & Detection Badges -->
          <div class="p-4 flex-1 flex flex-col justify-between">
            <div>
              <h5 class="text-xs font-bold text-white truncate cursor-pointer hover:text-azure-400" onclick="app.openDocViewer(${doc.id})" title="${doc.original_filename}">
                ${doc.original_filename}
              </h5>
              
              <!-- Badges from Azure Content Understanding -->
              <div class="flex flex-wrap items-center gap-1.5 mt-2.5">
                ${isStamped 
                  ? `<span class="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30">
                       <i data-lucide="stamp" class="w-3 h-3"></i><span>Stamped</span>
                     </span>` 
                  : `<span class="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-400">
                       <span>No stamp</span>
                     </span>`}

                ${isSigned 
                  ? `<span class="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                       <i data-lucide="pen-tool" class="w-3 h-3"></i><span>Signed</span>
                     </span>` 
                  : `<span class="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-400">
                       <span>Unsigned</span>
                     </span>`}

                ${isHw 
                  ? `<span class="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-purple-500/15 text-purple-300 border border-purple-500/30">
                       <span>${hwPct}% Hand</span>
                     </span>` 
                  : `<span class="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-400">
                       <span>Printed</span>
                     </span>`}
              </div>
            </div>

            <!-- Inspect Button -->
            <button onclick="app.openDocViewer(${doc.id})" class="mt-4 w-full py-1.5 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium flex items-center justify-center space-x-1.5 transition">
              <i data-lucide="eye" class="w-3.5 h-3.5 text-azure-400"></i>
              <span>Inspect Analysis & OCR</span>
            </button>

          </div>

        </div>
      `;
    }).join("");

    this.initLucide();
  }

  filterDossierDocs(category) {
    this.activeDocCategoryFilter = category;
    document.querySelectorAll(".doc-filter-btn").forEach(btn => {
      btn.classList.remove("active", "bg-azure-500", "text-white");
      btn.classList.add("bg-slate-800", "text-slate-300");
    });

    event.target.classList.add("active", "bg-azure-500", "text-white");
    event.target.classList.remove("bg-slate-800", "text-slate-300");

    if (!this.currentPerson || !this.currentPerson.documents) return;

    if (category === "all") {
      this.renderDossierDocs(this.currentPerson.documents);
    } else if (category === "Handwritten") {
      const filtered = this.currentPerson.documents.filter(d => d.analysis && d.analysis.is_handwritten);
      this.renderDossierDocs(filtered);
    } else {
      const filtered = this.currentPerson.documents.filter(d => d.doc_category === category);
      this.renderDossierDocs(filtered);
    }
  }

  // ============================================================================
  // Additional Batch Upload Modal
  // ============================================================================
  openUploadBatchModal() {
    const modal = document.getElementById("modal-batch-upload");
    if (!modal) return;
    this.stagedAdditionalFiles = [];
    this.renderStagedAdditionalFiles();
    document.getElementById("batch-additional-status").innerText = "";
    modal.classList.remove("hidden");
    this.initLucide();
  }

  closeUploadBatchModal() {
    const modal = document.getElementById("modal-batch-upload");
    if (modal) modal.classList.add("hidden");
    this.stagedAdditionalFiles = [];
  }

  handleAdditionalFilesSelected(fileList) {
    if (!fileList || fileList.length === 0) return;

    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i];
      let category = "Other";
      const name = file.name.toLowerCase();
      if (name.includes("voucher") || name.includes("fee")) category = "Fee Voucher";
      else if (name.includes("id") || name.includes("card")) category = "ID Document";
      else if (name.includes("cert")) category = "Certificate";
      else if (name.includes("handwritten") || name.includes("note")) category = "Handwritten Note";
      else if (name.includes("stamp")) category = "Stamped Form";

      this.stagedAdditionalFiles.push({
        file: file,
        category: category,
        previewUrl: URL.createObjectURL(file)
      });
    }

    this.renderStagedAdditionalFiles();
  }

  renderStagedAdditionalFiles() {
    const container = document.getElementById("staged-additional-files");
    if (!container) return;

    if (this.stagedAdditionalFiles.length === 0) {
      container.innerHTML = "";
      return;
    }

    const categories = ["Fee Voucher", "ID Document", "Certificate", "Handwritten Note", "Stamped Form", "Receipt", "Other"];

    container.innerHTML = this.stagedAdditionalFiles.map((item, idx) => `
      <div class="flex items-center justify-between p-2 rounded-xl bg-slate-950 border border-slate-800 text-xs">
        <span class="truncate max-w-[150px] font-medium text-white">${item.file.name}</span>
        <div class="flex items-center space-x-2">
          <select onchange="app.updateAdditionalCategory(${idx}, this.value)" class="bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg px-2 py-1">
            ${categories.map(c => `<option value="${c}" ${item.category === c ? 'selected' : ''}>${c}</option>`).join("")}
          </select>
          <button type="button" onclick="app.removeAdditionalStagedFile(${idx})" class="p-1 text-slate-400 hover:text-rose-400">
            <i data-lucide="x" class="w-4 h-4"></i>
          </button>
        </div>
      </div>
    `).join("");

    this.initLucide();
  }

  updateAdditionalCategory(index, cat) {
    if (this.stagedAdditionalFiles[index]) this.stagedAdditionalFiles[index].category = cat;
  }

  removeAdditionalStagedFile(index) {
    this.stagedAdditionalFiles.splice(index, 1);
    this.renderStagedAdditionalFiles();
  }

  async handleSaveAdditionalBatch(event) {
    event.preventDefault();
    if (!this.currentPerson || this.stagedAdditionalFiles.length === 0) {
      this.showToast("Please choose at least one scan picture", true);
      return;
    }

    const btn = document.getElementById("btn-save-additional-batch");
    const statusText = document.getElementById("batch-additional-status");
    btn.disabled = true;
    btn.innerText = "Uploading...";
    statusText.innerText = "Processing batch in Azure...";

    const formData = new FormData();
    const categoriesList = [];
    this.stagedAdditionalFiles.forEach(item => {
      formData.append("files", item.file);
      categoriesList.push(item.category);
    });
    formData.append("categories_json", JSON.stringify(categoriesList));

    try {
      const res = await fetch(`/api/documents/batch/${this.currentPerson.id}`, {
        method: "POST",
        body: formData
      });

      if (res.ok) {
        this.closeUploadBatchModal();
        this.showToast("Batch documents uploaded and analyzed!");
        await this.showPersonDossier(this.currentPerson.id);
      } else {
        const err = await res.json();
        this.showToast(err.detail || "Error uploading batch", true);
      }
    } catch (e) {
      this.showToast("Network error uploading batch", true);
    } finally {
      btn.disabled = false;
      btn.innerText = "Upload Scans";
    }
  }

  // ============================================================================
  // Document Viewer & Lightbox Modal
  // ============================================================================
  async openDocViewer(docId) {
    if (!this.currentPerson) return;
    const doc = (this.currentPerson.documents || []).find(d => d.id === docId);
    if (!doc) return;

    this.currentDoc = doc;
    this.currentRotation = 0;

    const modal = document.getElementById("modal-doc-viewer");
    const img = document.getElementById("viewer-image");
    img.src = `/api/documents/${doc.id}/file`;
    img.style.transform = `rotate(0deg)`;

    document.getElementById("viewer-doc-title").innerText = doc.original_filename;
    document.getElementById("viewer-doc-category").innerText = `${doc.doc_category} • Azure Account Storage Service`;
    document.getElementById("viewer-storage-ref").innerText = doc.storage_reference;

    const an = doc.analysis || {};

    // Signature Badge
    const sigText = document.getElementById("badge-sig-text");
    sigText.innerText = an.has_signature ? "Detected" : "Not Found";
    sigText.className = an.has_signature ? "text-xs font-bold text-emerald-400 mt-0.5" : "text-xs font-bold text-slate-400 mt-0.5";

    // Stamp Badge
    const stampText = document.getElementById("badge-stamp-text");
    stampText.innerText = an.has_stamp ? "Official Stamp Found" : "No Stamp";
    stampText.className = an.has_stamp ? "text-xs font-bold text-amber-400 mt-0.5" : "text-xs font-bold text-slate-400 mt-0.5";

    // Handwriting Badge
    document.getElementById("badge-hw-text").innerText = `${an.handwritten_percentage || 0}%`;

    // Structured Fields Table
    const table = document.getElementById("viewer-fields-table");
    const fields = an.extracted_fields || {};
    // Don't display the nested extracted_person object as a raw field — handled separately
    const displayFields = Object.entries(fields).filter(([k]) => k !== "extracted_person");
    if (displayFields.length === 0) {
      table.innerHTML = `<div class="p-3 text-slate-500 italic">No structured key-values detected.</div>`;
    } else {
      table.innerHTML = displayFields.map(([k, v]) => `
        <div class="flex items-start justify-between p-2.5">
          <span class="font-medium text-slate-400">${k}:</span>
          <span class="font-semibold text-white text-right ml-2">${typeof v === 'object' ? JSON.stringify(v) : v}</span>
        </div>
      `).join("");
    }

    // Show AI-Extracted Person Info if available
    const ep = fields.extracted_person;
    const epSection = document.getElementById("viewer-extracted-person");
    if (epSection) {
      if (ep && (ep.full_name || ep.national_id)) {
        epSection.innerHTML = `
          <div class="mt-1">
            <div class="flex items-center space-x-1.5 mb-2">
              <span class="text-[10px] font-bold uppercase tracking-wider text-indigo-400">🤖 AI-Extracted Person</span>
              ${ep.confidence ? `<span class="text-[10px] text-slate-500">${Math.round(ep.confidence * 100)}% confidence</span>` : ''}
            </div>
            <div class="bg-indigo-950/40 border border-indigo-500/20 rounded-xl p-3 space-y-1 text-xs">
              ${ep.full_name ? `<div class="flex justify-between"><span class="text-slate-400">Name:</span><span class="text-white font-semibold">${ep.full_name}</span></div>` : ''}
              ${ep.national_id ? `<div class="flex justify-between"><span class="text-slate-400">National ID:</span><span class="text-white font-semibold">${ep.national_id}</span></div>` : ''}
              ${ep.date_of_birth ? `<div class="flex justify-between"><span class="text-slate-400">Date of Birth:</span><span class="text-white">${ep.date_of_birth}</span></div>` : ''}
              ${ep.email ? `<div class="flex justify-between"><span class="text-slate-400">Email:</span><span class="text-white">${ep.email}</span></div>` : ''}
              ${ep.phone ? `<div class="flex justify-between"><span class="text-slate-400">Phone:</span><span class="text-white">${ep.phone}</span></div>` : ''}
              ${ep.address ? `<div class="flex justify-between"><span class="text-slate-400">Address:</span><span class="text-white text-right ml-2">${ep.address}</span></div>` : ''}
            </div>
          </div>
        `;
        epSection.classList.remove("hidden");
      } else {
        epSection.innerHTML = "";
        epSection.classList.add("hidden");
      }
    }

    // OCR Text
    document.getElementById("viewer-ocr-text").innerText = an.extracted_text || "No OCR text extracted.";

    modal.classList.remove("hidden");
    this.initLucide();
  }

  closeDocViewer() {
    const modal = document.getElementById("modal-doc-viewer");
    if (modal) modal.classList.add("hidden");
    this.currentDoc = null;
  }

  rotateViewerImage() {
    this.currentRotation = (this.currentRotation + 90) % 360;
    const img = document.getElementById("viewer-image");
    if (img) {
      img.style.transform = `rotate(${this.currentRotation}deg)`;
    }
  }

  async reanalyzeCurrentDocument() {
    if (!this.currentDoc) return;
    this.showToast("Re-analyzing with Azure Content Understanding...");

    try {
      const res = await fetch(`/api/documents/${this.currentDoc.id}/reanalyze`, { method: "POST" });
      if (res.ok) {
        const newAnalysis = await res.json();
        this.currentDoc.analysis = newAnalysis;
        this.showToast("Document re-analyzed successfully!");
        this.openDocViewer(this.currentDoc.id);
      } else {
        this.showToast("Re-analysis failed", true);
      }
    } catch (e) {
      this.showToast("Error connecting to Azure Content Understanding", true);
    }
  }

  copyOcrText() {
    const text = document.getElementById("viewer-ocr-text")?.innerText;
    if (text) {
      navigator.clipboard.writeText(text);
      this.showToast("OCR text copied to clipboard!");
    }
  }

  async deleteDocument(docId, event) {
    if (event) event.stopPropagation();
    if (!confirm("Are you sure you want to delete this document from Azure SQL and Azure Storage?")) return;

    try {
      const res = await fetch(`/api/documents/${docId}`, { method: "DELETE" });
      if (res.ok) {
        this.showToast("Document deleted successfully");
        if (this.currentDoc && this.currentDoc.id === docId) {
          this.closeDocViewer();
        }
        if (this.currentPerson) {
          await this.showPersonDossier(this.currentPerson.id);
        }
      } else {
        this.showToast("Error deleting document", true);
      }
    } catch (e) {
      this.showToast("Error deleting document", true);
    }
  }

  // ============================================================================
  // AI Agent Assistant
  // ============================================================================
  toggleAgentDrawer() {
    const drawer = document.getElementById("agent-drawer");
    if (drawer) {
      drawer.classList.toggle("translate-x-full");
    }
  }

  appendAgentMessage(text, isUser = false) {
    const cont = document.getElementById("agent-messages");
    if (!cont) return;

    const div = document.createElement("div");
    div.className = isUser ? "flex items-start justify-end space-x-2.5" : "flex items-start space-x-2.5";

    // Format simple markdown (bold, lists, headings)
    const formatted = text
      .replace(/### (.*)/g, '<h4 class="font-bold text-white text-xs mt-1 mb-1">$1</h4>')
      .replace(/\*\*(.*?)\*\*/g, '<strong class="text-white">$1</strong>')
      .replace(/`([^`]+)`/g, '<code class="bg-slate-900 px-1 py-0.5 rounded text-azure-400 font-mono text-[11px]">$1</code>')
      .replace(/\n/g, '<br>');

    if (isUser) {
      div.innerHTML = `
        <div class="p-3 rounded-2xl bg-azure-600 text-white max-w-[85%] leading-relaxed shadow-sm">
          ${text}
        </div>
        <div class="w-7 h-7 rounded-lg bg-slate-700 flex-shrink-0 flex items-center justify-center text-white font-bold text-xs">
          You
        </div>
      `;
    } else {
      div.innerHTML = `
        <div class="w-7 h-7 rounded-lg bg-gradient-to-tr from-azure-600 to-indigo-600 flex-shrink-0 flex items-center justify-center text-white font-bold text-xs shadow">
          AI
        </div>
        <div class="p-3.5 rounded-2xl bg-slate-800 text-slate-200 border border-slate-700 max-w-[85%] leading-relaxed shadow-md">
          ${formatted}
        </div>
      `;
    }

    cont.appendChild(div);
    cont.scrollTop = cont.scrollHeight;
  }

  async handleAgentSubmit(event) {
    event.preventDefault();
    const input = document.getElementById("agent-input");
    const query = input.value.trim();
    if (!query) return;

    input.value = "";
    this.appendAgentMessage(query, true);

    const payload = {
      query: query,
      project_id: this.currentProject ? this.currentProject.id : null,
      person_id: this.currentPerson ? this.currentPerson.id : null
    };

    try {
      const res = await fetch("/api/agent/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        const data = await res.json();
        this.appendAgentMessage(data.answer);
      } else {
        this.appendAgentMessage("I encountered an issue processing your request. Please try again.");
      }
    } catch (e) {
      this.appendAgentMessage("Network error communicating with AI Agent.");
    }
  }

  sendQuickPrompt(promptText) {
    document.getElementById("agent-input").value = promptText;
    this.handleAgentSubmit(new Event("submit"));
  }

  async runPersonAudit() {
    if (!this.currentPerson) return;
    this.toggleAgentDrawer();
    this.appendAgentMessage(`Auditing documents for ${this.currentPerson.full_name}...`, true);

    try {
      const res = await fetch(`/api/agent/audit/person/${this.currentPerson.id}`);
      if (res.ok) {
        const audit = await res.json();
        const findingsList = audit.findings.map(f => `• [${f.status}] **${f.category}**: ${f.message}`).join("\n");
        const answer = `### AI Audit Report: ${audit.person_name} (${audit.person_type})\n\n` +
          `**Compliance Status:** \`${audit.compliance_status}\` (Score: **${audit.score}%**)\n\n` +
          `**Summary:** ${audit.summary}\n\n` +
          `**Findings:**\n${findingsList}`;
        this.appendAgentMessage(answer);
      }
    } catch (e) {
      this.appendAgentMessage("Error running person audit.");
    }
  }

  async runProjectAudit() {
    if (!this.currentProject) return;
    this.toggleAgentDrawer();
    this.appendAgentMessage(`Running project health audit for ${this.currentProject.title}...`, true);

    try {
      const res = await fetch(`/api/agent/audit/project/${this.currentProject.id}`);
      if (res.ok) {
        const stats = await res.json();
        const answer = `### Project Audit: ${stats.project_title}\n\n` +
          `• **Enrolled Persons:** ${stats.total_persons}\n` +
          `• **Total Scanned Documents:** ${stats.total_documents}\n` +
          `• **Compliant Persons:** ${stats.compliant_persons}\n` +
          `• **Issues / Warnings:** ${stats.action_required_persons}\n` +
          `• **Overall Compliance Score:** **${stats.overall_health_score}%**`;
        this.appendAgentMessage(answer);
      }
    } catch (e) {
      this.appendAgentMessage("Error running project audit.");
    }
  }
}

// Instantiate and expose globally
const app = new DocuScanApp();
window.app = app;
