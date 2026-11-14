"""Execute the actual template modules: absent spoken cues cannot become guessed times.

The templates initialise through the explicit init entry of their sibling
.mjs (modules/modules.md). The driver below is a minimal non-rendering stub
environment: it records every timeline call and which parts get hidden, so
the cue contract is checked against the real module code without a browser.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / 'modules/templates/github-trending'
DRIVER = r'''
const fs = require('fs'), vm = require('vm');
const source = fs.readFileSync(process.argv[1], 'utf8');
const vars = JSON.parse(process.argv[2]), data = JSON.parse(process.argv[3]);
const elements = {}, calls = [];
let counter = 0;
function makeElement(name) {
  const el = {
    __name: name, style: {},
    append() {}, appendChild() {},
    remove() { this.removed = true; },
    querySelector(selector) {
      return element(((this.__id || this.__name) + ' ' + selector).trim());
    },
  };
  Object.defineProperty(el, 'id', {
    get() { return this.__id || ''; },
    set(value) { this.__id = value; },
  });
  return el;
}
function element(name) {
  if (!elements[name]) elements[name] = makeElement(name);
  return elements[name];
}
const root = element('');
const tl = {};
for (const method of ['fromTo','to','set']) tl[method] = (...args) => {
  const target = args[0];
  const name = Array.isArray(target) ? 'array'
    : (target && (target.__id || target.__name)) || typeof target;
  calls.push({method, target: name, at: args[method === 'fromTo' ? 3 : 2]});
  return tl;
};
let error = null;
try {
  const context = {
    gsap: {timeline() {return tl}},
    getComputedStyle() {return {getPropertyValue() {return '#222'}, fontFamily: 'sans'}},
    document: {createElement(tag) {return element(tag + '#' + (++counter))}},
  };
  vm.createContext(context);
  vm.runInContext(source.replace(/\bexport function init\b/, 'function init'), context);
  context.init(root, {params: vars, data, duration: 6, gsap: context.gsap});
} catch (e) {error = e.message;}
console.log(JSON.stringify({error, calls, hidden: Object.entries(elements)
  .filter(([, el]) => el.removed || el.style.display === 'none')
  .map(([name]) => name.split(' ').pop().replace(/^#/, ''))}));
'''


def execute(name: str, variables: dict, data: dict | None = None) -> dict:
    proc = subprocess.run(
        ['node', '-e', DRIVER, str(TEMPLATES / f'{name}.mjs'),
         json.dumps(variables), json.dumps(data or {})],
        capture_output=True, text=True, check=True, timeout=10,
    )
    return json.loads(proc.stdout)


def test_project_cover_without_optional_cues_hides_the_corresponding_parts():
    result = execute('project-cover', dict(owner='demo', repo='tool', nameAt=0,
                    tagline='Not spoken', topics='test', stars=2000, lang='Rust'))
    assert result['error'] is None
    assert {'pc-tag', 'pc-topics', 'pc-stats', 'pc-meta'} <= set(result['hidden'])
    assert not any(c['target'].startswith(('#pc-tag', '#pc-topics', '#pc-stats', '#pc-meta'))
                   for c in result['calls'])


@pytest.mark.parametrize('value', [None, '', -1, 'not a cue', True])
def test_project_cover_requires_a_real_name_cue(value):
    result = execute('project-cover', dict(owner='demo', repo='tool', nameAt=value))
    assert 'nameAt' in result['error']
    assert result['calls'] == []


def test_project_cover_uses_supplied_cues_including_zero():
    result = execute('project-cover', dict(nameAt=0, tagline='Spoken', taglineAt=1.25,
                                         stars=2000, starsAt=2.75))
    assert result['error'] is None
    assert any(c['target'] == '#pc-tag' and c['at'] == 1.25 for c in result['calls'])
    assert any(c['target'] == '#pc-stats' and c['at'] == 2.75 for c in result['calls'])


def test_trending_overview_rejects_missing_repo_cues():
    result = execute('trending-overview', {}, {'repos': [
        dict(owner='demo', repo='tool', readme='x.png'),
    ]})
    assert 'cue' in result['error']
    assert result['calls'] == []


def test_trending_overview_uses_supplied_repo_cues():
    result = execute('trending-overview', {}, {'repos': [
        dict(owner='demo', repo='tool', readme='x.png', cue=1.25),
        dict(owner='demo', repo='other', readme='y.png', cue=3.5),
    ]})
    assert result['error'] is None
    assert any(c['target'] == 'to-row1 .tint' and c['at'] == 1.25 for c in result['calls'])
    assert any(c['target'] == 'to-row2 .tint' and c['at'] == 3.5 for c in result['calls'])


def test_template_metadata_and_contract_declare_required_and_optional_cues_without_defaults():
    text = (TEMPLATES / 'project-cover.html').read_text(encoding='utf-8')
    variables = json.loads(re.search(r"data-composition-variables='(.*?)'", text, flags=re.S).group(1))
    for variable in variables:
        if variable['id'] in ('nameAt', 'taglineAt', 'starsAt'):
            assert 'default' not in variable

    contract = json.loads((TEMPLATES / 'github-trending.json').read_text(encoding='utf-8'))
    assert contract['anchor_fields'] == {
        'project-cover': {'required': ['nameAt'], 'optional': ['taglineAt', 'starsAt']},
        'trending-overview': {'required': ['repos[].cue'], 'optional': []},
    }
