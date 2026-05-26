#!/usr/bin/env node
/**
 * Zero-dependency born-digital PDF generator for GeneralFiles test samples.
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(__dirname, "..", "testfiles", "GeneralFiles");

function escPdf(text) {
  return String(text).replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");
}

function buildPdf(pages) {
  const objects = [];
  const add = (body) => {
    objects.push(body);
    return objects.length;
  };

  const fontRegular = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>");
  const fontBold = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>");

  const pageObjIds = [];

  for (const page of pages) {
    const contentLines = ["BT"];
    for (const item of page.items) {
      const fontId = item.bold ? fontBold : fontRegular;
      const size = item.size || 11;
      contentLines.push(`/F${fontId} ${size} Tf`);
      contentLines.push(`1 0 0 1 ${item.x} ${item.y} Tm`);
      contentLines.push(`(${escPdf(item.text)}) Tj`);
    }
    for (const line of page.lines || []) {
      contentLines.push(`${line.width || 0.5} w`);
      contentLines.push(`${line.x1} ${line.y1} m ${line.x2} ${line.y2} l S`);
    }
    contentLines.push("ET");
    const stream = contentLines.join("\n");
    const contentId = add(`<< /Length ${Buffer.byteLength(stream, "utf8")} >>\nstream\n${stream}\nendstream`);
    const pageId = add(
      `<< /Type /Page /Parent {{PAGES}} 0 R /MediaBox [0 0 612 792] ` +
        `/Resources << /Font << ` +
        `/F${fontRegular} ${fontRegular} 0 R /F${fontBold} ${fontBold} 0 R >> >> ` +
        `/Contents ${contentId} 0 R >>`
    );
    pageObjIds.push(pageId);
  }

  const kids = pageObjIds.map((id) => `${id} 0 R`).join(" ");
  const pagesId = add(`<< /Type /Pages /Kids [ ${kids} ] /Count ${pageObjIds.length} >>`);

  for (let i = 0; i < objects.length; i++) {
    if (objects[i].includes("{{PAGES}}")) {
      objects[i] = objects[i].replace("{{PAGES}}", String(pagesId));
    }
  }

  const catalogId = add(`<< /Type /Catalog /Pages ${pagesId} 0 R >>`);

  let pdf = "%PDF-1.4\n";
  const offsets = [0];
  for (let i = 0; i < objects.length; i++) {
    offsets.push(Buffer.byteLength(pdf, "utf8"));
    pdf += `${i + 1} 0 obj\n${objects[i]}\nendobj\n`;
  }

  const xrefPos = Buffer.byteLength(pdf, "utf8");
  pdf += `xref\n0 ${objects.length + 1}\n`;
  pdf += "0000000000 65535 f \n";
  for (let i = 1; i <= objects.length; i++) {
    pdf += `${String(offsets[i]).padStart(10, "0")} 00000 n \n`;
  }
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root ${catalogId} 0 R >>\n`;
  pdf += `startxref\n${xrefPos}\n%%EOF\n`;
  return pdf;
}

function tablePage(title, subtitle, headers, rows, bordered = true) {
  const items = [];
  const lines = [];
  items.push({ text: title, x: 50, y: 740, size: 14, bold: true });
  if (subtitle) items.push({ text: subtitle, x: 50, y: 720, size: 10, bold: false });

  const startX = 50;
  let y = 690;
  const colWidths = headers.length === 4 ? [80, 220, 90, 120] : [85, 200, 90, 100];
  const rowH = 20;
  let x = startX;

  headers.forEach((h, i) => {
    items.push({ text: h, x: x + 4, y: y - 14, size: 10, bold: true });
    if (bordered) {
      lines.push({ x1: x, y1: y - rowH, x2: x + colWidths[i], y2: y - rowH });
      lines.push({ x1: x, y1: y, x2: x, y2: y - rowH });
    }
    x += colWidths[i];
  });
  if (bordered) {
    lines.push({ x1: startX + colWidths.reduce((a, b) => a + b, 0), y1: y, x2: startX + colWidths.reduce((a, b) => a + b, 0), y2: y - rowH });
    lines.push({ x1: startX, y1: y, x2: startX + colWidths.reduce((a, b) => a + b, 0), y2: y });
  }
  y -= rowH;

  rows.forEach((row) => {
    x = startX;
    row.forEach((cell, i) => {
      items.push({ text: cell, x: x + 4, y: y - 14, size: 10, bold: false });
      if (bordered) {
        lines.push({ x1: x, y1: y - rowH, x2: x + colWidths[i], y2: y - rowH });
        lines.push({ x1: x, y1: y, x2: x, y2: y - rowH });
      }
      x += colWidths[i];
    });
    if (bordered) {
      lines.push({ x1: startX + colWidths.reduce((a, b) => a + b, 0), y1: y, x2: startX + colWidths.reduce((a, b) => a + b, 0), y2: y - rowH });
      lines.push({ x1: startX, y1: y, x2: startX + colWidths.reduce((a, b) => a + b, 0), y2: y });
    }
    y -= rowH;
  });

  return { items, lines };
}

function textPage(title, subtitle, bodyLines) {
  const items = [{ text: title, x: 50, y: 740, size: 14, bold: true }];
  if (subtitle) items.push({ text: subtitle, x: 50, y: 720, size: 10, bold: false });
  let y = 690;
  bodyLines.forEach((line) => {
    items.push({ text: line, x: 50, y, size: 10, bold: line === bodyLines[0], mono: true });
    y -= 16;
  });
  return { items, lines: [] };
}

function write(name, pages) {
  const outPath = path.join(OUT, name);
  fs.mkdirSync(OUT, { recursive: true });
  fs.writeFileSync(outPath, buildPdf(pages), "utf8");
  console.log("Wrote", outPath);
}

write("financial_report_01.pdf", [
  tablePage(
    "Acme Corp — Quarterly Transaction Report",
    "Report Period: Q1 2024    Currency: USD    Vendor: Acme Reporting",
    ["Date", "Description", "Amount", "Category"],
    [
      ["2024-01-05", "Office supplies — Staples", "$245.00", "Office"],
      ["2024-01-12", "Cloud software subscription", "$1,299.00", "Software"],
      ["2024-01-18", "Client travel — NYC", "$892.50", "Travel"],
      ["2024-02-02", "Utility payment — electric", "$410.00", "Utilities"],
      ["2024-02-14", "Product revenue deposit", "$15,200.00", "Revenue"],
    ],
    true
  ),
]);

write("financial_report_02.pdf", [
  tablePage(
    "GlobalFin Services — Account Activity Summary",
    "Account: OPER-7782    Statement Date: 2024-03-31",
    ["Posting Date", "Memo", "Debit", "Type"],
    [
      ["03/01/2024", "WIRE IN — CLIENT PAYMENT", "12,500.00", "Revenue"],
      ["03/05/2024", "ACH OUT — PAYROLL VENDOR", "8,200.00", "Payroll"],
      ["03/09/2024", "POS — OFFICE DEPOT #442", "156.78", "Office"],
      ["03/15/2024", "SaaS — ANALYTICS PLATFORM", "499.00", "Software"],
      ["03/22/2024", "AIRLINE — CONFERENCE TRAVEL", "1,045.60", "Travel"],
    ],
    true
  ),
]);

write("bank_statement_sample.pdf", [
  tablePage(
    "First National Bank — Business Checking Statement",
    "Statement Period: Feb 1 – Feb 29, 2024",
    ["Date", "Description", "Amount", "Balance"],
    [
      ["02/01", "Opening balance", "", "25,000.00"],
      ["02/03", "Deposit — Invoice #1042", "3,400.00", "28,400.00"],
      ["02/07", "Withdrawal — Rent", "-2,100.00", "26,300.00"],
      ["02/12", "Fee — wire transfer", "-25.00", "26,275.00"],
    ],
    true
  ),
]);

write("transaction_ledger_unbordered.pdf", [
  textPage("Vendor B — Transaction Ledger (text-aligned columns)", null, [
    "Date        Description                      Amount     Category",
    "2024-04-01  Software license renewal         890.00     Software",
    "2024-04-08  Office furniture                 450.00     Office",
    "2024-04-15  Utility bill                     210.00     Utilities",
    "2024-04-22  Consulting revenue               5200.00    Revenue",
  ]),
]);

write("financial_report_scansim.pdf", [
  tablePage(
    "ScanSim Corp — Monthly Expense Summary",
    "(Low-density text sample for scan / OCR routing tests)",
    ["Date", "Description", "Amount", "Category"],
    [
      ["2024-05-01", "Misc expense", "$120.00", "Office"],
      ["2024-05-10", "Travel", "$340.00", "Travel"],
    ],
    false
  ),
]);

const readme = `# GeneralFiles — Trial / Cloud Test Samples

| File | Purpose | Suggested track |
|------|---------|-----------------|
| \`financial_report_01.pdf\` | Bordered transaction table (Acme Q1) | Lite + Pro \`financial_report\` KIE |
| \`financial_report_02.pdf\` | Alternate vendor layout (GlobalFin) | Lite + Pro KIE |
| \`bank_statement_sample.pdf\` | Bank statement with Date/Amount/Balance | Lite table → transactions mapping |
| \`transaction_ledger_unbordered.pdf\` | Monospace columns, weak borders | Lite borderless / text routing |
| \`financial_report_scansim.pdf\` | Sparse layout | Lite scan-profile / OCR path |

Regenerate: \`node test_data/scripts/generate_general_testfiles_pure.mjs\`
`;
fs.writeFileSync(path.join(OUT, "README.md"), readme, "utf8");
console.log("Done.");
