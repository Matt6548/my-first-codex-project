// reportGenerators.js
import fs from 'fs';
import json2xls from 'json2xls'; // или xlsxwriter
import { Document } from 'docx';
import { FPDF } from 'fpdf';

export function toJsonReport(text, meta) {
  return JSON.stringify({ meta, analysis: text }, null, 2);
}

export function toDocxReport(text, meta) {
  const doc = new Document();
  doc.addSection({ children: [
    new Paragraph({ text: meta.title, heading: HeadingLevel.HEADING_1 }),
    new Paragraph(text)
  ]});
  const buf = Packer.toBuffer(doc);
  const path = `report_${meta.code}.docx`;
  fs.writeFileSync(path, buf);
  return path;
}

export function toExcelReport(text, meta) {
  const data = [{ meta: JSON.stringify(meta), analysis: text }];
  const xls = json2xls(data);
  const path = `report_${meta.code}.xlsx`;
  fs.writeFileSync(path, xls, 'binary');
  return path;
}

export function toPdfReport(text, meta) {
  const pdf = new FPDF();
  pdf.AddPage();
  pdf.SetFont('Arial', '', 12);
  text.split('\\n').forEach(line => pdf.Cell(0, 5, line, 0, 1));
  const path = `report_${meta.code}.pdf`;
  pdf.Output('F', path);
  return path;
}
