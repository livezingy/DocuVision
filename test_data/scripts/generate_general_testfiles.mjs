#!/usr/bin/env node
/**
 * Generate GeneralFiles test PDFs for Lite (table) and Pro (KIE financial_report) demos.
 * Usage: node generate_general_testfiles.mjs  (requires: npm install pdfkit)
 */
import PDFDocument from "pdfkit";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(__dirname, "..", "testfiles", "GeneralFiles");

function ensureOut() {
  fs.mkdirSync(OUT, { recursive: true });
}

function drawTable(doc, startX, startY, colWidths, headers, rows, bordered = true) {
  const rowH = 22;
  const pad = 4;
  let y = startY;

  const drawRow = (cells, isHeader = false) => {
    let x = startX;
    cells.forEach((cell, i) => {
      const w = colWidths[i];
      if (bordered) {
        doc.rect(x, y, w, rowH).stroke();
      }
      doc
        .font(isHeader ? "Helvetica-Bold" : "Helvetica")
        .fontSize(10)
        .text(String(cell ?? ""), x + pad, y + 6, { width: w - pad * 2, lineBreak: false });
      x += w;
    });
    y += rowH;
  };

  drawRow(headers, true);
  rows.forEach((row) => drawRow(row));
  return y;
}

function writePdf(filename, build) {
  return new Promise((resolve, reject) => {
    const outPath = path.join(OUT, filename);
    const doc = new PDFDocument({ margin: 50, size: "LETTER" });
    const stream = fs.createWriteStream(outPath);
    doc.pipe(stream);
    build(doc);
    doc.end();
    stream.on("finish", () => {
      console.log("Wrote", outPath);
      resolve(outPath);
    });
    stream.on("error", reject);
  });
}

async function genFinancialReport01(doc) {
  doc.font("Helvetica-Bold").fontSize(16).text("Acme Corp — Quarterly Transaction Report", { align: "center" });
  doc.moveDown(0.5);
  doc.font("Helvetica").fontSize(11).text("Report Period: Q1 2024    Currency: USD    Vendor: Acme Reporting", {
    align: "center",
  });
  doc.moveDown(1);
  drawTable(
    doc,
    50,
    doc.y,
    [80, 200, 90, 120],
    ["Date", "Description", "Amount", "Category"],
    [
      ["2024-01-05", "Office supplies — Staples", "$245.00", "Office"],
      ["2024-01-12", "Cloud software subscription", "$1,299.00", "Software"],
      ["2024-01-18", "Client travel — NYC", "$892.50", "Travel"],
      ["2024-02-02", "Utility payment — electric", "$410.00", "Utilities"],
      ["2024-02-14", "Product revenue deposit", "$15,200.00", "Revenue"],
    ],
    true
  );
}

async function genFinancialReport02(doc) {
  doc.font("Helvetica-Bold").fontSize(16).text("GlobalFin Services — Account Activity Summary", { align: "left" });
  doc.moveDown(0.3);
  doc.font("Helvetica").fontSize(10).text("Account: OPER-7782    Statement Date: 2024-03-31");
  doc.moveDown(1);
  drawTable(
    doc,
    50,
    doc.y,
    [95, 210, 85, 110],
    ["Posting Date", "Memo", "Debit", "Type"],
    [
      ["03/01/2024", "WIRE IN — CLIENT PAYMENT", "12,500.00", "Revenue"],
      ["03/05/2024", "ACH OUT — PAYROLL VENDOR", "8,200.00", "Payroll"],
      ["03/09/2024", "POS — OFFICE DEPOT #442", "156.78", "Office"],
      ["03/15/2024", "SaaS — ANALYTICS PLATFORM", "499.00", "Software"],
      ["03/22/2024", "AIRLINE — CONFERENCE TRAVEL", "1,045.60", "Travel"],
    ],
    true
  );
}

async function genBankStatementSample(doc) {
  doc.font("Helvetica-Bold").fontSize(14).text("First National Bank — Business Checking Statement");
  doc.moveDown(0.5);
  doc.font("Helvetica").fontSize(10).text("Statement Period: Feb 1 – Feb 29, 2024");
  doc.moveDown(1);
  drawTable(
    doc,
    50,
    doc.y,
    [85, 185, 80, 95],
    ["Date", "Description", "Amount", "Balance"],
    [
      ["02/01", "Opening balance", "", "25,000.00"],
      ["02/03", "Deposit — Invoice #1042", "3,400.00", "28,400.00"],
      ["02/07", "Withdrawal — Rent", "-2,100.00", "26,300.00"],
      ["02/12", "Fee — wire transfer", "-25.00", "26,275.00"],
    ],
    true
  );
}

async function genTransactionLedgerUnbordered(doc) {
  doc.font("Helvetica-Bold").fontSize(14).text("Vendor B — Transaction Ledger (text-aligned columns)");
  doc.moveDown(0.8);
  doc.font("Courier").fontSize(10);
  const lines = [
    "Date        Description                      Amount     Category",
    "2024-04-01  Software license renewal         890.00     Software",
    "2024-04-08  Office furniture                 450.00     Office",
    "2024-04-15  Utility bill                     210.00     Utilities",
    "2024-04-22  Consulting revenue               5200.00    Revenue",
  ];
  lines.forEach((line) => doc.text(line));
}

async function genScannedStyleReport(doc) {
  doc.font("Helvetica-Bold").fontSize(14).text("ScanSim Corp — Monthly Expense Summary");
  doc.moveDown(0.5);
  doc.font("Helvetica").fontSize(9).fillColor("#444444").text("(Minimal-text PDF simulating low digital text density for scan detection tests)");
  doc.fillColor("#000000");
  doc.moveDown(1);
  drawTable(
    doc,
    50,
    doc.y,
    [80, 190, 90, 110],
    ["Date", "Description", "Amount", "Category"],
    [
      ["2024-05-01", "Misc expense", "$120.00", "Office"],
      ["2024-05-10", "Travel", "$340.00", "Travel"],
    ],
    false
  );
}

async function main() {
  ensureOut();
  await writePdf("financial_report_01.pdf", genFinancialReport01);
  await writePdf("financial_report_02.pdf", genFinancialReport02);
  await writePdf("bank_statement_sample.pdf", genBankStatementSample);
  await writePdf("transaction_ledger_unbordered.pdf", genTransactionLedgerUnbordered);
  await writePdf("financial_report_scansim.pdf", genScannedStyleReport);

  const readme = `# GeneralFiles — Trial / Cloud Test Samples

| File | Purpose | Suggested track |
|------|---------|-----------------|
| \`financial_report_01.pdf\` | Bordered transaction table (Acme Q1) | Lite + Pro \`financial_report\` KIE |
| \`financial_report_02.pdf\` | Alternate vendor layout (GlobalFin) | Lite + Pro KIE |
| \`bank_statement_sample.pdf\` | Bank statement with Date/Amount/Balance | Lite table → transactions mapping |
| \`transaction_ledger_unbordered.pdf\` | Monospace columns, weak borders | Lite borderless / text routing |
| \`financial_report_scansim.pdf\` | Sparse text density | Lite scan-profile / OCR path |

Regenerate: \`cd test_data/scripts && npm install pdfkit && node generate_general_testfiles.mjs\`
`;
  fs.writeFileSync(path.join(OUT, "README.md"), readme, "utf8");
  console.log("Done.");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
