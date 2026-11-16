# Test stand-in for a server plugin with a bug: it fails on import, and LeafyGrove must start anyway.
raise ImportError('this plugin is broken on purpose')
