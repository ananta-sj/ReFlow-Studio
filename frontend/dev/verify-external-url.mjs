import assert from 'node:assert/strict'
import { safeExternalUrl } from '../src/lib/external-url.ts'

for (const value of [undefined, '', 'javascript:alert(1)', 'data:text/html,test',
  'file:///C:/secret', '//evil.test', 'https://user:secret@example.com',
  'https://example.com\\@evil.test', 'https://example.com\n']) {
  assert.equal(safeExternalUrl(value), undefined, `Rejected: ${value}`)
}
assert.equal(safeExternalUrl('https://example.com/project'), 'https://example.com/project')
assert.equal(safeExternalUrl('http://example.com/project'), 'http://example.com/project')
console.log('External URL security checks passed')
