# Test stand-in: a bundled plugin that the owner's own demo-server (tests/plugin-fixtures) replaces. Never loaded.
raise RuntimeError('the bundled demo-server must not load: the owner\'s copy wins')
