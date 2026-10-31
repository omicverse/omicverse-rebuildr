import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
import loop
from benchmark import TimingResult
from parity_metrics import compute_parity, is_pass, extract_output


def template_module():
    spec = importlib.util.spec_from_file_location('parity_metrics.template', ROOT / 'templates/test_exact_match.template.py')
    module = importlib.util.module_from_spec(spec)
    # Resolve the template's relative import against the vendored-equivalent module.
    sys.modules['parity_metrics.parity_metrics'] = sys.modules['parity_metrics']
    spec.loader.exec_module(module)
    return module


def test_shape_mismatch_is_not_flattened_away():
    with pytest.raises(ValueError, match='shape mismatch'):
        compute_parity(np.arange(6).reshape(2, 3), np.arange(6).reshape(3, 2), 'deterministic')
    assert compute_parity([[1, 2]], [[1, 2]], 'deterministic') == 0


def test_inference_honors_threshold_and_top_k():
    metric = compute_parity(np.arange(1, 11) / 11, np.arange(1, 11) / 11, 'inference', top_k=3)
    assert is_pass(metric, 'inference', top_k=3)
    metric['spearman_neglog10p'] = 0.94
    assert is_pass(metric, 'inference', 0.90, top_k=3)
    assert not is_pass(metric, 'inference', 0.95, top_k=3)
    metric['top3_jaccard'] = 0.6
    assert not is_pass(metric, 'inference', 0.90, top_k=3)


@pytest.mark.parametrize('location,blob', [
    ('$.nested.value', {'nested': {'value': [1, 2]}}),
    ("adata.obs['value']", {'value': [1, 2]}),
    ('adata.value', {'value': [1, 2]}),
])
def test_output_locations(location, blob):
    assert extract_output(blob, location) == [1, 2]


@pytest.mark.parametrize('inference', [False, True])
def test_manifest_loop_and_pytest_template_agree(tmp_path, inference):
    raw = yaml.safe_load((ROOT / 'engine/manifest.template.yaml').read_text(encoding='utf-8'))
    values = [0.01, 0.02, 0.03, 0.04]
    output = raw['outputs'][0]
    output['location_reference'] = '$.nested.values'
    output['location_candidate'] = '$.nested.values'
    if inference:
        output.update(metric='inference', metric_params={'top_k': 2}, threshold=0.95)
    manifest_path = tmp_path / 'manifest.yaml'
    manifest_path.write_text(yaml.safe_dump(raw))
    ref = {'nested': {'values': values}}
    cand = {'nested': {'values': values}}
    ref_path = tmp_path / 'ref.json'
    cand_path = tmp_path / 'cand.json'
    ref_path.write_text(json.dumps(ref))
    cand_path.write_text(json.dumps(cand))
    manifest = loop.Manifest.load(manifest_path)
    assert loop.parity_diff(manifest, ref_path, cand_path).passed
    template_module().test_parity_against_R(raw, ref, cand)
    cand['nested']['values'] = [0.02, 0.04, 0.01, 0.03]
    cand_path.write_text(json.dumps(cand))
    assert not loop.parity_diff(manifest, ref_path, cand_path).passed
    with pytest.raises(AssertionError, match='Parity gate failed'):
        template_module().test_parity_against_R(raw, ref, cand)


@pytest.mark.parametrize('runs,expected', [([2, 2, 2], 2), ([1, 1, 1, 1, 10], 1)])
def test_loop_uses_repeated_timer(monkeypatch, tmp_path, runs, expected):
    def timer(fn, manifest, port_dir):
        assert fn is loop.run_candidate
        assert port_dir == tmp_path
        return TimingResult(warmup_run_s=99, wall_clock_runs_s=runs)
    monkeypatch.setattr(loop, 'time_callable', timer)
    assert loop._stopwatch_run_candidate(None, tmp_path) == expected
