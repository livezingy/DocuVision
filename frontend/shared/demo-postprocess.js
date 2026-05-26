/**
 * Shared demo post-processing: transactions + classification mapping preview.
 * Used by Lite and Pro frontends during trial demos.
 */
(function (global) {
  const DEFAULT_MAPPINGS = {
    default_internal_code: "UNMAPPED",
    default_internal_label: "Unmapped",
    rules: [],
  };

  const HEADER_ALIASES = {
    date: "date",
    "transaction date": "date",
    description: "description",
    memo: "description",
    amount: "amount",
    debit: "amount",
    credit: "amount",
    category: "category",
    type: "category",
    reference: "reference",
  };

  function normalizeHeader(value) {
    return String(value || "")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, " ");
  }

  function getTableRowData(table) {
    if (Array.isArray(table.data) && table.data.length) {
      return table.data;
    }
    const rows = table.rows;
    if (Array.isArray(rows) && rows.length && Array.isArray(rows[0])) {
      return rows;
    }
    return [];
  }

  function extractTransactionsFromTables(tables) {
    const transactions = [];
    (tables || []).forEach((table) => {
      const rowData = getTableRowData(table);
      const headers = table.headers || (rowData.length ? rowData[0] : []);
      const bodyRows = table.headers ? rowData : rowData.slice(1);
      const headerMap = {};
      headers.forEach((h, idx) => {
        const key = HEADER_ALIASES[normalizeHeader(h)];
        if (key) headerMap[idx] = key;
      });
      if (!Object.keys(headerMap).length && bodyRows.length) {
        headerMap[0] = "date";
        headerMap[1] = "description";
        headerMap[2] = "amount";
      }
      bodyRows.forEach((row, ri) => {
        if (!Array.isArray(row)) return;
        const tx = { source_table: table.table_id || table.id, page: table.page || 1, row_index: ri };
        row.forEach((cell, ci) => {
          const field = headerMap[ci];
          if (field && cell) tx[field] = String(cell).trim();
        });
        if (Object.keys(tx).length > 3) transactions.push(tx);
      });
    });
    return transactions;
  }

  function extractTransactionsFromKie(fields) {
    const items = (fields && fields.items) || [];
    return items
      .map((item, idx) => ({
        source: "kie",
        row_index: idx,
        description: item.description || item.name || "",
        quantity: item.quantity || "",
        unit_price: item.unit_price || item.price || "",
        amount: item.amount || item.total || "",
        category: item.category || "",
      }))
      .filter((tx) => tx.description || tx.amount);
  }

  function extractTransactions(result) {
    if (!result) return [];
    if (result.transactions && result.transactions.length) return result.transactions;
    if (result.mapped_transactions && result.mapped_transactions.length) {
      return result.mapped_transactions;
    }
    if (result.tables && result.tables.length) {
      return extractTransactionsFromTables(result.tables);
    }
    const fields = result.kie_fields || (result.view && result.view.fields) || {};
    return extractTransactionsFromKie(fields);
  }

  function matchRule(value, rule) {
    const external = String(rule.external || "");
    const match = (rule.match || "exact").toLowerCase();
    const v = String(value || "").trim().toLowerCase();
    if (match === "exact") return v === external.toLowerCase();
    if (match === "contains") return v.includes(external.toLowerCase());
    if (match === "prefix") return v.startsWith(external.toLowerCase());
    return false;
  }

  function applyMappings(transactions, config) {
    const cfg = config || DEFAULT_MAPPINGS;
    const defaultCode = cfg.default_internal_code || "UNMAPPED";
    const defaultLabel = cfg.default_internal_label || "Unmapped";
    return (transactions || []).map((tx) => {
      const external = tx.category || tx.description || "";
      let mapping = { internal_code: defaultCode, internal_label: defaultLabel, mapping_rule_id: "" };
      (cfg.rules || []).forEach((rule) => {
        if (matchRule(external, rule)) {
          mapping = {
            internal_code: rule.internal_code || defaultCode,
            internal_label: rule.internal_label || defaultLabel,
            mapping_rule_id: rule.id || "",
          };
        }
      });
      return { ...tx, ...mapping };
    });
  }

  let _mappingConfig = null;

  async function loadMappingConfig(url) {
    if (_mappingConfig) return _mappingConfig;
    const configUrl = url || "/shared/demo_classification_mappings.json";
    try {
      const res = await fetch(configUrl);
      if (res.ok) {
        _mappingConfig = await res.json();
        return _mappingConfig;
      }
    } catch (_) { /* fallback */ }
    _mappingConfig = DEFAULT_MAPPINGS;
    return _mappingConfig;
  }

  async function enrichResult(result, mappingUrl) {
    const transactions = extractTransactions(result);
    const config = await loadMappingConfig(mappingUrl);
    const mapped = applyMappings(transactions, config);
    return { transactions, mapped_transactions: mapped };
  }

  global.DocuVisionDemo = {
    extractTransactions,
    applyMappings,
    loadMappingConfig,
    enrichResult,
    DEFAULT_MAPPINGS,
  };
})(typeof window !== "undefined" ? window : globalThis);
