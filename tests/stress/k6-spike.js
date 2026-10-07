import http from 'k6/http';
import { Trend } from 'k6/metrics';
import { check } from 'k6';

// Uso: k6 run tests/stress/k6-spike.js
const statusTrend = new Trend('status_codes');

export const options = {
    stages: [
        { duration: '10s', target: 100 },
        { duration: '20s', target: 100 },
        { duration: '10s', target: 0 },
    ],
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';

const pdfFiles = [
    open('./pdfs/2020-Scrum-Guide-Spanish-Latin-South-American.pdf', 'b'),
    open('./pdfs/Essential-Kanban-Condensed-Spanish.pdf', 'b'),
    open('./pdfs/Filosofia Lean.pdf', 'b'),
    open('./pdfs/scrum_manager_historias_usuario.pdf', 'b'),
];

export default function () {
    const randomPdf = pdfFiles[Math.floor(Math.random() * pdfFiles.length)];

    const params = {
        headers: {
            'Content-Type': 'application/pdf',
        },
    };

    const res = http.post(`${BASE_URL}/extract`, randomPdf, params);

    statusTrend.add(res.status);

    check(res, {
        'status 200': (r) => r.status === 200,
    });
}
