const form = document.getElementById("config-form");
const statusEl = document.getElementById("config-status");
const exportYamlBtn = document.getElementById("export-config-yaml");
const exportJsonBtn = document.getElementById("export-config-json");
const importConfigBtn = document.getElementById("import-config-btn");
const importConfigFileInput = document.getElementById("import-config-file");
const writeConfigFileBtn = document.getElementById("write-config-file-btn");
const configWritePathInput = document.getElementById("config-write-path");
const configWriteFormatInput = document.getElementById("config-write-format");
const importerJsonUploadInput = document.getElementById("importer_json_upload");
const uploadImporterJsonBtn = document.getElementById("upload-importer-json-btn");
const verifyImporterJsonBtn = document.getElementById("verify-importer-json-btn");
const resetConfigBtn = document.getElementById("reset-config-btn");

const fields = {
  firefly_url: document.getElementById("firefly_url"),
  firefly_secret: document.getElementById("firefly_secret"),
  firefly_token: document.getElementById("firefly_token"),
  firefly_timeout: document.getElementById("firefly_timeout"),
  firefly_batch_size: document.getElementById("firefly_batch_size"),
  firefly_adaptive_batch_enabled: document.getElementById("firefly_adaptive_batch_enabled"),
  firefly_adaptive_target_ratio: document.getElementById("firefly_adaptive_target_ratio"),
  firefly_adaptive_max_batch_size: document.getElementById("firefly_adaptive_max_batch_size"),
  importer_json_path: document.getElementById("importer_json_path"),
  merge_own_accounts: document.getElementById("merge_own_accounts"),
  merge_account_aliases: document.getElementById("merge_account_aliases"),
  merge_savings_accounts: document.getElementById("merge_savings_accounts"),
  ollama_enabled: document.getElementById("ollama_enabled"),
  ollama_url: document.getElementById("ollama_url"),
  ollama_model: document.getElementById("ollama_model"),
  ollama_temperature: document.getElementById("ollama_temperature"),
  ollama_batch_size: document.getElementById("ollama_batch_size"),
  ollama_auto_export_after_categorize: document.getElementById("ollama_auto_export_after_categorize"),
  ollama_categories: document.getElementById("ollama_categories"),
  ollama_prompt_template: document.getElementById("ollama_prompt_template"),
};

function categoriesToText(list) {
  return (list || []).join(", ");
}

function textToCategories(text) {
  return String(text || "")
    .split(",")
    .map((x) => x.trim())
    .filter((x) => x);
}

function parseLineList(text) {
  const tokens = String(text || "")
    .split(/\r?\n|,/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"));
  return Array.from(new Set(tokens));
}

function formatLineList(items) {
  return (Array.isArray(items) ? items : []).map((item) => String(item || "").trim()).filter(Boolean).join("\n");
}

function parseAliases(text) {
  const out = {};
  String(text || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"))
    .forEach((line) => {
      const idx = line.indexOf("=");
      if (idx <= 0) {
        return;
      }
      const key = line.slice(0, idx).trim();
      const value = line.slice(idx + 1).trim();
      if (key && value) {
        out[key] = value;
      }
    });
  return out;
}

function formatAliases(obj) {
  return Object.entries(obj || {})
    .filter(([key, value]) => String(key || "").trim() && String(value || "").trim())
    .sort((a, b) => String(a[0]).localeCompare(String(b[0])))
    .map(([key, value]) => `${key}=${value}`)
    .join("\n");
}

function parseSavingsAccounts(text) {
  const out = {};
  String(text || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"))
    .forEach((line) => {
      const idx = line.indexOf("=");
      if (idx <= 0) {
        return;
      }
      const id = line.slice(0, idx).trim();
      const right = line.slice(idx + 1).trim();
      if (!id || !right) {
        return;
      }
      const pipe = right.indexOf("|");
      if (pipe >= 0) {
        const account = right.slice(0, pipe).trim() || id;
        const name = right.slice(pipe + 1).trim();
        out[id] = { account };
        if (name) {
          out[id].name = name;
        }
        return;
      }
      out[id] = { account: id, name: right };
    });
  return out;
}

function formatSavingsAccounts(obj) {
  return Object.entries(obj || {})
    .sort((a, b) => String(a[0]).localeCompare(String(b[0])))
    .map(([id, value]) => {
      if (value && typeof value === "object") {
        const account = String(value.account || id).trim() || id;
        const name = String(value.name || "").trim();
        return `${id}=${account}|${name}`;
      }
      const token = String(value || "").trim();
      return `${id}=${id}|${token}`;
    })
    .join("\n");
}

function setStatus(message) {
  if (statusEl) {
    statusEl.textContent = String(message || "");
  }
}

function summarizeVerification(verification) {
  if (!verification || typeof verification !== "object") {
    return "No verification payload.";
  }
  const bytes = Number(verification.bytes || 0);
  const count = Number(verification.top_level_key_count || 0);
  const hash = String(verification.sha256_canonical || verification.sha256_raw || "");
  const shortHash = hash ? `${hash.slice(0, 12)}...` : "-";
  const path = String(verification.path || "");
  return `Verified importer JSON (${bytes} bytes, ${count} top-level keys, sha256 ${shortHash}) at ${path}`;
}

async function loadConfig() {
  const response = await fetch("/api/config");
  if (!response.ok) {
    throw new Error("Failed to load config.");
  }
  const config = await response.json();
  const firefly = config.firefly || {};
  const importer = config.importer || {};
  const ollama = config.ollama || {};
  const merge = config.merge || {};

  fields.firefly_url.value = firefly.url || "";
  fields.firefly_secret.value = firefly.secret || "";
  fields.firefly_token.value = firefly.token || "";
  fields.firefly_timeout.value = firefly.timeout ?? 30;
  fields.firefly_batch_size.value = firefly.batch_size ?? 50;
  fields.firefly_adaptive_batch_enabled.checked = firefly.adaptive_batch_enabled !== false;
  fields.firefly_adaptive_target_ratio.value = firefly.adaptive_target_timeout_ratio ?? 0.75;
  fields.firefly_adaptive_max_batch_size.value = firefly.adaptive_max_batch_size ?? 200;
  fields.importer_json_path.value = importer.json_path || "";
  fields.merge_own_accounts.value = formatLineList(merge.own_accounts || []);
  fields.merge_account_aliases.value = formatAliases(merge.account_aliases || {});
  fields.merge_savings_accounts.value = formatSavingsAccounts(merge.savings_accounts || {});
  fields.ollama_enabled.checked = !!ollama.enabled;
  fields.ollama_url.value = ollama.url || "";
  fields.ollama_model.value = ollama.model || "";
  fields.ollama_temperature.value = ollama.temperature ?? 0.0;
  fields.ollama_batch_size.value = ollama.batch_size ?? 20;
  fields.ollama_auto_export_after_categorize.checked = !!ollama.auto_export_after_categorize;
  fields.ollama_categories.value = categoriesToText(ollama.default_categories || []);
  fields.ollama_prompt_template.value = ollama.prompt_template || "";
}

async function saveConfig(event) {
  event.preventDefault();
  setStatus("Saving...");

  const payload = {
    firefly: {
      url: fields.firefly_url.value.trim(),
      secret: fields.firefly_secret.value.trim(),
      token: fields.firefly_token.value.trim(),
      timeout: Number(fields.firefly_timeout.value || 30),
      batch_size: Number(fields.firefly_batch_size.value || 50),
      adaptive_batch_enabled: !!fields.firefly_adaptive_batch_enabled.checked,
      adaptive_target_timeout_ratio: Number(fields.firefly_adaptive_target_ratio.value || 0.75),
      adaptive_max_batch_size: Number(fields.firefly_adaptive_max_batch_size.value || 200),
    },
    importer: {
      json_path: fields.importer_json_path.value.trim(),
    },
    merge: {
      own_accounts: parseLineList(fields.merge_own_accounts.value),
      account_aliases: parseAliases(fields.merge_account_aliases.value),
      savings_accounts: parseSavingsAccounts(fields.merge_savings_accounts.value),
    },
    ollama: {
      enabled: !!fields.ollama_enabled.checked,
      url: fields.ollama_url.value.trim(),
      model: fields.ollama_model.value.trim(),
      temperature: Number(fields.ollama_temperature.value || 0),
      batch_size: Number(fields.ollama_batch_size.value || 20),
      auto_export_after_categorize: !!fields.ollama_auto_export_after_categorize.checked,
      default_categories: textToCategories(fields.ollama_categories.value),
      prompt_template: fields.ollama_prompt_template.value,
    },
  };

  const response = await fetch("/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const body = await response.json();
    throw new Error(body.detail || "Failed to save config.");
  }
  setStatus("Configuration saved.");
}

function downloadConfig(format) {
  const token = String(format || "yaml").toLowerCase();
  window.location.assign(`/api/config/export?format=${encodeURIComponent(token)}`);
}

async function importConfigFile() {
  const file = importConfigFileInput && importConfigFileInput.files && importConfigFileInput.files[0];
  if (!file) {
    throw new Error("Select a config file to import.");
  }
  setStatus("Importing configuration...");
  const formData = new FormData();
  formData.append("config_file", file);
  const response = await fetch("/api/config/import", {
    method: "POST",
    body: formData,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to import config.");
  }
  await loadConfig();
  setStatus("Configuration imported.");
}

async function writeConfigFile() {
  const path = (configWritePathInput && configWritePathInput.value) || "config/system_config.yml";
  const format = (configWriteFormatInput && configWriteFormatInput.value) || "yaml";
  setStatus("Writing config file on server...");
  const response = await fetch("/api/config/write-file", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, format }),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to write config file.");
  }
  setStatus(`Config written to ${payload.path}`);
}

async function uploadImporterJson() {
  const file = importerJsonUploadInput && importerJsonUploadInput.files && importerJsonUploadInput.files[0];
  if (!file) {
    throw new Error("Select an importer JSON file.");
  }
  setStatus("Uploading importer JSON...");
  const formData = new FormData();
  formData.append("importer_file", file);
  const response = await fetch("/api/config/importer-json", {
    method: "POST",
    body: formData,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to upload importer JSON.");
  }
  fields.importer_json_path.value = payload.path || "";
  setStatus(summarizeVerification(payload.verification));
}

async function verifyImporterJson() {
  const configuredPath = String(fields.importer_json_path.value || "").trim();
  const params = new URLSearchParams();
  if (configuredPath) {
    params.set("path", configuredPath);
  }
  const query = params.toString();
  const response = await fetch(`/api/config/importer-json/verify${query ? `?${query}` : ""}`);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to verify importer JSON.");
  }
  setStatus(summarizeVerification(payload.verification || {}));
}

async function resetAllSettings() {
  const clearFiles = window.confirm("Also delete uploaded importer JSON files?");
  setStatus("Resetting settings...");
  const response = await fetch("/api/config/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ clear_uploaded_importer_files: clearFiles }),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to reset settings.");
  }
  await loadConfig();
  if (importerJsonUploadInput) {
    importerJsonUploadInput.value = "";
  }
  const deleted = Number(payload.deleted_importer_files || 0);
  setStatus(`Settings reset to defaults. Deleted importer files: ${deleted}.`);
}

form.addEventListener("submit", async (event) => {
  try {
    await saveConfig(event);
  } catch (error) {
    setStatus(error.message);
  }
});

if (exportYamlBtn) {
  exportYamlBtn.addEventListener("click", () => downloadConfig("yaml"));
}

if (exportJsonBtn) {
  exportJsonBtn.addEventListener("click", () => downloadConfig("json"));
}

if (importConfigBtn) {
  importConfigBtn.addEventListener("click", async () => {
    try {
      await importConfigFile();
    } catch (error) {
      setStatus(error.message);
    }
  });
}

if (writeConfigFileBtn) {
  writeConfigFileBtn.addEventListener("click", async () => {
    try {
      await writeConfigFile();
    } catch (error) {
      setStatus(error.message);
    }
  });
}

if (uploadImporterJsonBtn) {
  uploadImporterJsonBtn.addEventListener("click", async () => {
    try {
      await uploadImporterJson();
    } catch (error) {
      setStatus(error.message);
    }
  });
}

if (verifyImporterJsonBtn) {
  verifyImporterJsonBtn.addEventListener("click", async () => {
    try {
      await verifyImporterJson();
    } catch (error) {
      setStatus(error.message);
    }
  });
}

if (resetConfigBtn) {
  resetConfigBtn.addEventListener("click", async () => {
    const approved = window.confirm("Reset all settings to defaults?");
    if (!approved) {
      return;
    }
    try {
      await resetAllSettings();
    } catch (error) {
      setStatus(error.message);
    }
  });
}

loadConfig().catch((error) => {
  setStatus(error.message);
});
