const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const projectRoot = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(projectRoot, "index.html"), "utf8");
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
assert.ok(scriptMatch, "index.html should contain the browser app script");

class FakeElement {
  constructor(id, dataField = "") {
    this.id = id;
    this.dataset = dataField ? { field: dataField } : {};
    this.listeners = new Map();
    this.value = "";
    this.textContent = "";
    this.innerHTML = "";
    this.className = "";
    this.files = [];
    this.classList = { add() {}, remove() {} };
  }

  addEventListener(type, handler) {
    this.listeners.set(type, handler);
  }

  dispatch(type, event = {}) {
    const handler = this.listeners.get(type);
    if (handler) return handler({ target: this, ...event });
  }

  click() {
    return this.dispatch("click");
  }

  remove() {}
}

function createApp() {
  const ids = [
    "metaProject", "metaBranch", "metaHead", "metaFiles", "fileList",
    "snapshotStatus", "snapshotHint", "preview", "toast", "copyBtn",
    "downloadBtn", "importBtn", "fileInput", "newBtn",
  ];
  const elements = new Map(ids.map((id) => [id, new FakeElement(id)]));
  const fieldNames = [
    "projectName", "taskTitle", "goal", "currentState", "decisions",
    "checks", "blockers", "nextSteps",
  ];
  const fields = fieldNames.map((name) => new FakeElement(name, name));
  const downloads = [];
  const blobsByUrl = new Map();
  const storage = new Map();
  let nextBlob = 0;

  class TestBlob {
    constructor(parts, options = {}) {
      this.text = parts.join("");
      this.type = options.type || "";
    }
  }

  class TestFileReader {
    readAsText(file) {
      this.result = file.content;
      this.onload();
    }
  }

  const document = {
    body: { appendChild() {} },
    querySelectorAll(selector) {
      return selector === "[data-field]" ? fields : [];
    },
    getElementById(id) {
      return elements.get(id) || null;
    },
    createElement(tag) {
      const element = new FakeElement(tag);
      element.click = () => {
        const blob = blobsByUrl.get(element.href);
        downloads.push({ filename: element.download, text: blob?.text, type: blob?.type });
      };
      return element;
    },
  };

  const context = {
    document,
    localStorage: {
      getItem(key) { return storage.has(key) ? storage.get(key) : null; },
      setItem(key, value) { storage.set(key, value); },
    },
    navigator: { clipboard: { writeText: async () => {} } },
    FileReader: TestFileReader,
    Blob: TestBlob,
    URL: {
      createObjectURL(blob) {
        const url = `blob:test-${nextBlob++}`;
        blobsByUrl.set(url, blob);
        return url;
      },
      revokeObjectURL() {},
    },
    setTimeout(callback) { callback(); return 1; },
    clearTimeout() {},
  };
  vm.runInNewContext(scriptMatch[1], context, { filename: "index.html:inline-script" });

  return {
    elements,
    fields: Object.fromEntries(fields.map((field) => [field.dataset.field, field])),
    downloads,
    importJson(value) {
      const input = elements.get("fileInput");
      input.files = [{ content: JSON.stringify(value) }];
      input.dispatch("change");
    },
    exportFiles() {
      elements.get("downloadBtn").click();
    },
  };
}

function exportedCapsule(app) {
  app.exportFiles();
  const jsonDownload = app.downloads.find((item) => item.type?.startsWith("application/json"));
  assert.ok(jsonDownload, "JSON export should be downloaded");
  return JSON.parse(jsonDownload.text);
}

function testImportWithoutSnapshotClearsPreviousRepository() {
  const app = createApp();
  app.importJson({
    repository: null,
    task: { title: "A fresh handoff", goal: "Continue the work", current_state: "Ready" },
  });

  assert.equal(app.elements.get("metaBranch").textContent, "Not imported");
  assert.equal(app.elements.get("metaProject").textContent, "—");
  assert.equal(exportedCapsule(app).repository, null);
}

function testImportClearsEmptyTextFields() {
  const app = createApp();
  app.importJson({
    repository: null,
    task: { title: "Empty fields", goal: "", current_state: "" },
  });

  assert.equal(app.fields.goal.value, "");
  assert.equal(app.fields.currentState.value, "");
  const task = exportedCapsule(app).task;
  assert.equal(task.goal, "");
  assert.equal(task.current_state, "");
}

function testMalformedChangedFilesAreRejectedWithoutBreakingExport() {
  const app = createApp();
  app.importJson({
    repository: { name: "broken", branch: "main", head: "abc123", changed_files: "not a list" },
    task: { title: "Malformed snapshot" },
  });

  assert.match(app.elements.get("toast").textContent, /changed_files must be a list of paths/);
  assert.equal(app.elements.get("snapshotStatus").textContent, "Sample handoff loaded");
  assert.equal(exportedCapsule(app).repository.name, "webhook-service");
  assert.equal(app.downloads.length, 2, "both exports should still be produced after the rejected import");
}

const tests = [
  ["import without a snapshot clears the old repository", testImportWithoutSnapshotClearsPreviousRepository],
  ["imported empty goal/state fields clear old text", testImportClearsEmptyTextFields],
  ["malformed changed_files is rejected and exports stay usable", testMalformedChangedFilesAreRejectedWithoutBreakingExport],
];

for (const [name, run] of tests) {
  run();
  console.log(`PASS ${name}`);
}
