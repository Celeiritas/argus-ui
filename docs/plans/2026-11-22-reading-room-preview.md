# Reading room preview delivery

The owner likes the ancient-library direction and needs an easy way to try it on a phone, with a salient icon and color system.

- [x] Provide consistent violet/open-book, cyan/document, amber/pencil and green/compass identities. Carry them across labeled shelf buttons, covers, current-shelf context and navigation. Use selection outlines independently of category identity.
- [x] Bundle an explicitly labeled sample preview in the existing owner-only Memory plugin sandbox. Link it from Library and provide a return link, instructions, ordinary scrolling, drag index and keyboard/select equivalents.
- [x] Keep ten recent sample reads, separate ribbons, focus reading and browser Back/Forward within a page visit. Sample state resets on reload; it never fetches or writes the real catalog.
- [ ] Verify actual bundled bytes, role gate and CSP at both mounts; phone interactions and widths; independent code/visual review; full CI and privacy checks.
- [ ] Merge and deploy under the owner's standing authorization after checks pass; verify live version and preview availability.

This is a testable design preview. Applying it to the real catalog still requires full filtered-catalog index support, source-type mapping beyond these four sample shelves, and real reader integration. Do not mistake the 16 sample titles for the production catalog.
