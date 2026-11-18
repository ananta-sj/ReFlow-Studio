import test from 'node:test'
import assert from 'node:assert/strict'
import { nextPreviewTag } from '../publish_development_preview.mjs'

test('first desktop preview starts at v0.7.1 with a readable suffix', () => {
  assert.equal(nextPreviewTag(['v0.7.0-rc.2','development-preview']), 'v0.7.1-desktop-preview')
})
test('next desktop preview advances patch and respects stable or reserved tags', () => {
  assert.equal(nextPreviewTag(['v0.7.2-desktop-preview','v0.7.10-desktop-preview','v0.7.12','v0.8.99-desktop-preview']), 'v0.7.13-desktop-preview')
})
test('malformed and unrelated tags do not become release versions', () => {
  assert.equal(nextPreviewTag(['v0.7.x-desktop-preview','v0.7.9evil','v1.7.100']), 'v0.7.1-desktop-preview')
})
