import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { getFraudResultPresentation, getHistoryResultPresentation } from '../src/shared/results/fraudResultPresentation.js';
import { getHistoryOutcome } from '../src/features/history/utils/historyView.js';
import { createHistoryDetailController } from '../src/features/history/utils/historyDetail.js';

// The backend Flex tests consume this exact same matrix.
const cases = JSON.parse(readFileSync(new URL('../../../tests/fixtures/result_presentation_cases.json', import.meta.url)));

test('link, QR and text scans, History cards/popups and Summary share the Flex tone contract', async () => {
    for (const { name, type, result, tone } of cases) {
        const before = JSON.stringify(result);
        const scan = getFraudResultPresentation({ ...result, type });
        const history = { ...result, id: 'stored', type, message_text: 'synthetic input', classification: result.category,
            url_check_result: result.url_check ?? { verification_verdict: result.verification_verdict } };
        const card = getHistoryResultPresentation(history);
        assert.equal(scan.tone, tone, name);
        assert.equal(card.tone, tone, name);
        assert.equal(card.status, scan.status, name);
        assert.equal(card.showConfidence, false);
        assert.equal(getHistoryOutcome(history), tone === 'green' ? 'safe' : tone === 'red' ? 'risk'
            : result.verification_verdict === 'INVALID' ? 'invalid' : 'unknown', name);
        const popups = [];
        const flow = createHistoryDetailController({ getDetail: async () => history,
            swal: { fire: popup => popups.push(popup), showLoading() {}, close() {} }, typeName: value => value });
        await flow.open(history);
        const popup = popups.at(-1);
        assert.equal(popup.title, card.status, name);
        assert.equal(popup.iconColor, card.statusColor, name);
        assert.equal(popup.confirmButtonColor, card.statusColor, name);
        assert.equal(JSON.stringify(result), before, name);
        flow.dispose();
    }
});

test('both scanner result entrypoints use the shared verdict and explicit icon tone', () => {
    for (const path of ['../src/features/scanner/scanner.jsx', '../src/features/scanner/ScanImage.jsx']) {
        const source = readFileSync(new URL(path, import.meta.url), 'utf8');
        assert.match(source, /const presentation = getFraudResultPresentation\(result\)/u);
        assert.match(source, /iconColor: statusColor/u);
        assert.match(source, /confirmButtonColor: statusColor/u);
        assert.doesNotMatch(source, /is_fraud === false/u);
    }
});
